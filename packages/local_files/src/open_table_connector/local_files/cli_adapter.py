"""Local CSV, JSON, JSONL, and Markdown-table codecs for the CLI."""

from __future__ import annotations

import csv
import io
import json
import math
import sys
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TextIO
from urllib.parse import parse_qsl, unquote, urlsplit

import pyarrow as pa
from open_table_connector.contract import (
    CAPABILITY_TABLE_READ_ARROW,
    CAPABILITY_TABLE_WRITE,
    PROVIDER_CSV,
    PROVIDER_EXCEL,
    PROVIDER_JSON,
    PROVIDER_JSONL,
    PROVIDER_LOCAL_FILES,
    SCHEME_FILE,
    SCHEME_MD,
    SCHEME_XLSX,
    AdapterEndpoint,
    AdapterFormat,
    AdapterOptions,
    ArrowReadResult,
    BaseConvention,
    CapabilityIdentity,
    ConnectorError,
    ConnectorErrorCode,
    ConnectorIdentity,
    InspectRequest,
    NeutralReceipt,
    PluginDescriptor,
    ResourceLimits,
    TableInspection,
    TableMode,
    TableURI,
    TableWriteResult,
)
from open_table_connector.contract.fingerprints import (
    arrow_content_fingerprint,
    arrow_schema_fingerprint,
    operation_identity,
)

from .csv_connector import CsvConnector, CsvReadOptions, CsvTableReadRequest
from .excel_connector import ExcelConnector, ExcelReadOptions, ExcelTableReadRequest
from .local_files_connector import (
    LocalFilesConnector,
    LocalReadOptions,
    LocalTableReadRequest,
)
from .markdown_connector import MarkdownConnector, MarkdownReadOptions, MarkdownTableReadRequest

Endpoint = AdapterEndpoint
FormatName = AdapterFormat

_MARKDOWN_SUFFIXES = {".table", ".md", ".markdown"}
_LOCAL_FORMAT_SCHEMES = {
    PROVIDER_CSV: FormatName.CSV,
    PROVIDER_EXCEL: FormatName.EXCEL,
    PROVIDER_JSON: FormatName.JSON,
    PROVIDER_JSONL: FormatName.JSONL,
    SCHEME_MD: FormatName.TABLE,
}


def infer_format(endpoint: Endpoint, explicit: FormatName) -> FormatName:
    if explicit is not FormatName.AUTO:
        return explicit
    if endpoint.uri is not None and endpoint.uri.scheme in _LOCAL_FORMAT_SCHEMES:
        return _LOCAL_FORMAT_SCHEMES[endpoint.uri.scheme]
    if endpoint.path is None and endpoint.uri is None:
        return explicit
    suffix = endpoint.path.suffix.casefold()
    if suffix == ".csv":
        return FormatName.CSV
    if suffix == ".xlsx":
        return FormatName.EXCEL
    if suffix == ".json":
        return FormatName.JSON
    if suffix in {".jsonl", ".ndjson"}:
        return FormatName.JSONL
    if suffix in _MARKDOWN_SUFFIXES:
        return FormatName.TABLE
    return explicit


def read_local(source: Endpoint, format_name: FormatName, stream: TextIO | None = None) -> pa.Table:
    if format_name is FormatName.EXCEL:
        from open_table_connector.local_files import read_excel_arrow

        if source.path is None:
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "Excel local input requires a filesystem path",
                {"endpoint": source.raw},
            )
        table, _, _ = read_excel_arrow(
            source.path,
            sheet=None,
            header_row=1,
            limits=ResourceLimits(),
        )
        return table
    text = _read_text(source, stream)
    if format_name is FormatName.CSV:
        return _read_csv(text, source)
    if format_name is FormatName.JSON:
        from open_table_connector.local_files import parse_json_table

        return parse_json_table(text, source=_endpoint_path(source) or "stdin")
    if format_name is FormatName.JSONL:
        from open_table_connector.local_files import parse_jsonl_table

        return parse_jsonl_table(text, source=_endpoint_path(source) or "stdin")
    if format_name is FormatName.TABLE:
        return _read_markdown_table(text, source)
    raise ConnectorError(
        ConnectorErrorCode.EXECUTION_FAILED,
        "unsupported local input format",
        {"endpoint": source.raw, "format": format_name.value},
    )


