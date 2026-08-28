"""Local CSV, JSON, JSONL, and Markdown-table codecs for the CLI."""

from __future__ import annotations

import csv
import io
import json
import math
import sys
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable, Mapping, Sequence, TextIO

import pyarrow as pa

from open_table_connector.contract import ConnectorError, ConnectorErrorCode

from .model import Endpoint, FormatName


_MARKDOWN_SUFFIXES = {".table", ".md", ".markdown"}
_MARKDOWN_SEPARATOR_RE = re.compile(r":?-+:?")


def infer_format(endpoint: Endpoint, explicit: FormatName) -> FormatName:
    if explicit is not FormatName.AUTO:
        return explicit
    if endpoint.path is None:
        return explicit
    suffix = endpoint.path.suffix.casefold()
    if suffix == ".csv":
        return FormatName.CSV
    if suffix == ".json":
        return FormatName.JSON
    if suffix in {".jsonl", ".ndjson"}:
        return FormatName.JSONL
    if suffix in _MARKDOWN_SUFFIXES:
        return FormatName.TABLE
    return explicit


def read_local(source: Endpoint, format_name: FormatName, stream: TextIO | None = None) -> pa.Table:
    text = _read_text(source, stream)
    if format_name is FormatName.CSV:
        return _read_csv(text, source)
    if format_name is FormatName.JSON:
        return _read_json(text, source)
    if format_name is FormatName.JSONL:
        return _read_jsonl(text, source)
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
) -> None:
    text_stream, should_close = _open_text_sink(destination, stream)
    try:
        if format_name is FormatName.CSV:
            _write_csv(table, text_stream)
            return
        if format_name is FormatName.JSON:
            _write_json(table, text_stream)
            return
        if format_name is FormatName.JSONL:
            _write_jsonl(table, text_stream)
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
    if endpoint.path is None:
        raise ConnectorError(
            ConnectorErrorCode.INVALID_URI,
            "local endpoints require a filesystem path or stdin",
            {"endpoint": endpoint.raw},
        )
    try:
        return endpoint.path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "local input could not be read",
            {"path": str(endpoint.path), "reason": exc.strerror or str(exc)},
        ) from None


def _open_text_sink(endpoint: Endpoint, stream: TextIO | None) -> tuple[TextIO, bool]:
    if endpoint.is_stdio:
        return (stream if stream is not None else sys.stdout, False)
    if endpoint.path is None:
        raise ConnectorError(
            ConnectorErrorCode.INVALID_URI,
            "local endpoints require a filesystem path or stdout",
            {"endpoint": endpoint.raw},
        )
    try:
        return endpoint.path.open("w", encoding="utf-8", newline=""), True
    except OSError as exc:
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "local output could not be opened",
            {"path": str(endpoint.path), "reason": exc.strerror or str(exc)},
        ) from None


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


def _read_json(text: str, source: Endpoint) -> pa.Table:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "JSON input is malformed",
            {"path": _endpoint_path(source), "line": exc.lineno, "column": exc.colno},
        ) from None
    if not isinstance(payload, list):
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "JSON input must be a list of objects",
            {"path": _endpoint_path(source)},
        )
    rows = []
    columns = []
    seen: set[str] = set()
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, Mapping):
            raise ConnectorError(
                ConnectorErrorCode.EXECUTION_FAILED,
                "JSON array items must be objects",
                {"path": _endpoint_path(source), "index": index},
            )
        row: dict[str, object | None] = {}
        for key, value in item.items():
            name = str(key)
            if name not in seen:
                seen.add(name)
                columns.append(name)
            row[name] = _normalize_cell(value)
        rows.append(row)
    return _rows_to_table(rows, columns)


def _read_jsonl(text: str, source: Endpoint) -> pa.Table:
    rows = []
    columns = []
    seen: set[str] = set()
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ConnectorError(
                ConnectorErrorCode.EXECUTION_FAILED,
                "JSONL line is malformed",
                {"path": _endpoint_path(source), "line": line_number, "column": exc.colno},
            ) from None
        if not isinstance(item, Mapping):
            raise ConnectorError(
                ConnectorErrorCode.EXECUTION_FAILED,
                "JSONL rows must be objects",
                {"path": _endpoint_path(source), "line": line_number},
            )
        row: dict[str, object | None] = {}
        for key, value in item.items():
            name = str(key)
            if name not in seen:
                seen.add(name)
                columns.append(name)
            row[name] = _normalize_cell(value)
        rows.append(row)
    return _rows_to_table(rows, columns)


def _read_markdown_table(text: str, source: Endpoint) -> pa.Table:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return pa.table({})
    rows = [
        (index + 1, _split_markdown_row(line, line_number=index + 1, source=source))
        for index, line in enumerate(lines)
    ]
    _, header = rows[0]
    body_start = 1
    if len(rows) > 1 and _is_separator_row(rows[1][1]):
        separator_line, separator_row = rows[1]
        if len(separator_row) != len(header):
            raise ConnectorError(
                ConnectorErrorCode.EXECUTION_FAILED,
                "Markdown table row has an inconsistent column count",
                {"path": _endpoint_path(source), "line": separator_line},
            )
        body_start = 2
    for line_number, row in rows[body_start:]:
        if len(row) != len(header):
            raise ConnectorError(
                ConnectorErrorCode.EXECUTION_FAILED,
                "Markdown table row has an inconsistent column count",
                {"path": _endpoint_path(source), "line": line_number},
            )
    data_rows = [
        {header[index]: _normalize_table_cell(value) for index, value in enumerate(row)}
        for _, row in rows[body_start:]
    ]
    return _rows_to_table(data_rows, header)


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


