from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pyarrow as pa


def temporal_table(rows: int, unique_timestamps: int) -> pa.Table:
    if rows < 1 or unique_timestamps < 1 or unique_timestamps > rows:
        raise ValueError(
            "rows and unique_timestamps must be positive, with unique_timestamps <= rows"
        )
    start = datetime(2026, 8, 29, tzinfo=UTC)
    timestamps = [start + timedelta(minutes=index % unique_timestamps) for index in range(rows)]
    return pa.table(
        {
            "entity": [f"entity-{index % 17}" for index in range(rows)],
            "ts": timestamps,
            "value": [float(index) for index in range(rows)],
        }
    )