def write_local(
    table: pa.Table,
    destination: Endpoint,
    format_name: FormatName,
    stream: TextIO | None = None,
    *,
    sheet: str | None = None,
) -> None:
    if format_name is FormatName.EXCEL:
        from open_table_connector.local_files import write_excel

        if destination.is_stdio:
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "Excel local output requires a filesystem path",
                {"endpoint": destination.raw},
            )
        write_excel(table, _local_path(destination), sheet)
        return
    text_stream, should_close = _open_text_sink(destination, stream)
    try:
        if format_name is FormatName.CSV:
            _write_csv(table, text_stream)
            return
        if format_name is FormatName.JSON:
            from open_table_connector.local_files import encode_json_table

            text_stream.write(encode_json_table(table))
            return
        if format_name is FormatName.JSONL:
            from open_table_connector.local_files import encode_jsonl_table

            text_stream.write(encode_jsonl_table(table))
            return
        if format_name is FormatName.TABLE:
            _write_markdown_table(table, text_stream)
            return
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "unsupported local output format",
            {"endpoint": destination.raw, "format": format_name.value},
        )
    finally:
        if should_close:
            text_stream.close()


def _read_text(endpoint: Endpoint, stream: TextIO | None) -> str:
    if endpoint.is_stdio:
        handle = stream if stream is not None else sys.stdin
        return handle.read()
    if endpoint.path is None and endpoint.uri is None:
        raise ConnectorError(
            ConnectorErrorCode.INVALID_URI,
            "local endpoints require a filesystem path or stdin",
            {"endpoint": endpoint.raw},
        )
    path = endpoint.path if endpoint.path is not None else _local_path(endpoint)
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "local input could not be read",
            {"path": str(path), "reason": exc.strerror or str(exc)},
        ) from None


def _open_text_sink(endpoint: Endpoint, stream: TextIO | None) -> tuple[TextIO, bool]:
    if endpoint.is_stdio:
        return (stream if stream is not None else sys.stdout, False)
    path = _local_path(endpoint)
    try:
        return path.open("w", encoding="utf-8", newline=""), True
    except OSError as exc:
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "local output could not be opened",
            {"path": str(path), "reason": exc.strerror or str(exc)},
        ) from None


def _structured_uri_component_keys(component: str) -> list[str]:
    pairs = [item for item in component.split("&") if "=" in item]
    if not pairs:
        return []
    return sorted({key for key, _ in parse_qsl("&".join(pairs), keep_blank_values=True)})


def _local_path(endpoint: Endpoint) -> Path:
    if endpoint.path is not None:
        return endpoint.path
    if endpoint.uri is None or endpoint.uri.scheme not in _LOCAL_FORMAT_SCHEMES:
        raise ConnectorError(
            ConnectorErrorCode.INVALID_URI,
            "local endpoints require a filesystem path or stdout",
            {"endpoint": endpoint.raw},
        )
    parsed = urlsplit(endpoint.uri.value)
    if parsed.netloc.casefold() not in ("", "localhost"):
        raise ConnectorError(
            ConnectorErrorCode.INVALID_URI,
            "local output host is unsupported",
            {"host": parsed.netloc},
        )
    if parsed.query:
        raise ConnectorError(
            ConnectorErrorCode.INVALID_URI,
            "local output query parameters are unsupported",
            {"query_keys": _structured_uri_component_keys(parsed.query)},
        )
    if parsed.fragment:
        raise ConnectorError(
            ConnectorErrorCode.INVALID_URI,
            "local output URI fragments are unsupported",
            {"fragment_keys": _structured_uri_component_keys(parsed.fragment)},
        )
    path = Path(unquote(parsed.path))
    if not path.is_absolute():
        raise ConnectorError(
            ConnectorErrorCode.INVALID_URI,
            "local output URI must contain an absolute path",
            {"endpoint": endpoint.raw},
        )
    return path


def _read_csv(text: str, source: Endpoint) -> pa.Table:
    if not text.strip():
        return pa.table({})
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""))
        if reader.fieldnames is None:
            return pa.table({})
        rows: list[dict[str, object | None]] = []
        for row_number, row in enumerate(reader, start=2):
            if row.get(None):
                raise ConnectorError(
                    ConnectorErrorCode.EXECUTION_FAILED,
                    "CSV row has too many columns",
                    {"path": _endpoint_path(source), "line": row_number},
                )
            rows.append({name: _normalize_table_cell(row.get(name)) for name in reader.fieldnames})
        return _rows_to_table(rows, reader.fieldnames)
    except csv.Error as exc:
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "CSV input is malformed",
            {"path": _endpoint_path(source), "reason": str(exc)},
        ) from None


