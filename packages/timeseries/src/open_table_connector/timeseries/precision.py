"""Lossless integer conversion between UTC wire timestamps and storage units."""

from __future__ import annotations

from datetime import UTC, datetime

import pyarrow as pa

from .descriptor import TimestampPrecision
from .plan import _utc_parts

_SCALE = {
    TimestampPrecision.SECOND: 1,
    TimestampPrecision.MILLISECOND: 1_000,
    TimestampPrecision.MICROSECOND: 1_000_000,
    TimestampPrecision.NANOSECOND: 1_000_000_000,
}
_DIGITS = {
    TimestampPrecision.SECOND: 0,
    TimestampPrecision.MILLISECOND: 3,
    TimestampPrecision.MICROSECOND: 6,
    TimestampPrecision.NANOSECOND: 9,
}


def timestamp_to_storage(value: str, precision: TimestampPrecision) -> int:
    precision = TimestampPrecision(precision)
    seconds, nanos = _utc_parts(value, "timestamp")
    scale = _SCALE[precision]
    return seconds * scale + nanos // (1_000_000_000 // scale)


def storage_to_timestamp(value: int, precision: TimestampPrecision) -> str:
    precision = TimestampPrecision(precision)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("stored timestamp must be an integer")
    scale = _SCALE[precision]
    seconds, units = divmod(value, scale)
    whole = datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%S")
    digits = _DIGITS[precision]
    return f"{whole}Z" if digits == 0 else f"{whole}.{units:0{digits}d}Z"


def arrow_time_bounds(table: pa.Table, field: str, precision: TimestampPrecision) -> tuple[str, str] | None:
    if not isinstance(table, pa.Table):
        raise TypeError("table must be a pyarrow.Table")
    column = table[field]
    if len(column) == 0 or column.null_count:
        return None
    values = column.cast(pa.int64()).to_pylist()
    precision = TimestampPrecision(precision)
    # Receipts use the canonical nine-digit UTC representation regardless of
    # the physical descriptor precision.  Convert integer storage units to
    # nanoseconds without passing through floating point.
    factor = 1_000_000_000 // _SCALE[precision]
    return (
        storage_to_timestamp(min(values) * factor, TimestampPrecision.NANOSECOND),
        storage_to_timestamp(max(values) * factor, TimestampPrecision.NANOSECOND),
    )


__all__ = ["arrow_time_bounds", "storage_to_timestamp", "timestamp_to_storage"]
