"""Strict deterministic JSON and JSONL Arrow codecs."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
import json
import math
from typing import Mapping

import pyarrow as pa

from open_table_connector.contract import ConnectorError, ConnectorErrorCode


class _DuplicateKey(ValueError):
    pass


class _NonFiniteConstant(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey(key)
        result[key] = value
    return result


def _reject_non_finite(value: str) -> object:
    raise _NonFiniteConstant(value)


def _loads(text: str, *, source: str, line: int | None = None) -> object:
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite,
        )
    except json.JSONDecodeError as exc:
        details: dict[str, object] = {
            "source": source,
            "line": line if line is not None else exc.lineno,
            "column": exc.colno,
        }
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "JSONL line is malformed" if line is not None else "JSON input is malformed",
            details,
        ) from None
    except _DuplicateKey:
        details = {"source": source}
        if line is not None:
            details["line"] = line
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "JSON object contains a duplicate key",
            details,
        ) from None
    except _NonFiniteConstant:
        details = {"source": source}
        if line is not None:
            details["line"] = line
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "JSON contains a non-finite numeric constant",
            details,
        ) from None


def parse_json_table(text: str, *, source: str) -> pa.Table:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    payload = _loads(text, source=source)
    if not isinstance(payload, list):
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "JSON input must contain one top-level array of objects",
            {"source": source},
        )
    rows: list[Mapping[str, object]] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, Mapping):
            raise ConnectorError(
                ConnectorErrorCode.EXECUTION_FAILED,
                "JSON array items must be objects",
                {"source": source, "index": index},
            )
        rows.append(item)
    return _rows_to_table(rows, source=source)


def parse_jsonl_table(text: str, *, source: str) -> pa.Table:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    rows: list[Mapping[str, object]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        item = _loads(line, source=source, line=line_number)
        if not isinstance(item, Mapping):
            raise ConnectorError(
                ConnectorErrorCode.EXECUTION_FAILED,
                "JSONL rows must be objects",
                {"source": source, "line": line_number},
            )
        rows.append(item)
    return _rows_to_table(rows, source=source)


def _rows_to_table(rows: list[Mapping[str, object]], *, source: str) -> pa.Table:
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                columns.append(key)
    if not columns:
        return pa.table({})
    values = {name: [row.get(name) for row in rows] for name in columns}
    try:
        return pa.table(values)
    except (pa.ArrowInvalid, pa.ArrowNotImplementedError, TypeError, ValueError) as exc:
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "JSON rows contain incompatible Arrow value shapes",
            {"source": source, "reason": type(exc).__name__},
        ) from None


def encode_json_table(table: pa.Table) -> str:
    rows = _table_rows(table)
    return json.dumps(
        rows,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


def encode_jsonl_table(table: pa.Table) -> str:
    rows = _table_rows(table)
    return "".join(
        json.dumps(
            row,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
        for row in rows
    )


def _table_rows(table: pa.Table) -> list[dict[str, object]]:
    if not isinstance(table, pa.Table):
        raise TypeError("table must be a pyarrow.Table")
    columns: list[list[object]] = []
    for field, column in zip(table.schema, table.columns, strict=True):
        if pa.types.is_timestamp(field.type):
            raw = column.cast(pa.int64()).to_pylist()
            columns.append(
                [
                    None if value is None else _timestamp_text(value, field.type.unit)
                    for value in raw
                ]
            )
        else:
            columns.append([_json_value(item) for item in column])
    return [
        {
            name: columns[column_index][row_index]
            for column_index, name in enumerate(table.column_names)
        }
        for row_index in range(table.num_rows)
    ]


def _json_value(value: object) -> object:
    if isinstance(value, pa.Scalar):
        if not value.is_valid:
            return None
        return _json_value(value.as_py())
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ConnectorError(
                ConnectorErrorCode.EXECUTION_FAILED,
                "JSON encoding rejects non-finite numeric values",
                {},
            )
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ConnectorError(
                ConnectorErrorCode.EXECUTION_FAILED,
                "JSON encoding rejects non-finite decimal values",
                {},
            )
        return format(value, "f")
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.isoformat()
        utc = value.astimezone(UTC)
        return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond * 1000:09d}Z"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {
            str(key): _json_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    raise ConnectorError(
        ConnectorErrorCode.EXECUTION_FAILED,
        "Arrow value cannot be represented by the strict JSON codec",
        {"type": type(value).__name__},
    )


def _timestamp_text(value: int, unit: str) -> str:
    scale = {"s": 1_000_000_000, "ms": 1_000_000, "us": 1_000, "ns": 1}[unit]
    nanoseconds = value * scale
    seconds, fraction = divmod(nanoseconds, 1_000_000_000)
    whole = datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%S")
    return f"{whole}.{fraction:09d}Z"


__all__ = [
    "encode_json_table",
    "encode_jsonl_table",
    "parse_json_table",
    "parse_jsonl_table",
]