def _read_markdown_table(text: str, source: Endpoint) -> pa.Table:
    from open_table_connector.local_files import read_markdown_arrow

    return read_markdown_arrow(text, source=_endpoint_path(source))


def _rows_to_table(rows: list[dict[str, object | None]], columns: Iterable[str]) -> pa.Table:
    ordered_columns = list(columns)
    data = {
        name: [row.get(name) for row in rows]
        for name in ordered_columns
    }
    return pa.table(data)


def _write_csv(table: pa.Table, stream: TextIO) -> None:
    writer = csv.writer(stream, lineterminator="\n")
    rows = _table_rows(table)
    writer.writerow(table.column_names)
    for row in rows:
        writer.writerow([_stringify_cell(row.get(name)) for name in table.column_names])


def _write_markdown_table(table: pa.Table, stream: TextIO) -> None:
    rows = _table_rows(table)
    names = list(table.column_names)
    string_rows = [[_stringify_cell(row.get(name)) for name in names] for row in rows]
    write_markdown_table(names, string_rows, stream)


def write_markdown_table(
    headers: Sequence[str], rows: Iterable[Sequence[str]], stream: TextIO
) -> None:
    """Write an aligned Markdown table with escaped single-line cells."""
    from open_table_connector.local_files import write_markdown_table as write_markdown_table_codec

    write_markdown_table_codec(headers, rows, stream)


def _table_rows(table: pa.Table) -> list[dict[str, object | None]]:
    rows = table.to_pylist()
    return [{name: _normalize_cell(row.get(name)) for name in table.column_names} for row in rows]


def _stringify_cell(value: object | None) -> str:
    normalized = _normalize_cell(value)
    return "" if normalized is None else str(normalized)


def _normalize_cell(value: object | None) -> object | None:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return value


def json_safe_value(value: object | None) -> object | None:
    """Convert Arrow-derived values to JSON-compatible Python values."""
    if isinstance(value, pa.Scalar):
        return json_safe_value(value.as_py())
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Decimal):
        return format(value, "f") if value.is_finite() else None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): json_safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe_value(item) for item in value]
    return str(value)


def _normalize_table_cell(value: object | None) -> object | None:
    if value == "":
        return None
    return _normalize_cell(value)


def _endpoint_path(endpoint: Endpoint) -> str | None:
    return None if endpoint.path is None else str(endpoint.path)


def _connector_uri(endpoint: Endpoint) -> TableURI:
    if endpoint.uri is not None:
        return endpoint.uri
    if endpoint.path is not None:
        return TableURI(endpoint.path.resolve().as_uri())
    raise ConnectorError(
        ConnectorErrorCode.INVALID_URI,
        "local connector endpoints require a URI or filesystem path",
        {"endpoint": endpoint.raw},
    )


def _local_uri(endpoint: Endpoint) -> TableURI:
    if endpoint.path is not None:
        return TableURI(endpoint.path.resolve().as_uri())
    return TableURI("stdio://stdin")


def _limited_table(table: pa.Table, options: AdapterOptions) -> pa.Table:
    return table if options.limit is None else table.slice(0, options.limit)


def _limits(options: AdapterOptions) -> ResourceLimits:
    timeout = None if options.timeout is None else math.ceil(options.timeout)
    return ResourceLimits(max_rows=options.limit, timeout_seconds=timeout)


def _frame(table: pa.Table):
    import polars as pl

    return pl.from_arrow(table)


_LOCAL_READ_CAPABILITY = CapabilityIdentity(CAPABILITY_TABLE_READ_ARROW, "1.0")
_LOCAL_WRITE_CAPABILITY = CapabilityIdentity(CAPABILITY_TABLE_WRITE, "1.0")


def _local_receipt(
    endpoint: Endpoint,
    table: pa.Table,
    capability: CapabilityIdentity,
    *,
    connector: ConnectorIdentity,
) -> NeutralReceipt:
    uri = _connector_uri(endpoint) if endpoint.uri is not None else _local_uri(endpoint)
    schema = arrow_schema_fingerprint(table.schema)
    content = arrow_content_fingerprint(table)
    source_revision = "sha256:" + content
    operation = operation_identity(
        connector=connector,
        capability=capability,
        uri=uri,
        source_revision=source_revision,
        schema_fingerprint=schema,
        content_fingerprint=content,
    )
    return NeutralReceipt(
        connector,
        capability,
        operation,
        uri,
        TableMode.BASE,
        source_revision,
        schema,
        content,
        BaseConvention(ordinal_snapshot_id=source_revision),
        table.num_rows,
        1,
    )


