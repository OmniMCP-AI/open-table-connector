"""JSON array, object, and newline-delimited JSON to Arrow conversion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pyarrow as pa

from open_table_connector.contract import ConnectorError, ConnectorErrorCode, ResourceLimits


def read_json_arrow(path: Path, *, encoding: str, limits: ResourceLimits) -> pa.Table:
    try:
        text = path.read_bytes().decode(encoding)
        try:
            payload: Any = json.loads(text)
        except json.JSONDecodeError:
            payload = [json.loads(line) for line in text.splitlines() if line.strip()]
    except (OSError, UnicodeError, LookupError, json.JSONDecodeError) as exc:
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "JSON file could not be decoded",
            {"path": str(path), "encoding": encoding, "reason": str(exc)},
        ) from None
    if isinstance(payload, Mapping):
        records = [dict(payload)]
    elif isinstance(payload, list) and all(isinstance(item, Mapping) for item in payload):
        records = [dict(item) for item in payload]
    else:
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "JSON table must be an object or an array of objects",
            {"path": str(path)},
        )
    if limits.max_rows is not None:
        records = records[: limits.max_rows]
    try:
        return pa.Table.from_pylist(records)
    except (pa.ArrowInvalid, pa.ArrowTypeError) as exc:
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "JSON records do not form a consistent table",
            {"path": str(path), "reason": str(exc)},
        ) from None


__all__ = ["read_json_arrow"]
