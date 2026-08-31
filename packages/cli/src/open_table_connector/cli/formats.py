"""Local CSV, JSON, JSONL, and Markdown-table codecs for the CLI."""

from __future__ import annotations

import csv
import io
import json
import math
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Mapping, Sequence, TextIO
from urllib.parse import parse_qsl, unquote, urlsplit

import pyarrow as pa

from open_table_connector.contract import ConnectorError, ConnectorErrorCode, ResourceLimits
from open_table_connector.local_files import (
    encode_json_table,
    encode_jsonl_table,
    parse_json_table,
    parse_jsonl_table,
    read_excel_arrow,
    read_markdown_arrow,
    write_excel,
    write_markdown_table as write_markdown_table_codec,
)

from .model import Endpoint, FormatName


_MARKDOWN_SUFFIXES = {".table", ".md", ".markdown"}
_LOCAL_FORMAT_SCHEMES = {
    "csv": FormatName.CSV,
    "excel": FormatName.EXCEL,
    "json": FormatName.JSON,
    "jsonl": FormatName.JSONL,
    "md": FormatName.TABLE,
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
        return parse_json_table(text, source=_endpoint_path(source) or "stdin")
    if format_name is FormatName.JSONL:
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
            text_stream.write(encode_json_table(table))
            return
        if format_name is FormatName.JSONL:
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


__all__ = ["infer_format", "read_local", "write_local", "write_markdown_table"]
