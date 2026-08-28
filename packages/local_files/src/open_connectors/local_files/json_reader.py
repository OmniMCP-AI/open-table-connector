"""Deterministic JSON-record/array to Arrow materialization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow as pa

from open_connectors.contract import ConnectorError, ConnectorErrorCode, ResourceLimits


def _rows(payload: Any) -> tuple[list[str], list[dict[str, Any]]]:
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        raise ValueError("JSON root must be an array of records or arrays")
    if not payload:
        return [], []
    if all(isinstance(item, dict) for item in payload):
        names: list[str] = []
        for item in payload:
            for key in item:
                key = str(key)
                if key not in names:
                    names.append(key)
        return names, [{name: item.get(name) for name in names} for item in payload]
    if all(isinstance(item, list) for item in payload):
        header = payload[0]
        if any(not isinstance(name, (str, int, float, bool)) for name in header):
            raise ValueError("JSON array header values must be scalar")
        names: list[str] = []
        for value in header:
            name = str(value)
            if name in names:
                suffix = 0
                candidate = f"{name}_duplicated_{suffix}"
                while candidate in names:
                    suffix += 1
                    candidate = f"{name}_duplicated_{suffix}"
                name = candidate
            names.append(name)
        records = []
        for item in payload[1:]:
            records.append({name: item[index] if index < len(item) else None for index, name in enumerate(names)})
        return names, records
    raise ValueError("JSON arrays must contain only records or arrays")


def read_json_arrow(path: Path, *, limits: ResourceLimits) -> pa.Table:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        names, records = _rows(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "JSON file could not be read",
            {"path": str(path), "reason": str(exc)},
        ) from None
    if limits.max_rows is not None:
        records = records[: limits.max_rows]
    if not names:
        return pa.table({})
    # Construct columns in first-seen header order.  Arrow infers one stable
    # type per column while preserving JSON nulls and scalar values.
    try:
        return pa.Table.from_pylist(records, schema=pa.schema([pa.field(name, pa.array([row.get(name) for row in records]).type) for name in names]))
    except Exception as exc:
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "JSON values have incompatible column types",
            {"path": str(path), "reason": str(exc)},
        ) from None


__all__ = ["read_json_arrow"]
