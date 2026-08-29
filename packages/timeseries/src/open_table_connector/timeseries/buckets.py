"""Pure fixed-width and calendar bucket arithmetic."""

from __future__ import annotations

import calendar
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from .plan import CalendarBucket, CalendarUnit, _utc_parts


def fixed_bucket_start(
    timestamp_ns: int,
    width_ns: int,
    origin_ns: int,
    offset_ns: int = 0,
) -> int:
    """Return the aligned fixed bucket start using integer floor division."""

    for value, field in (
        (timestamp_ns, "timestamp_ns"),
        (width_ns, "width_ns"),
        (origin_ns, "origin_ns"),
        (offset_ns, "offset_ns"),
    ):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{field} must be an integer")
    if width_ns <= 0:
        raise ValueError("width_ns must be positive")
    anchor = origin_ns + offset_ns
    return anchor + ((timestamp_ns - anchor) // width_ns) * width_ns


def calendar_bucket_start(timestamp: str, bucket: CalendarBucket) -> str:
    """Return a calendar bucket label in UTC while aligning in local wall time."""

    if not isinstance(bucket, CalendarBucket):
        raise TypeError("bucket must be a CalendarBucket")
    timestamp_ns = _timestamp_ns(timestamp)
    origin_ns = _timestamp_ns(bucket.origin)
    shifted = _datetime_from_ns(timestamp_ns - bucket.offset_ns)
    origin = _datetime_from_ns(origin_ns - bucket.offset_ns)
    timezone = ZoneInfo(bucket.timezone)
    local = shifted.astimezone(timezone).replace(tzinfo=None)
    local_origin = origin.astimezone(timezone).replace(tzinfo=None)
    boundary = _calendar_boundary(local, local_origin, bucket)
    boundary_utc = boundary.replace(tzinfo=timezone).astimezone(UTC)
    boundary_ns = _datetime_ns(boundary_utc) + bucket.offset_ns
    return _format_ns(boundary_ns)


def calendar_bucket_next(label: str, bucket: CalendarBucket) -> str:
    """Advance one bucket from an existing calendar bucket label."""

    timezone = ZoneInfo(bucket.timezone)
    shifted = _datetime_from_ns(_timestamp_ns(label) - bucket.offset_ns)
    local = shifted.astimezone(timezone).replace(tzinfo=None)
    if bucket.unit is CalendarUnit.DAY:
        advanced = local + timedelta(days=bucket.count)
    elif bucket.unit is CalendarUnit.WEEK:
        advanced = local + timedelta(weeks=bucket.count)
    else:
        months = {
            CalendarUnit.MONTH: bucket.count,
            CalendarUnit.QUARTER: bucket.count * 3,
            CalendarUnit.YEAR: bucket.count * 12,
        }[bucket.unit]
        advanced = _add_months(local, months)
    utc = advanced.replace(tzinfo=timezone).astimezone(UTC)
    return _format_ns(_datetime_ns(utc) + bucket.offset_ns)


def _calendar_boundary(
    local: datetime,
    origin: datetime,
    bucket: CalendarBucket,
) -> datetime:
    if bucket.unit is CalendarUnit.DAY:
        steps = int((local - origin).total_seconds() // 86_400)
        return origin + timedelta(days=(steps // bucket.count) * bucket.count)
    if bucket.unit is CalendarUnit.WEEK:
        local_week = local.date() - timedelta(
            days=(local.isoweekday() - bucket.week_start) % 7
        )
        origin_week = origin.date() - timedelta(
            days=(origin.isoweekday() - bucket.week_start) % 7
        )
        weeks = (local_week - origin_week).days // 7
        date = origin_week + timedelta(weeks=(weeks // bucket.count) * bucket.count)
        return datetime.combine(date, origin.time())
    months_per_unit = {
        CalendarUnit.MONTH: 1,
        CalendarUnit.QUARTER: 3,
        CalendarUnit.YEAR: 12,
    }[bucket.unit]
    width = bucket.count * months_per_unit
    months = (local.year - origin.year) * 12 + local.month - origin.month
    candidate = _add_months(origin, months)
    if local < candidate:
        months -= 1
    return _add_months(origin, (months // width) * width)


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.year * 12 + value.month - 1 + months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _timestamp_ns(value: str) -> int:
    seconds, fraction = _utc_parts(value, "timestamp")
    return seconds * 1_000_000_000 + fraction


def _datetime_from_ns(value: int) -> datetime:
    seconds, nanos = divmod(value, 1_000_000_000)
    return datetime.fromtimestamp(seconds, UTC).replace(microsecond=nanos // 1_000)


def _datetime_ns(value: datetime) -> int:
    seconds = calendar.timegm(value.utctimetuple())
    return seconds * 1_000_000_000 + value.microsecond * 1_000


def _format_ns(value: int) -> str:
    seconds, nanos = divmod(value, 1_000_000_000)
    whole = datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%S")
    return f"{whole}.{nanos:09d}Z"


__all__ = ["calendar_bucket_next", "calendar_bucket_start", "fixed_bucket_start"]
