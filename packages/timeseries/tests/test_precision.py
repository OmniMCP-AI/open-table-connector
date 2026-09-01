from __future__ import annotations

import pytest
from open_table_connector.timeseries import TimestampPrecision
from open_table_connector.timeseries.precision import storage_to_timestamp, timestamp_to_storage


@pytest.mark.parametrize(
    ("precision", "value", "stored"),
    [
        (TimestampPrecision.SECOND, "1969-12-31T23:59:59Z", -1),
        (TimestampPrecision.MILLISECOND, "2026-08-29T00:00:00.123Z", 1787961600123),
        (TimestampPrecision.MICROSECOND, "2026-08-29T00:00:00.123456Z", 1787961600123456),
        (TimestampPrecision.NANOSECOND, "2026-08-29T00:00:00.123456789Z", 1787961600123456789),
    ],
)
def test_timestamp_storage_round_trip(precision, value, stored) -> None:
    assert timestamp_to_storage(value, precision) == stored
    assert storage_to_timestamp(stored, precision) == value
