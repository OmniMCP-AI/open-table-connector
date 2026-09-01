"""Closed capability identities for the portable temporal extension."""

from __future__ import annotations

DESCRIBE = "timeseries.describe/1.0"
SCAN_RANGE = "timeseries.scan.range/1.0"
SCAN_RANGE_PUSHDOWN = "timeseries.scan.range.pushdown/1.0"
LOOKUP_LATEST = "timeseries.lookup.latest/1.0"
LOOKUP_ASOF = "timeseries.lookup.asof/1.0"
AGGREGATE_WINDOW = "timeseries.aggregate.window/1.0"
AGGREGATE_WINDOW_PUSHDOWN = "timeseries.aggregate.window.pushdown/1.0"
FILL = "timeseries.fill/1.0"
WRITE_APPEND = "timeseries.write.append/1.0"
WRITE_UPSERT = "timeseries.write.upsert/1.0"
STORAGE_STAGE = "storage.stage/1.0"
STORAGE_COMMIT_IDEMPOTENT = "storage.commit.idempotent/1.0"
STORAGE_SNAPSHOT_READ = "storage.snapshot.read/1.0"
STORAGE_READBACK_VERIFY = "storage.readback.verify/1.0"
STORAGE_VISIBILITY_ATOMIC = "storage.visibility.atomic/1.0"
STORAGE_ABORT = "storage.abort/1.0"

ALL_CAPABILITIES = (
    DESCRIBE,
    SCAN_RANGE,
    SCAN_RANGE_PUSHDOWN,
    LOOKUP_LATEST,
    LOOKUP_ASOF,
    AGGREGATE_WINDOW,
    AGGREGATE_WINDOW_PUSHDOWN,
    FILL,
    WRITE_APPEND,
    WRITE_UPSERT,
    STORAGE_STAGE,
    STORAGE_COMMIT_IDEMPOTENT,
    STORAGE_SNAPSHOT_READ,
    STORAGE_READBACK_VERIFY,
    STORAGE_VISIBILITY_ATOMIC,
    STORAGE_ABORT,
)


__all__ = [
    "AGGREGATE_WINDOW",
    "AGGREGATE_WINDOW_PUSHDOWN",
    "ALL_CAPABILITIES",
    "DESCRIBE",
    "FILL",
    "LOOKUP_ASOF",
    "LOOKUP_LATEST",
    "SCAN_RANGE",
    "SCAN_RANGE_PUSHDOWN",
    "STORAGE_ABORT",
    "STORAGE_COMMIT_IDEMPOTENT",
    "STORAGE_READBACK_VERIFY",
    "STORAGE_SNAPSHOT_READ",
    "STORAGE_STAGE",
    "STORAGE_VISIBILITY_ATOMIC",
    "WRITE_APPEND",
    "WRITE_UPSERT",
]