def _write_json(table: pa.Table, stream: TextIO) -> None:
    json.dump(
        _json_table_rows(table),
        stream,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


def _write_jsonl(table: pa.Table, stream: TextIO) -> None:
    for row in _json_table_rows(table):
        stream.write(
            json.dumps(
                row,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        stream.write("\n")


def _write_markdown_table(table: pa.Table, stream: TextIO) -> None:
    rows = _table_rows(table)
    names = list(table.column_names)
    string_rows = [[_stringify_cell(row.get(name)) for name in names] for row in rows]
    write_markdown_table(names, string_rows, stream)


def write_markdown_table(
    headers: Sequence[str], rows: Iterable[Sequence[str]], stream: TextIO
) -> None:
    """Write an aligned Markdown table with escaped single-line cells."""
    names = [_escape_markdown_cell(str(header)) for header in headers]
    if not names:
        return
    values = [[_escape_markdown_cell(str(value)) for value in row] for row in rows]
    if any(len(row) != len(names) for row in values):
        raise ValueError("table rows must match the header width")
    widths = [
        max([len(name), 3] + [len(row[index]) for row in values])
        for index, name in enumerate(names)
    ]
    stream.write(_format_markdown_row(names, widths))
    stream.write("\n")
    stream.write(_format_markdown_separator(widths))
    stream.write("\n")
    for row in values:
        stream.write(_format_markdown_row(row, widths))
        stream.write("\n")


def _table_rows(table: pa.Table) -> list[dict[str, object | None]]:
    rows = table.to_pylist()
    return [{name: _normalize_cell(row.get(name)) for name in table.column_names} for row in rows]


def _json_table_rows(table: pa.Table) -> list[dict[str, object | None]]:
    rows = table.to_pylist()
    return [
        {name: _normalize_json_cell(row.get(name)) for name in table.column_names}
        for row in rows
    ]


def _stringify_cell(value: object | None) -> str:
    normalized = _normalize_cell(value)
    return "" if normalized is None else str(normalized)


def _normalize_cell(value: object | None) -> object | None:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return value


def _normalize_json_cell(value: object | None) -> object | None:
    normalized = json_safe_value(value)
    if not isinstance(normalized, (list, dict)):
        return normalized
    return json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


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


def _split_markdown_row(line: str, *, line_number: int, source: Endpoint) -> list[str]:
    content = line.strip()
    if content.startswith("|"):
        content = content[1:]
    if content.endswith("|"):
        backslashes = 0
        for character in reversed(content[:-1]):
            if character != "\\":
                break
            backslashes += 1
        if backslashes % 2 == 0:
            content = content[:-1]

    raw_cells: list[str] = []
    cell: list[str] = []
    index = 0
    while index < len(content):
        character = content[index]
        if character == "\\" and index + 1 < len(content):
            cell.extend((character, content[index + 1]))
            index += 2
            continue
        if character == "|":
            raw_cells.append("".join(cell))
            cell = []
        else:
            cell.append(character)
        index += 1
    raw_cells.append("".join(cell))

    cells = [_unescape_markdown_cell(cell.strip()) for cell in raw_cells]
    if len(cells) == 1 and cells[0] == "":
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "Markdown table row is empty",
            {"path": _endpoint_path(source), "line": line_number},
        )
    return cells


def _unescape_markdown_cell(value: str) -> str:
    characters: list[str] = []
    index = 0
    while index < len(value):
        character = value[index]
        if character != "\\" or index + 1 == len(value):
            characters.append(character)
            index += 1
            continue

        escaped = value[index + 1]
        if escaped == "n":
            characters.append("\n")
        elif escaped in {"\\", "|"}:
            characters.append(escaped)
        else:
            characters.extend((character, escaped))
        index += 2
    return "".join(characters)


def _is_separator_row(row: list[str]) -> bool:
    return bool(row) and all(_MARKDOWN_SEPARATOR_RE.fullmatch(cell) is not None for cell in row)


def _escape_markdown_cell(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r\n", "\\n")
        .replace("\r", "\\n")
        .replace("\n", "\\n")
    )


def _format_markdown_row(cells: list[str], widths: list[int]) -> str:
    padded = [cell.ljust(widths[index]) for index, cell in enumerate(cells)]
    return "| " + " | ".join(padded) + " |"


def _format_markdown_separator(widths: list[int]) -> str:
    parts = ["-" * max(3, width) for width in widths]
    return "| " + " | ".join(parts) + " |"


def _endpoint_path(endpoint: Endpoint) -> str | None:
    return None if endpoint.path is None else str(endpoint.path)


__all__ = ["infer_format", "read_local", "write_local", "write_markdown_table"]