class _LocalCliAdapter:
    local = True

    def __init__(self, connector: object, context) -> None:
        self.connector = connector
        self._validate_context(context)

    @staticmethod
    def _validate_context(context) -> None:
        if context.config.environment:
            raise ValueError("local adapter environment must be empty")
        if context.config.options:
            raise ValueError("local adapter options must be empty")
        if context.credentials:
            raise ValueError("local adapter credentials must be empty")


class CsvCliAdapter(_LocalCliAdapter):
    identity = ConnectorIdentity(PROVIDER_CSV, "0.1.0", "1.0")
    schemes = (PROVIDER_CSV,)
    hosts: tuple[str, ...] = ()
    modes = (TableMode.SHEET,)
    capabilities = (
        CapabilityIdentity("uri.resolve", "1.0"),
        CapabilityIdentity("table.inspect", "1.0"),
        _LOCAL_READ_CAPABILITY,
        CapabilityIdentity("table.read.polars", "1.0"),
        _LOCAL_WRITE_CAPABILITY,
    )

    def _request(self, endpoint: Endpoint, options: AdapterOptions):
        return CsvTableReadRequest(
            _connector_uri(endpoint),
            resource_limits=_limits(options),
            options=CsvReadOptions(),
        )

    def read(self, endpoint: Endpoint, options: AdapterOptions) -> ArrowReadResult:
        return self.connector.read_arrow(self._request(endpoint, options))

    def inspect(self, endpoint: Endpoint, options: AdapterOptions) -> TableInspection:
        return self.connector.inspect(InspectRequest(_connector_uri(endpoint), _limits(options)))

    def write(
        self, endpoint: Endpoint, table: pa.Table, options: AdapterOptions
    ) -> TableWriteResult:
        write_local(table, endpoint, FormatName.CSV)
        return TableWriteResult(
            _local_receipt(endpoint, table, _LOCAL_WRITE_CAPABILITY, connector=self.identity),
            table.num_rows,
        )


class ExcelCliAdapter(CsvCliAdapter):
    identity = ConnectorIdentity(PROVIDER_EXCEL, "0.1.0", "1.0")
    schemes = (PROVIDER_EXCEL, SCHEME_XLSX)

    def _request(self, endpoint: Endpoint, options: AdapterOptions):
        return ExcelTableReadRequest(
            _connector_uri(endpoint),
            resource_limits=_limits(options),
            options=ExcelReadOptions(sheet=options.sheet),
        )

    def write(
        self, endpoint: Endpoint, table: pa.Table, options: AdapterOptions
    ) -> TableWriteResult:
        write_local(table, endpoint, FormatName.EXCEL, sheet=options.sheet)
        return TableWriteResult(
            _local_receipt(endpoint, table, _LOCAL_WRITE_CAPABILITY, connector=self.identity),
            table.num_rows,
        )


class MarkdownCliAdapter(CsvCliAdapter):
    identity = ConnectorIdentity(SCHEME_MD, "0.1.0", "1.0")
    schemes = (SCHEME_MD,)

    def _request(self, endpoint: Endpoint, options: AdapterOptions):
        return MarkdownTableReadRequest(
            _connector_uri(endpoint),
            resource_limits=_limits(options),
            options=MarkdownReadOptions(),
        )

    def write(
        self, endpoint: Endpoint, table: pa.Table, options: AdapterOptions
    ) -> TableWriteResult:
        write_local(table, endpoint, FormatName.TABLE)
        return TableWriteResult(
            _local_receipt(endpoint, table, _LOCAL_WRITE_CAPABILITY, connector=self.identity),
            table.num_rows,
        )


