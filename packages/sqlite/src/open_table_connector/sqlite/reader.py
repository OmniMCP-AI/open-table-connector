"""SQLite Base-mode Connector using the Python DB-API."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from contextvars import ContextVar
import re
import sqlite3
from datetime import date, datetime
from typing import Any, Callable
from urllib.parse import unquote, urlsplit

import polars as pl
import pyarrow as pa

from open_table_connector.contract import (
    ArrowReadResult,
    ArrowTableReader,
    BaseConvention,
    ConnectorError,
    ConnectorErrorCode,
    ExecutionRequest,
    ExecutionResult,
    InspectRequest,
    NeutralReceipt,
    PolarsReadResult,
    PolarsTableReader,
    ResourceLimits,
    ResolveContext,
    ResolvedTable,
    SqlExecutor,
    TableInspection,
    TableInspector,
    TableMode,
    TableReadRequest,
    TableURI,
    TableWriteRequest,
    TableWriteResult,
    TableWriter,
    TransactionalStore,
    URIResolver,
)
from open_table_connector.contract.fingerprints import arrow_content_fingerprint, arrow_schema_fingerprint, operation_identity

from .identity import (
    CONNECTOR_IDENTITY,
    TABLE_EXECUTE_CAPABILITY,
    TABLE_INSPECT_CAPABILITY,
    TABLE_READ_ARROW_CAPABILITY,
    TABLE_READ_POLARS_CAPABILITY,
    TABLE_WRITE_CAPABILITY,
)

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*)?$")


@dataclass(frozen=True)
class SQLiteReadOptions:
    table: str | None = None
    query: str | None = None
    parameters: tuple[Any, ...] = ()
    key_fields: tuple[str, ...] = ()
    record_id_field: str | None = None

    def __post_init__(self) -> None:
        if (self.table is None) == (self.query is None):
            raise ValueError("SQLiteReadOptions requires exactly one table or query")
        if self.table is not None and not _IDENTIFIER.fullmatch(self.table):
            raise ValueError("table must be a simple qualified identifier")
        if self.query is not None and not self.query.lstrip().casefold().startswith(("select", "with")):
            raise ValueError("SQLite query reads must be SELECT or WITH statements")
        object.__setattr__(self, "parameters", tuple(self.parameters))
        object.__setattr__(self, "key_fields", tuple(self.key_fields))


@dataclass(frozen=True)
class SQLiteTableReadRequest(TableReadRequest):
    options: SQLiteReadOptions = field(default_factory=lambda: SQLiteReadOptions(table="main.table"))


@dataclass(frozen=True)
class ResolvedSQLite:
    uri: TableURI
    path: str


class SQLiteTransaction:
    """Explicit transaction handle with context-local legacy routing."""

    def __init__(self, connector: "SQLiteConnector", uri: TableURI, connection: Any) -> None:
        self._connector = connector
        self.uri = uri
        self._connection = connection
        self._closed = False

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self._ensure_open(request.uri)
        return self._connector.execute(request)

    def write(self, request: TableWriteRequest) -> TableWriteResult:
        self._ensure_open(request.uri)
        return self._connector.write(request)

    def commit(self) -> None:
        self._finish(commit=True)

    def abort(self) -> None:
        self._finish(commit=False)

    def _finish(self, *, commit: bool) -> None:
        if self._closed:
            raise ConnectorError(ConnectorErrorCode.CONFLICT, "SQLite transaction is closed", {})
        try:
            self._connection.commit() if commit else self._connection.rollback()
        finally:
            self._connection.close()
            self._closed = True
            self._connector._clear_transaction(self)

    def _ensure_open(self, uri: TableURI) -> None:
        if self._closed:
            raise ConnectorError(ConnectorErrorCode.CONFLICT, "SQLite transaction is closed", {})
        if uri != self.uri:
            raise ConnectorError(
                ConnectorErrorCode.CONFLICT,
                "SQLite transaction cannot cross database URIs",
                {},
            )


def _rows_to_arrow(description: Any, rows: list[tuple[Any, ...]]) -> pa.Table:
    names = [str(item[0]) for item in description]
    columns = []
    for index in range(len(names)):
        values = [row[index] for row in rows]
        column = pa.array(values)
        if pa.types.is_string(column.type):
            column = pa.array(values, type=pa.large_string())
        columns.append(column)
    return pa.Table.from_arrays(columns, names=names)


class SQLiteConnector(
    URIResolver,
    TableInspector,
    ArrowTableReader,
    PolarsTableReader,
    SqlExecutor,
    TableWriter,
    TransactionalStore,
):
    identity = CONNECTOR_IDENTITY

    def __init__(self, connection_factory: Callable[[str], Any] | None = None) -> None:
        self._connection_factory = connection_factory or sqlite3.connect
        self._transaction_context: ContextVar[SQLiteTransaction | None] = ContextVar(
            f"sqlite_transaction_{id(self)}",
            default=None,
        )

    @staticmethod
    def _execution_id(request: ExecutionRequest) -> str:
        payload = f"{request.uri.value}\0{request.statement}".encode("utf-8")
        return "exec_" + sha256(payload).hexdigest()

    @staticmethod
    def _quote(identifier: str) -> str:
        return '"' + identifier.replace('"', '""') + '"'

    @staticmethod
    def _column_type(dtype: pl.DataType) -> str:
        if dtype in (pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64, pl.Boolean):
            return "INTEGER"
        if dtype in (pl.Float32, pl.Float64):
            return "REAL"
        if dtype == pl.Binary:
            return "BLOB"
        return "TEXT"

    @staticmethod
    def _value(value: Any) -> Any:
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, (dict, list, tuple, set, frozenset)):
            return str(value)
        return value

    def resolve(self, uri: TableURI, context: ResolveContext) -> ResolvedTable:
        if uri.scheme != "sqlite":
            raise ConnectorError(ConnectorErrorCode.INVALID_URI, "SQLite Connector requires sqlite URI", {"scheme": uri.scheme})
        parsed = urlsplit(uri.value)
        if parsed.query or parsed.fragment:
            raise ConnectorError(ConnectorErrorCode.INVALID_URI, "SQLite URI query/fragment is unsupported", {})
        path = unquote(parsed.path)
        if path == "/:memory:":
            path = ":memory:"
        if not path:
            raise ConnectorError(ConnectorErrorCode.INVALID_URI, "SQLite URI requires a database path", {})
        return ResolvedTable(uri=uri, mode=TableMode.BASE, resource=ResolvedSQLite(uri, path))

    def _read(self, request: SQLiteTableReadRequest) -> tuple[pa.Table, str, SQLiteReadOptions]:
        resolved = self.resolve(request.uri, ResolveContext(resource_limits=request.resource_limits))
        resource: ResolvedSQLite = resolved.resource
        active = self._active_transaction(request.uri)
        connection = active._connection if active is not None else None
        owns_connection = connection is None
        try:
            if connection is None:
                connection = self._connection_factory(resource.path)
            cursor = connection.cursor()
            options = request.options
            statement = options.query or f'SELECT * FROM "{options.table}"'
            cursor.execute(statement, options.parameters)
            description = cursor.description or ()
            rows: list[tuple[Any, ...]] = []
            while request.resource_limits.max_rows is None or len(rows) < request.resource_limits.max_rows:
                batch = cursor.fetchmany(min(1000, request.resource_limits.max_rows - len(rows)) if request.resource_limits.max_rows else 1000)
                if not batch:
                    break
                rows.extend(tuple(row) for row in batch)
            table = _rows_to_arrow(description, rows)
            revision = "query:" + sha256(statement.encode("utf-8")).hexdigest()
            return table, revision, options
        except ConnectorError:
            raise
        except Exception as exc:
            raise ConnectorError(ConnectorErrorCode.EXECUTION_FAILED, "SQLite read failed", {"reason": str(exc)}) from None
        finally:
            if owns_connection and connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    def _receipt(self, request: SQLiteTableReadRequest, table: pa.Table, revision: str, options: SQLiteReadOptions, capability) -> NeutralReceipt:
        schema = arrow_schema_fingerprint(table.schema)
        content = arrow_content_fingerprint(table)
        operation = operation_identity(connector=CONNECTOR_IDENTITY, capability=TABLE_READ_ARROW_CAPABILITY, uri=request.uri, source_revision=revision, schema_fingerprint=schema, content_fingerprint=content, parameters={"table": options.table, "query": options.query, "key_fields": options.key_fields, "record_id_field": options.record_id_field, "max_rows": request.resource_limits.max_rows})
        return NeutralReceipt(connector=CONNECTOR_IDENTITY, capability=capability, operation_id=operation, safe_uri=request.uri, mode=TableMode.BASE, source_revision=revision, schema_fingerprint=schema, content_fingerprint=content, coordinate_convention=BaseConvention(record_id_field=options.record_id_field, key_fields=options.key_fields, ordinal_snapshot_id=revision), row_count=table.num_rows, batch_count=1)

    def read_arrow(self, request: SQLiteTableReadRequest) -> ArrowReadResult:
        table, revision, options = self._read(request)
        return ArrowReadResult(table=table, receipt=self._receipt(request, table, revision, options, TABLE_READ_ARROW_CAPABILITY))

    def read_polars(self, request: SQLiteTableReadRequest) -> PolarsReadResult:
        table, revision, options = self._read(request)
        return PolarsReadResult(frame=pl.from_arrow(table), receipt=self._receipt(request, table, revision, options, TABLE_READ_POLARS_CAPABILITY))

    def inspect(self, request: InspectRequest) -> TableInspection:
        read = SQLiteTableReadRequest(request.uri)
        table, revision, options = self._read(read)
        return TableInspection(safe_uri=request.uri, mode=TableMode.BASE, columns=tuple(table.column_names), schema_fingerprint=arrow_schema_fingerprint(table.schema), row_count=table.num_rows, coordinate_convention=BaseConvention(record_id_field=options.record_id_field, key_fields=options.key_fields, ordinal_snapshot_id=revision), facts={"query": options.query, "table": options.table})

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        resolved = self.resolve(request.uri, ResolveContext(resource_limits=request.resource_limits))
        active = self._active_transaction(request.uri)
        if active is not None:
            return self._execute_on(request, active._connection, commit=False)
        connection = self._connection_factory(resolved.resource.path)
        return self._execute_on(request, connection, commit=True)

    def _execute_on(
        self,
        request: ExecutionRequest,
        connection: Any,
        *,
        commit: bool,
    ) -> ExecutionResult:
        try:
            cursor = connection.execute(request.statement, request.parameters)
            if commit:
                connection.commit()
            affected = cursor.rowcount if cursor.rowcount >= 0 else None
            return ExecutionResult(self._execution_id(request), "completed", affected)
        except ConnectorError:
            raise
        except Exception as exc:
            raise ConnectorError(ConnectorErrorCode.EXECUTION_FAILED, "SQLite statement failed", {"reason": str(exc)}) from None
        finally:
            if commit:
                try:
                    connection.close()
                except Exception:
                    pass

    def write(self, request: TableWriteRequest) -> TableWriteResult:
        if request.if_exists not in {"error", "append", "replace"}:
            raise ConnectorError(ConnectorErrorCode.INVALID_URI, "if_exists must be error, append, or replace", {})
        if not request.frame.columns:
            raise ConnectorError(ConnectorErrorCode.EXECUTION_FAILED, "cannot write a frame without columns", {})
        table_name = request.table
        if table_name is None:
            raise ConnectorError(ConnectorErrorCode.INVALID_URI, "SQLite table writes require an explicit table", {})
        if not _IDENTIFIER.fullmatch(table_name):
            raise ConnectorError(ConnectorErrorCode.INVALID_URI, "SQLite table writes require a simple table URI path", {"table": table_name})
        resolved = self.resolve(request.uri, ResolveContext())
        active = self._active_transaction(request.uri)
        if active is not None:
            return self._write_on(request, active._connection, commit=False)
        connection = self._connection_factory(resolved.resource.path)
        return self._write_on(request, connection, commit=True)

    def _write_on(
        self,
        request: TableWriteRequest,
        connection: Any,
        *,
        commit: bool,
    ) -> TableWriteResult:
        table_name = request.table
        quoted_table = self._quote(table_name)
        columns = tuple(request.frame.columns)
        quoted_columns = ", ".join(self._quote(column) for column in columns)
        definitions = ", ".join(
            f"{self._quote(column)} {self._column_type(dtype)}"
            for column, dtype in request.frame.schema.items()
        )
        placeholders = ", ".join("?" for _ in columns)
        try:
            if request.if_exists == "replace":
                connection.execute(f"DROP TABLE IF EXISTS {quoted_table}")
            if request.if_exists in {"append", "replace"}:
                connection.execute(f"CREATE TABLE IF NOT EXISTS {quoted_table} ({definitions})")
            else:
                connection.execute(f"CREATE TABLE {quoted_table} ({definitions})")
            rows = [tuple(self._value(value) for value in row) for row in request.frame.rows()]
            if rows:
                connection.executemany(
                    f"INSERT INTO {quoted_table} ({quoted_columns}) VALUES ({placeholders})",
                    rows,
                )
            if commit:
                connection.commit()
            arrow = request.frame.to_arrow()
            schema = arrow_schema_fingerprint(arrow.schema)
            content = arrow_content_fingerprint(arrow)
            revision = "write:" + content
            operation = operation_identity(
                connector=CONNECTOR_IDENTITY,
                capability=TABLE_WRITE_CAPABILITY,
                uri=request.uri,
                source_revision=revision,
                schema_fingerprint=schema,
                content_fingerprint=content,
                parameters={"table": table_name, "if_exists": request.if_exists},
            )
            receipt = NeutralReceipt(
                CONNECTOR_IDENTITY,
                TABLE_WRITE_CAPABILITY,
                operation,
                request.uri,
                TableMode.BASE,
                revision,
                schema,
                content,
                BaseConvention(ordinal_snapshot_id=revision),
                request.frame.height,
                1,
            )
            return TableWriteResult(receipt, request.frame.height)
        except ConnectorError:
            raise
        except Exception as exc:
            raise ConnectorError(ConnectorErrorCode.EXECUTION_FAILED, "SQLite table write failed", {"reason": str(exc)}) from None
        finally:
            if commit:
                try:
                    connection.close()
                except Exception:
                    pass

    def begin(self, uri: TableURI | None = None) -> SQLiteTransaction:
        if uri is None:
            raise ConnectorError(ConnectorErrorCode.INVALID_URI, "SQLite begin requires a database URI", {})
        return self.begin_for(uri)

    def begin_for(self, uri: TableURI) -> SQLiteTransaction:
        if self._transaction_context.get() is not None:
            raise ConnectorError(ConnectorErrorCode.CONFLICT, "SQLite transaction is already active", {})
        resolved = self.resolve(uri, ResolveContext())
        transaction = SQLiteTransaction(
            self,
            uri,
            self._connection_factory(resolved.resource.path),
        )
        self._transaction_context.set(transaction)
        return transaction

    def commit(self) -> None:
        transaction = self._transaction_context.get()
        if transaction is None:
            raise ConnectorError(ConnectorErrorCode.CONFLICT, "SQLite transaction is not active", {})
        transaction.commit()

    def abort(self) -> None:
        transaction = self._transaction_context.get()
        if transaction is None:
            raise ConnectorError(ConnectorErrorCode.CONFLICT, "SQLite transaction is not active", {})
        transaction.abort()

    def _active_transaction(self, uri: TableURI) -> SQLiteTransaction | None:
        transaction = self._transaction_context.get()
        if transaction is not None:
            transaction._ensure_open(uri)
        return transaction

    def _clear_transaction(self, transaction: SQLiteTransaction) -> None:
        if self._transaction_context.get() is transaction:
            self._transaction_context.set(None)
