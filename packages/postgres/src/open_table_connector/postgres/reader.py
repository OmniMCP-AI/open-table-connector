"""PostgreSQL Base-mode Connector with DB-API injection for deterministic tests."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from contextvars import ContextVar
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any
from urllib.parse import urlsplit

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
    ResolveContext,
    ResolvedTable,
    SqlExecutor,
    TableInspection,
    TableInspector,
    TableMode,
    TableReadRequest,
    TableURI,
    TableWriter,
    TableWriteRequest,
    TableWriteResult,
    TransactionalStore,
    URIResolver,
)
from open_table_connector.contract.fingerprints import (
    arrow_content_fingerprint,
    arrow_schema_fingerprint,
    operation_identity,
)

from .identity import (
    CONNECTOR_IDENTITY,
    TABLE_READ_ARROW_CAPABILITY,
    TABLE_READ_POLARS_CAPABILITY,
    TABLE_WRITE_CAPABILITY,
)

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*)?$")


@dataclass(frozen=True)
class PostgresReadOptions:
    table: str | None = None
    query: str | None = None
    parameters: tuple[Any, ...] = ()
    key_fields: tuple[str, ...] = ()
    record_id_field: str | None = None

    def __post_init__(self) -> None:
        if (self.table is None) == (self.query is None):
            raise ValueError("PostgresReadOptions requires exactly one table or query")
        if self.table is not None and not _IDENTIFIER.fullmatch(self.table):
            raise ValueError("table must be a simple qualified identifier")
        if self.query is not None and not self.query.lstrip().casefold().startswith(("select", "with")):
            raise ValueError("Postgres query reads must be SELECT or WITH statements")
        object.__setattr__(self, "parameters", tuple(self.parameters))
        object.__setattr__(self, "key_fields", tuple(self.key_fields))


@dataclass(frozen=True)
class PostgresTableReadRequest(TableReadRequest):
    options: PostgresReadOptions = field(default_factory=lambda: PostgresReadOptions(table="public.table"))
    credentials: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "credentials", dict(self.credentials))


@dataclass(frozen=True)
class ResolvedPostgres:
    uri: TableURI
    connect_kwargs: dict[str, Any]


class PostgresTransaction:
    def __init__(self, connector: PostgresConnector, uri: TableURI, connection: Any) -> None:
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
            raise ConnectorError(ConnectorErrorCode.CONFLICT, "PostgreSQL transaction is closed", {})
        try:
            self._connection.commit() if commit else self._connection.rollback()
        finally:
            self._connection.close()
            self._closed = True
            self._connector._clear_transaction(self)

    def _ensure_open(self, uri: TableURI) -> None:
        if self._closed:
            raise ConnectorError(ConnectorErrorCode.CONFLICT, "PostgreSQL transaction is closed", {})
        if uri != self.uri:
            raise ConnectorError(
                ConnectorErrorCode.CONFLICT,
                "PostgreSQL transaction cannot cross database URIs",
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


def _safe_provider_reason(
    exc: BaseException,
    connect_kwargs: Mapping[str, Any],
) -> str:
    reason = str(exc)
    password = connect_kwargs.get("password")
    if password is not None:
        secret = str(password)
        if secret:
            reason = reason.replace(secret, "[REDACTED]")
    return reason


def _close_cursor(cursor: Any | None) -> None:
    if cursor is None:
        return
    try:
        cursor.close()
    except Exception:
        pass


def _begin_read_only(connection: Any, cursor: Any | None = None) -> None:
    """Put a standalone query read in a database-enforced read-only transaction."""
    active_cursor = cursor or connection.cursor()
    try:
        active_cursor.execute("SET TRANSACTION READ ONLY")
    except TypeError:
        active_cursor.execute("SET TRANSACTION READ ONLY", ())


class PostgresConnector(
    URIResolver,
    TableInspector,
    ArrowTableReader,
    PolarsTableReader,
    SqlExecutor,
    TableWriter,
    TransactionalStore,
):
    identity = CONNECTOR_IDENTITY

    def __init__(self, connection_factory: Callable[..., Any] | None = None) -> None:
        self._connection_factory = connection_factory
        self._transaction_context: ContextVar[PostgresTransaction | None] = ContextVar(
            f"postgres_transaction_{id(self)}",
            default=None,
        )

    @staticmethod
    def _execution_id(request: ExecutionRequest) -> str:
        payload = f"{request.uri.value}\0{request.statement}".encode()
        return "exec_" + sha256(payload).hexdigest()

    @staticmethod
    def _quote(identifier: str) -> str:
        return ".".join('"' + part.replace('"', '""') + '"' for part in identifier.split("."))

    @staticmethod
    def _column_type(dtype: pl.DataType) -> str:
        if dtype == pl.Boolean:
            return "BOOLEAN"
        if dtype in (pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64):
            return "BIGINT"
        if dtype in (pl.Float32, pl.Float64):
            return "DOUBLE PRECISION"
        if dtype == pl.Binary:
            return "BYTEA"
        return "TEXT"

    def resolve(self, uri: TableURI, context: ResolveContext) -> ResolvedTable:
        if uri.scheme not in {"postgres", "postgresql"}:
            raise ConnectorError(ConnectorErrorCode.INVALID_URI, "Postgres Connector requires postgres URI", {"scheme": uri.scheme})
        parsed = urlsplit(uri.value)
        if parsed.query or parsed.fragment:
            raise ConnectorError(ConnectorErrorCode.INVALID_URI, "Postgres URI query/fragment is unsupported", {})
        credentials = context.credentials if isinstance(context.credentials, dict) else {}
        kwargs = {key: value for key, value in credentials.items() if key in {"host", "port", "dbname", "user", "password", "sslmode"}}
        if parsed.hostname:
            kwargs.setdefault("host", parsed.hostname)
        if parsed.port:
            kwargs.setdefault("port", parsed.port)
        if parsed.path.strip("/"):
            kwargs.setdefault("dbname", parsed.path.strip("/"))
        return ResolvedTable(uri=uri, mode=TableMode.BASE, resource=ResolvedPostgres(uri, kwargs))

    def _connect(self, resource: ResolvedPostgres):
        factory = self._connection_factory
        if factory is None:
            try:
                import psycopg2
            except ImportError:
                raise ConnectorError(ConnectorErrorCode.UNSUPPORTED_CAPABILITY, "PostgreSQL DB-API is not installed", {}) from None
            factory = psycopg2.connect
        try:
            return factory(**resource.connect_kwargs)
        except Exception as exc:
            raise ConnectorError(
                ConnectorErrorCode.AUTHENTICATION,
                "PostgreSQL connection failed",
                {"reason": _safe_provider_reason(exc, resource.connect_kwargs)},
            ) from None

    def _read(self, request: PostgresTableReadRequest) -> tuple[pa.Table, str, PostgresReadOptions]:
        resolved = self.resolve(request.uri, ResolveContext(resource_limits=request.resource_limits, credentials=request.credentials))
        resource: ResolvedPostgres = resolved.resource
        active = self._active_transaction(request.uri)
        options = request.options
        if options.query is not None and active is not None:
            raise ConnectorError(
                ConnectorErrorCode.CONFLICT,
                "query reads cannot run inside a writable PostgreSQL transaction",
                {},
            )
        connection = active._connection if active is not None else self._connect(resource)
        owns_connection = active is None
        cursor = None
        try:
            cursor = connection.cursor()
            if options.query is not None:
                _begin_read_only(connection, cursor)
            statement = options.query or f"SELECT * FROM {options.table}"
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
            raise ConnectorError(
                ConnectorErrorCode.EXECUTION_FAILED,
                "PostgreSQL read failed",
                {"reason": _safe_provider_reason(exc, resource.connect_kwargs)},
            ) from None
        finally:
            _close_cursor(cursor)
            if owns_connection:
                try:
                    connection.close()
                except Exception:
                    pass

    def _receipt(self, request: PostgresTableReadRequest, table: pa.Table, revision: str, options: PostgresReadOptions, capability):
        schema = arrow_schema_fingerprint(table.schema)
        content = arrow_content_fingerprint(table)
        operation = operation_identity(connector=CONNECTOR_IDENTITY, capability=TABLE_READ_ARROW_CAPABILITY, uri=request.uri, source_revision=revision, schema_fingerprint=schema, content_fingerprint=content, parameters={"table": options.table, "query": options.query, "key_fields": options.key_fields, "record_id_field": options.record_id_field, "max_rows": request.resource_limits.max_rows})
        return __import__("open_table_connector.contract", fromlist=["NeutralReceipt"]).NeutralReceipt(connector=CONNECTOR_IDENTITY, capability=capability, operation_id=operation, safe_uri=request.uri, mode=TableMode.BASE, source_revision=revision, schema_fingerprint=schema, content_fingerprint=content, coordinate_convention=BaseConvention(record_id_field=options.record_id_field, key_fields=options.key_fields, ordinal_snapshot_id=revision), row_count=table.num_rows, batch_count=1)

    def read_arrow(self, request: PostgresTableReadRequest) -> ArrowReadResult:
        table, revision, options = self._read(request)
        return ArrowReadResult(table=table, receipt=self._receipt(request, table, revision, options, TABLE_READ_ARROW_CAPABILITY))

    def read_polars(self, request: PostgresTableReadRequest) -> PolarsReadResult:
        table, revision, options = self._read(request)
        return PolarsReadResult(frame=pl.from_arrow(table), receipt=self._receipt(request, table, revision, options, TABLE_READ_POLARS_CAPABILITY))

    def inspect(self, request: InspectRequest) -> TableInspection:
        read = PostgresTableReadRequest(request.uri, resource_limits=request.resource_limits)
        table, revision, options = self._read(read)
        return TableInspection(safe_uri=request.uri, mode=TableMode.BASE, columns=tuple(table.column_names), schema_fingerprint=arrow_schema_fingerprint(table.schema), row_count=table.num_rows, coordinate_convention=BaseConvention(record_id_field=options.record_id_field, key_fields=options.key_fields, ordinal_snapshot_id=revision), facts={"query": options.query, "table": options.table})

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        resolved = self.resolve(request.uri, ResolveContext(resource_limits=request.resource_limits))
        active = self._active_transaction(request.uri)
        if active is not None:
            return self._execute_on(request, active._connection, resolved, commit=False)
        return self._execute_on(request, self._connect(resolved.resource), resolved, commit=True)

    def _execute_on(self, request, connection, resolved, *, commit: bool) -> ExecutionResult:
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute(request.statement, request.parameters)
            if commit:
                connection.commit()
            affected = cursor.rowcount if getattr(cursor, "rowcount", -1) >= 0 else None
            return ExecutionResult(self._execution_id(request), "completed", affected)
        except ConnectorError:
            raise
        except Exception as exc:
            raise ConnectorError(
                ConnectorErrorCode.EXECUTION_FAILED,
                "PostgreSQL statement failed",
                {"reason": _safe_provider_reason(exc, resolved.resource.connect_kwargs)},
            ) from None
        finally:
            _close_cursor(cursor)
            if commit:
                try:
                    connection.close()
                except Exception:
                    pass

    def write(self, request: TableWriteRequest) -> TableWriteResult:
        if request.if_exists not in {"error", "append", "replace"}:
            raise ConnectorError(ConnectorErrorCode.INVALID_URI, "if_exists must be error, append, or replace", {})
        if not request.table or not _IDENTIFIER.fullmatch(request.table):
            raise ConnectorError(ConnectorErrorCode.INVALID_URI, "PostgreSQL table writes require a simple qualified table", {"table": request.table})
        if not request.frame.columns:
            raise ConnectorError(ConnectorErrorCode.EXECUTION_FAILED, "cannot write a frame without columns", {})
        resolved = self.resolve(request.uri, ResolveContext())
        active = self._active_transaction(request.uri)
        if active is not None:
            return self._write_on(request, active._connection, resolved, commit=False)
        return self._write_on(request, self._connect(resolved.resource), resolved, commit=True)

    def _write_on(self, request, connection, resolved, *, commit: bool) -> TableWriteResult:
        cursors: list[Any] = []
        quoted_table = self._quote(request.table)
        columns = tuple(request.frame.columns)
        quoted_columns = ", ".join(self._quote(column) for column in columns)
        definitions = ", ".join(
            f'{self._quote(column)} {self._column_type(dtype)}'
            for column, dtype in request.frame.schema.items()
        )
        placeholders = ", ".join("%s" for _ in columns)
        try:
            if request.if_exists == "replace":
                cursor = connection.cursor()
                cursors.append(cursor)
                cursor.execute(f"DROP TABLE IF EXISTS {quoted_table}", ())
            if request.if_exists in {"append", "replace"}:
                cursor = connection.cursor()
                cursors.append(cursor)
                cursor.execute(
                    f"CREATE TABLE IF NOT EXISTS {quoted_table} ({definitions})",
                    (),
                )
            else:
                cursor = connection.cursor()
                cursors.append(cursor)
                cursor.execute(f"CREATE TABLE {quoted_table} ({definitions})", ())
            rows = [tuple(value for value in row) for row in request.frame.rows()]
            if rows:
                cursor = connection.cursor()
                cursors.append(cursor)
                cursor.executemany(
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
                parameters={"table": request.table, "if_exists": request.if_exists},
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
            raise ConnectorError(
                ConnectorErrorCode.EXECUTION_FAILED,
                "PostgreSQL table write failed",
                {"reason": _safe_provider_reason(exc, resolved.resource.connect_kwargs)},
            ) from None
        finally:
            for cursor in cursors:
                _close_cursor(cursor)
            if commit:
                try:
                    connection.close()
                except Exception:
                    pass

    def begin(self, uri: TableURI | None = None) -> PostgresTransaction:
        if uri is None:
            raise ConnectorError(ConnectorErrorCode.INVALID_URI, "PostgreSQL begin requires a database URI", {})
        if self._transaction_context.get() is not None:
            raise ConnectorError(ConnectorErrorCode.CONFLICT, "PostgreSQL transaction is already active", {})
        resolved = self.resolve(uri, ResolveContext())
        transaction = PostgresTransaction(self, uri, self._connect(resolved.resource))
        self._transaction_context.set(transaction)
        return transaction

    def commit(self) -> None:
        transaction = self._transaction_context.get()
        if transaction is None:
            raise ConnectorError(ConnectorErrorCode.CONFLICT, "PostgreSQL transaction is not active", {})
        transaction.commit()

    def abort(self) -> None:
        transaction = self._transaction_context.get()
        if transaction is None:
            raise ConnectorError(ConnectorErrorCode.CONFLICT, "PostgreSQL transaction is not active", {})
        transaction.abort()

    def _active_transaction(self, uri: TableURI) -> PostgresTransaction | None:
        transaction = self._transaction_context.get()
        if transaction is not None:
            transaction._ensure_open(uri)
        return transaction

    def _clear_transaction(self, transaction: PostgresTransaction) -> None:
        if self._transaction_context.get() is transaction:
            self._transaction_context.set(None)