class LocalFilesCliAdapter(_LocalCliAdapter):
    identity = ConnectorIdentity(PROVIDER_LOCAL_FILES, "0.1.0", "1.0")
    schemes = (SCHEME_FILE, PROVIDER_JSON, PROVIDER_JSONL)
    hosts: tuple[str, ...] = ()
    modes = (TableMode.SHEET,)
    capabilities = (
        CapabilityIdentity("uri.resolve", "1.0"),
        CapabilityIdentity("table.inspect", "1.0"),
        _LOCAL_READ_CAPABILITY,
        CapabilityIdentity("table.read.polars", "1.0"),
    )

    def _format(
        self, endpoint: Endpoint, options: AdapterOptions, *, output: bool = False
    ) -> FormatName:
        return infer_format(endpoint, options.output_format if output else options.from_format)

    def _read_request(self, endpoint: Endpoint, options: AdapterOptions):
        return LocalTableReadRequest(
            _connector_uri(endpoint),
            resource_limits=_limits(options),
            options=LocalReadOptions(sheet=options.sheet),
        )

    def _uses_legacy_reader(self, endpoint: Endpoint, options: AdapterOptions) -> bool:
        if endpoint.is_stdio or options.from_format is not FormatName.AUTO:
            return True
        return self._format(endpoint, options) in {FormatName.JSON, FormatName.JSONL}

    def read(self, endpoint: Endpoint, options: AdapterOptions) -> ArrowReadResult:
        if not self._uses_legacy_reader(endpoint, options):
            return self.connector.read_arrow(self._read_request(endpoint, options))
        table = _limited_table(read_local(endpoint, self._format(endpoint, options)), options)
        return ArrowReadResult(
            table,
            _local_receipt(
                endpoint, table, _LOCAL_READ_CAPABILITY, connector=self.identity
            ),
        )

    def inspect(self, endpoint: Endpoint, options: AdapterOptions) -> TableInspection:
        if not self._uses_legacy_reader(endpoint, options):
            return self.connector.inspect(self._read_request(endpoint, options))
        result = self.read(endpoint, options)
        return TableInspection(
            _local_uri(endpoint),
            TableMode.BASE,
            tuple(result.table.column_names),
            result.receipt.schema_fingerprint,
            result.table.num_rows,
            BaseConvention(ordinal_snapshot_id=result.receipt.source_revision),
            {"provider": PROVIDER_LOCAL_FILES},
        )

    def write(
        self, endpoint: Endpoint, table: pa.Table, options: AdapterOptions
    ) -> TableWriteResult:
        write_local(
            table,
            endpoint,
            self._format(endpoint, options, output=True),
            sheet=options.sheet,
        )
        return TableWriteResult(
            _local_receipt(endpoint, table, _LOCAL_WRITE_CAPABILITY, connector=self.identity),
            table.num_rows,
        )


def _context_factory(adapter_type, connector_type, context):
    return adapter_type(connector_type(), context)


def csv_cli_plugin() -> PluginDescriptor:
    return PluginDescriptor(
        PROVIDER_CSV,
        CsvCliAdapter.identity,
        CsvCliAdapter.schemes,
        lambda context: _context_factory(CsvCliAdapter, CsvConnector, context),
        capabilities=CsvCliAdapter.capabilities,
        modes=CsvCliAdapter.modes,
        local=True,
        handles_paths=False,
    )


def excel_cli_plugin() -> PluginDescriptor:
    return PluginDescriptor(
        PROVIDER_EXCEL,
        ExcelCliAdapter.identity,
        ExcelCliAdapter.schemes,
        lambda context: _context_factory(ExcelCliAdapter, ExcelConnector, context),
        capabilities=ExcelCliAdapter.capabilities,
        modes=ExcelCliAdapter.modes,
        local=True,
        handles_paths=False,
    )


def markdown_cli_plugin() -> PluginDescriptor:
    return PluginDescriptor(
        SCHEME_MD,
        MarkdownCliAdapter.identity,
        MarkdownCliAdapter.schemes,
        lambda context: _context_factory(MarkdownCliAdapter, MarkdownConnector, context),
        capabilities=MarkdownCliAdapter.capabilities,
        modes=MarkdownCliAdapter.modes,
        local=True,
        handles_paths=False,
    )


def local_files_cli_plugin() -> PluginDescriptor:
    return PluginDescriptor(
        PROVIDER_LOCAL_FILES,
        LocalFilesCliAdapter.identity,
        LocalFilesCliAdapter.schemes,
        lambda context: _context_factory(LocalFilesCliAdapter, LocalFilesConnector, context),
        capabilities=LocalFilesCliAdapter.capabilities,
        modes=LocalFilesCliAdapter.modes,
        local=True,
        handles_paths=True,
    )


__all__ = [
    "CsvCliAdapter",
    "ExcelCliAdapter",
    "LocalFilesCliAdapter",
    "MarkdownCliAdapter",
    "csv_cli_plugin",
    "excel_cli_plugin",
    "infer_format",
    "local_files_cli_plugin",
    "markdown_cli_plugin",
    "read_local",
    "write_local",
    "write_markdown_table",
]
