"""Stable, credential-safe output for CLI commands."""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any, TextIO

import pyarrow as pa

from open_connectors.contract import ArrowReadResult, ConnectorError, ConnectorErrorCode

from .formats import write_local
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
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
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
    return str(value)


def _write_json(value: Any, out: TextIO) -> None:
    out.write(json.dumps(_wire(value), ensure_ascii=False, default=str) + "\n")


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


def emit_summary(summary: PipelineSummary, out: TextIO) -> None:
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
    _write_json(payload, out)


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


__all__ = ["emit_error", "emit_read", "emit_summary"]
