"""Stable, credential-safe output for CLI commands."""

from __future__ import annotations

import json
import csv
from dataclasses import fields, is_dataclass
from enum import Enum
from collections.abc import Iterable, Sequence
from typing import Any, TextIO

import pyarrow as pa

from open_connectors.contract import ArrowReadResult, ConnectorError, ConnectorErrorCode

from .formats import json_safe_value, write_local
from .model import FormatName, PipelineSummary


EXIT_CODES = {
    ConnectorErrorCode.INVALID_URI: 2,
    ConnectorErrorCode.UNSUPPORTED_CAPABILITY: 3,
    ConnectorErrorCode.AUTHENTICATION: 4,
    ConnectorErrorCode.CONFLICT: 6,
    ConnectorErrorCode.TIMEOUT: 5,
    ConnectorErrorCode.CANCELLED: 5,
    ConnectorErrorCode.EXECUTION_FAILED: 5,
    ConnectorErrorCode.READBACK_MISMATCH: 5,
}


def _wire(value: Any) -> Any:
    """Convert contract values to JSON without exposing arbitrary exceptions."""
    if isinstance(value, Enum):
        return value.value
    to_wire = getattr(value, "to_wire", None)
    if callable(to_wire):
        return _wire(to_wire())
    if is_dataclass(value):
        return {item.name: _wire(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, dict):
        return {str(key): _wire(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_wire(item) for item in value]
    return json_safe_value(value)


def _write_json(value: Any, out: TextIO) -> None:
    out.write(
        json.dumps(_wire(value), ensure_ascii=False, allow_nan=False, default=str) + "\n"
    )


def _display(value: Any) -> str:
    value = _wire(value)
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return str(value).replace("\n", "\\n").replace("|", "\\|")


def emit_table(headers: Sequence[str], rows: Iterable[Sequence[Any]], out: TextIO) -> None:
    """Emit a small deterministic Markdown table for human-readable output."""
    names = [str(header) for header in headers]
    values = [[_display(value) for value in row] for row in rows]
    if any(len(row) != len(names) for row in values):
        raise ValueError("table rows must match the header width")
    widths = [max([len(name), 3] + [len(row[index]) for row in values]) for index, name in enumerate(names)]

    def row_line(row: Sequence[str]) -> str:
        return "| " + " | ".join(value.ljust(widths[index]) for index, value in enumerate(row)) + " |\n"

    out.write(row_line(names))
    out.write(row_line(["-" * width for width in widths]))
    for row in values:
        out.write(row_line(row))


def _record_columns(records: Sequence[dict[str, Any]], headers: Sequence[str] | None) -> list[str]:
    if headers is not None:
        return [str(header) for header in headers]
    columns: list[str] = []
    for record in records:
        for key in record:
            if key not in columns:
                columns.append(key)
    return columns


def emit_csv(
    records: Sequence[dict[str, Any]], out: TextIO, headers: Sequence[str] | None = None
) -> None:
    """Emit records as valid CSV, stringifying structured cells safely."""
    columns = _record_columns(records, headers)
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(columns)
    for record in records:
        writer.writerow([_display(record.get(column)) for column in columns])


def emit_record(
    record: dict[str, Any], output_format: FormatName, out: TextIO,
    *, headers: Sequence[str] | None = None,
) -> None:
    """Emit one object in the selected command-output format."""
    if output_format in (FormatName.JSONL, FormatName.JSON):
        _write_json(record, out)
        return
    if output_format is FormatName.CSV:
        emit_csv([record], out, headers)
        return
    if output_format is FormatName.TABLE:
        columns = _record_columns([record], headers)
        emit_table(("field", "value"), ((column, record.get(column)) for column in columns), out)
        return
    raise ValueError("output format must be explicit")


def emit_records(
    records: Sequence[dict[str, Any]], output_format: FormatName, out: TextIO,
    *, headers: Sequence[str] | None = None,
) -> None:
    """Emit a collection, using one JSON document for JSON output."""
    if output_format is FormatName.JSONL:
        for record in records:
            _write_json(record, out)
        return
    if output_format is FormatName.JSON:
        _write_json(list(records), out)
        return
    if output_format is FormatName.CSV:
        emit_csv(records, out, headers)
        return
    if output_format is FormatName.TABLE:
        columns = _record_columns(records, headers)
        emit_table(columns, ([record.get(column) for column in columns] for record in records), out)
        return
    raise ValueError("output format must be explicit")


def _rows(table: pa.Table) -> list[dict[str, Any]]:
    return [{str(key): _wire(value) for key, value in row.items()} for row in table.to_pylist()]


def emit_read(result: ArrowReadResult, output_format: FormatName, out: TextIO) -> None:
    """Emit a read in the requested format, with receipts only in JSON formats."""
    if output_format is FormatName.JSONL:
        for row in _rows(result.table):
            _write_json({"event": "row", "row": row}, out)
        _write_json(
            {"event": "summary", "status": "completed", "rows": result.table.num_rows,
             "receipt": result.receipt.to_wire()},
            out,
        )
        return
    if output_format is FormatName.JSON:
        _write_json({"rows": _rows(result.table), "receipt": result.receipt.to_wire()}, out)
        return
    if output_format in (FormatName.CSV, FormatName.TABLE):
        write_local(result.table, _stream_endpoint(output_format), output_format, out)
        return
    raise ValueError("output format must be explicit")


def _stream_endpoint(output_format: FormatName):
    # Local codecs use an stdio Endpoint for a supplied stream.
    from .model import Endpoint

    return Endpoint(raw="-", uri=None, path=None, is_stdio=True)


def emit_summary(
    summary: PipelineSummary, out: TextIO, output_format: FormatName = FormatName.JSONL
) -> None:
    if output_format is FormatName.TABLE:
        rows: list[tuple[str, Any]] = [("status", summary.status)]
        if summary.rows_read is not None:
            rows.append(("rows_read", summary.rows_read))
        if summary.rows_written is not None:
            rows.append(("rows_written", summary.rows_written))
        if summary.source_receipt is not None:
            rows.append(("source_receipt", summary.source_receipt))
        if summary.destination_receipt is not None:
            rows.append(("destination_receipt", summary.destination_receipt))
        emit_table(("field", "value"), rows, out)
        return
    payload: dict[str, Any] = {"status": summary.status}
    if summary.rows_read is not None:
        payload["rows_read"] = summary.rows_read
        payload["rows"] = summary.rows_read
    if summary.rows_written is not None:
        payload["rows_written"] = summary.rows_written
    if summary.source_receipt is not None:
        payload["source_receipt"] = _wire(summary.source_receipt)
        payload.setdefault("receipt", _wire(summary.source_receipt))
    if summary.destination_receipt is not None:
        payload["destination_receipt"] = _wire(summary.destination_receipt)
    if output_format is FormatName.CSV:
        emit_csv([payload], out)
        return
    if output_format in (FormatName.JSONL, FormatName.JSON):
        _write_json(payload, out)
        return
    raise ValueError("output format must be explicit")


def emit_error(error: BaseException, err: TextIO) -> int:
    if isinstance(error, ConnectorError):
        payload = error.to_wire()
        code = EXIT_CODES.get(error.code, 5)
    elif isinstance(error, ValueError):
        payload = {"code": "usage", "message": "invalid command input", "safe_details": {}}
        code = 2
    elif isinstance(error, OSError):
        payload = {"code": "execution", "message": "command execution failed", "safe_details": {}}
        code = 5
    else:
        payload = {"code": "execution", "message": "command failed", "safe_details": {}}
        code = 5
    _write_json(payload, err)
    return code


__all__ = [
    "emit_error",
    "emit_csv",
    "emit_read",
    "emit_record",
    "emit_records",
    "emit_summary",
    "emit_table",
]
