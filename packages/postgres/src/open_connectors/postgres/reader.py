"""PostgreSQL Base-mode Connector with DB-API injection for deterministic tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import re
from typing import Any, Callable
from urllib.parse import urlsplit

import polars as pl
import pyarrow as pa

from open_connectors.contract import (
    ArrowReadResult,
    ArrowTableReader,
    BaseConvention,
    ConnectorError,
    ConnectorErrorCode,
    InspectRequest,
    PolarsReadResult,
    PolarsTableReader,
    ResourceLimits,
    ResolveContext,
    ResolvedTable,
    TableInspection,
    TableInspector,
    TableMode,
    TableReadRequest,
    TableURI,
    URIResolver,
)
from open_connectors.contract.fingerprints import arrow_content_fingerprint, arrow_schema_fingerprint, operation_identity

from .identity import CONNECTOR_IDENTITY, TABLE_INSPECT_CAPABILITY, TABLE_READ_ARROW_CAPABILITY, TABLE_READ_POLARS_CAPABILITY

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


@dataclass(frozen=True)
class ResolvedPostgres:
    uri: TableURI
    connect_kwargs: dict[str, Any]


def _rows_to_arrow(description: Any, rows: list[tuple[Any, ...]]) -> pa.Table:
    names = [str(item[0]) for item in description]
    columns = [pa.array([row[index] for row in rows]) for index in range(len(names))]
    return pa.Table.from_arrays(columns, names=names)


class PostgresConnector(URIResolver, TableInspector, ArrowTableReader, PolarsTableReader):
    identity = CONNECTOR_IDENTITY

    def __init__(self, connection_factory: Callable[..., Any] | None = None) -> None:
        self._connection_factory = connection_factory

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
            raise ConnectorError(ConnectorErrorCode.AUTHENTICATION, "PostgreSQL connection failed", {"reason": str(exc)}) from None

    def _read(self, request: PostgresTableReadRequest) -> tuple[pa.Table, str, PostgresReadOptions]:
        resolved = self.resolve(request.uri, ResolveContext(resource_limits=request.resource_limits))
        resource: ResolvedPostgres = resolved.resource
        connection = self._connect(resource)
        try:
            cursor = connection.cursor()
            options = request.options
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
            raise ConnectorError(ConnectorErrorCode.EXECUTION_FAILED, "PostgreSQL read failed", {"reason": str(exc)}) from None
        finally:
            try:
                connection.close()
            except Exception:
                pass

    def _receipt(self, request: PostgresTableReadRequest, table: pa.Table, revision: str, options: PostgresReadOptions, capability):
        schema = arrow_schema_fingerprint(table.schema)
        content = arrow_content_fingerprint(table)
        operation = operation_identity(connector=CONNECTOR_IDENTITY, capability=TABLE_READ_ARROW_CAPABILITY, uri=request.uri, source_revision=revision, schema_fingerprint=schema, content_fingerprint=content, parameters={"table": options.table, "query": options.query, "key_fields": options.key_fields, "record_id_field": options.record_id_field, "max_rows": request.resource_limits.max_rows})
        return __import__("open_connectors.contract", fromlist=["NeutralReceipt"]).NeutralReceipt(connector=CONNECTOR_IDENTITY, capability=capability, operation_id=operation, safe_uri=request.uri, mode=TableMode.BASE, source_revision=revision, schema_fingerprint=schema, content_fingerprint=content, coordinate_convention=BaseConvention(record_id_field=options.record_id_field, key_fields=options.key_fields, ordinal_snapshot_id=revision), row_count=table.num_rows, batch_count=1)

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
