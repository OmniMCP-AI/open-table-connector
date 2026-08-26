"""Canonical CSV-to-Arrow materialization for the local-files Connector."""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pyarrow as pa

from open_connectors.contract import ConnectorError, ConnectorErrorCode, ResourceLimits


def _headers(values: list[str]) -> list[str]:
    """Use Polars-compatible deterministic names for duplicate headers."""

    seen: dict[str, int] = {}
    result: list[str] = []
    for value in values:
        count = seen.get(value, 0)
        result.append(value if count == 0 else f"{value}_duplicated_{count - 1}")
        seen[value] = count + 1
    return result


def read_csv_arrow(
    path: Path,
    *,
    separator: str,
    encoding: str,
    limits: ResourceLimits,
) -> pa.Table:
    try:
        text = path.read_bytes().decode(encoding)
    except (OSError, UnicodeError) as exc:
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "CSV file could not be decoded",
            {"path": str(path), "encoding": encoding, "reason": str(exc)},
        ) from None

    if not text.strip():
        return pa.table({})
    try:
        rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=separator))
    except csv.Error as exc:
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "CSV file is malformed",
            {"path": str(path), "reason": str(exc)},
        ) from None
    if not rows:
        return pa.table({})

    names = _headers([str(value) for value in rows[0]])
    if not names:
        return pa.table({})
    data_rows: list[list[str | None]] = []
    for row in rows[1:]:
        if len(row) > len(names):
            raise ConnectorError(
                ConnectorErrorCode.EXECUTION_FAILED,
                "CSV row has more fields than the header",
                {"path": str(path), "expected_fields": len(names), "actual_fields": len(row)},
            )
        normalized = [value if value != "" else None for value in row]
        normalized.extend([None] * (len(names) - len(normalized)))
        data_rows.append(normalized)
        if limits.max_rows is not None and len(data_rows) >= limits.max_rows:
            break

    columns = [
        pa.array([row[index] for row in data_rows], type=pa.large_string())
        for index in range(len(names))
    ]
    return pa.Table.from_arrays(columns, names=names)
