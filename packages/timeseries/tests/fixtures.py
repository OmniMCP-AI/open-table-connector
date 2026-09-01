from __future__ import annotations

from dataclasses import replace

import pyarrow as pa
from open_table_connector.contract import TableURI
from open_table_connector.timeseries import (
    AsOf,
    BucketAggregate,
    DuplicatePolicy,
    GapFill,
    Latest,
    OrderDirection,
    OrderKey,
    PortableTemporalPlan,
    ResourceBounds,
    ScanRange,
    TagPredicate,
    TemporalOrdering,
    TemporalTableDescriptor,
    TimestampPrecision,
    temporal_descriptor_hash,
)

TARGET = TableURI("json:///fixtures/ticks.json")


def ns(minutes: int, extra_ns: int = 0) -> int:
    return 1_787_961_600_000_000_000 + minutes * 60_000_000_000 + extra_ns


def ticks_table() -> pa.Table:
    order = [3, 0, 5, 2, 6, 1, 4]
    rows = {
        "ts": [ns(10), ns(0, 123), ns(5), ns(5), ns(0), ns(5), ns(5)],
        "symbol": ["AAPL", "AAPL", "AAPL", "AAPL", "MSFT", "MSFT", "MSFT"],
        "venue": ["XNAS", "XNAS", "XNAS", "XNAS", "XNYS", "XNYS", "ARCX"],
        "price": [103.0, 100.0, 101.0, 102.0, 200.0, None, 202.0],
        "size": [13, 10, 11, 12, 20, 21, 22],
        "received_at": [
            ns(10, 1),
            ns(0, 124),
            ns(5, 1),
            ns(5, 2),
            ns(0, 1),
            ns(5, 1),
            ns(5, 2),
        ],
    }
    arrays = [
        pa.array([rows["ts"][index] for index in order], type=pa.timestamp("ns", tz="UTC")),
        pa.array([rows["symbol"][index] for index in order]),
        pa.array([rows["venue"][index] for index in order]),
        pa.array([rows["price"][index] for index in order], type=pa.float64()),
        pa.array([rows["size"][index] for index in order], type=pa.int64()),
        pa.array(
            [rows["received_at"][index] for index in order],
            type=pa.timestamp("ns", tz="UTC"),
        ),
    ]
    return pa.Table.from_arrays(
        arrays,
        names=["ts", "symbol", "venue", "price", "size", "received_at"],
    )


def descriptor(policy: DuplicatePolicy = DuplicatePolicy.REPLACE_LATEST) -> TemporalTableDescriptor:
    return TemporalTableDescriptor(
        time_field="ts",
        timezone="UTC",
        precision=TimestampPrecision.NANOSECOND,
        series_key_fields=("symbol",),
        tag_fields=("venue",),
        value_fields=("price", "size"),
        ingestion_time_field="received_at",
        duplicate_policy=policy,
        ordering=TemporalOrdering.UNSPECIFIED,
    )


class MemoryTemporalSource:
    def __init__(
        self,
        table: pa.Table | None = None,
        temporal_descriptor: TemporalTableDescriptor | None = None,
    ) -> None:
        self.table = table if table is not None else ticks_table()
        self.descriptor = temporal_descriptor if temporal_descriptor is not None else descriptor()
        self.last_projection: tuple[str, ...] | None = None

    def read_bounded(self, target, projection, predicates, bounds):
        del target, predicates, bounds
        self.last_projection = tuple(projection)
        return self.table.select(projection)


def bounds(**changes: int) -> ResourceBounds:
    values = {"max_rows": 100, "max_bytes": 10_000_000, "max_duration_ms": 1_000}
    values.update(changes)
    return ResourceBounds(**values)


def portable(operation, *, resource_bounds: ResourceBounds | None = None, limit: int | None = None):
    if isinstance(operation, (BucketAggregate, GapFill)):
        output_order = (
            OrderKey("symbol", OrderDirection.ASC),
            OrderKey("bucket", OrderDirection.ASC),
        )
    else:
        output_order = (
            OrderKey("symbol", OrderDirection.ASC),
            OrderKey("ts", OrderDirection.ASC),
        )
    return PortableTemporalPlan(
        schema_version="otc.portable-temporal-plan/v1",
        descriptor_hash=temporal_descriptor_hash(descriptor(), ticks_table().schema),
        relation="ticks",
        required_capabilities=(),
        resource_bounds=resource_bounds or bounds(),
        operation=operation,
        output_order=output_order,
        result_row_limit=limit,
    )


def scan(*, predicates: tuple[TagPredicate, ...] = (), resource_bounds=None):
    return portable(
        ScanRange(
            start="2026-08-29T00:00:00.000000000Z",
            end="2026-08-29T00:10:00.000000000Z",
            projection=("ts", "symbol", "venue", "price"),
            tag_predicates=predicates,
        ),
        resource_bounds=resource_bounds,
    )


def latest(*, resource_bounds=None):
    return portable(
        Latest(
            at_or_before="2026-08-29T00:05:00.000000000Z",
            projection=("ts", "symbol", "venue", "price"),
            tag_predicates=(),
        ),
        resource_bounds=resource_bounds,
    )


def as_of(*, resource_bounds=None):
    return portable(
        AsOf(
            at="2026-08-29T00:00:00.000000123Z",
            projection=("ts", "symbol", "venue", "price"),
            tag_predicates=(),
        ),
        resource_bounds=resource_bounds,
    )


def with_policy(source: MemoryTemporalSource, policy: DuplicatePolicy) -> MemoryTemporalSource:
    source.descriptor = replace(source.descriptor, duplicate_policy=policy)
    return source
