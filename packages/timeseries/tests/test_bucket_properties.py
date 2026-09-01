from __future__ import annotations

import pytest
from open_table_connector.timeseries import CalendarBucket, CalendarUnit
from open_table_connector.timeseries.buckets import (
    _timestamp_ns,
    calendar_bucket_next,
    calendar_bucket_start,
)


@pytest.mark.parametrize(
    ("timezone", "start"),
    [
        ("America/Santiago", "2026-09-05T04:00:00.000000000Z"),
        ("America/New_York", "2026-03-07T05:00:00.000000000Z"),
    ],
)
def test_calendar_bucket_next_round_trips_across_dst(timezone: str, start: str) -> None:
    bucket = CalendarBucket(1, CalendarUnit.DAY, timezone, 1, start, 0)
    current = calendar_bucket_start(start, bucket)
    for _ in range(4):
        following = calendar_bucket_next(current, bucket)
        assert _timestamp_ns(following) > _timestamp_ns(current)
        assert calendar_bucket_start(following, bucket) == following
        current = following
