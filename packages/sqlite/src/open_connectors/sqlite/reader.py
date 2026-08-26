"""SQLite Base-mode Connector using the Python DB-API."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import re
import sqlite3
from typing import Any, Callable
from urllib.parse import unquote, urlsplit

import polars as pl
import pyarrow as pa

from open_connectors.contract import ArrowReadResult, ArrowTableReader, BaseConvention, ConnectorError, ConnectorErrorCode, InspectRequest, NeutralReceipt, PolarsReadResult, PolarsTableReader, ResourceLimits, ResolveContext, ResolvedTable, TableInspection, TableInspector, TableMode, TableReadRequest, TableURI, URIResolver
from open_connectors.contract.fingerprints import arrow_content_fingerprint, arrow_schema_fingerprint, operation_identity

from .identity import CONNECTOR_IDENTITY, TABLE_INSPECT_CAPABILITY, TABLE_READ_ARROW_CAPABILITY, TABLE_READ_POLARS_CAPABILITY

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


def _rows_to_arrow(description: Any, rows: list[tuple[Any, ...]]) -> pa.Table:
    names = [str(item[0]) for item in description]
    return pa.Table.from_arrays([pa.array([row[index] for row in rows]) for index in range(len(names))], names=names)


class SQLiteConnector(URIResolver, TableInspector, ArrowTableReader, PolarsTableReader):
    identity = CONNECTOR_IDENTITY

    def __init__(self, connection_factory: Callable[[str], Any] | None = None) -> None:
        self._connection_factory = connection_factory or sqlite3.connect

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
        try:
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
