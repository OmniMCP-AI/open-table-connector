from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from open_table_connector.timeseries import (
    AggregateFunction,
    AggregateMeasure,
    BucketAggregate,
    CalendarBucket,
    CalendarUnit,
    DuplicatePolicy,
    FixedBucket,
    PolarsTemporalExecutor,
    TemporalExecutionRequest,
    calendar_bucket_start,
    fixed_bucket_start,
    temporal_descriptor_hash,
)

from packages.timeseries.tests.fixtures import (
    MemoryTemporalSource,
    TARGET,
    bounds,
    descriptor,
    portable,
)


def execute(source, operation):
    plan = replace(
        portable(operation),
        descriptor_hash=temporal_descriptor_hash(source.descriptor, source.table.schema),
    )
    return PolarsTemporalExecutor(source).execute(
        TemporalExecutionRequest(TARGET, plan, None, "bucket-test", None)
    ).table


def aggregate(bucket, measures, *, group_by=("symbol",), predicates=()):
    return BucketAggregate(
        start="2026-08-29T00:00:00.000000000Z",
        end="2026-08-29T00:10:00.000000000Z",
        bucket=bucket,
        group_by=group_by,
        measures=measures,
        tag_predicates=predicates,
    )


def test_fixed_bucket_start_uses_flooring_integer_nanoseconds() -> None:
    assert fixed_bucket_start(1_000, 300, 100, 25) == 725
    assert fixed_bucket_start(0, 300, 100, 25) == -175
    with pytest.raises(ValueError, match="width"):
        fixed_bucket_start(1_000, 0, 100, 0)


def test_calendar_bucket_labels_match_dst_and_calendar_goldens() -> None:
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "calendar-cases.json").read_text()
    )
    assert fixture["schema_version"] == "otc.calendar-bucket-cases/v1"
    for case in fixture["cases"]:
        bucket = CalendarBucket(
            count=case["count"],
            unit=CalendarUnit(case["unit"]),
            timezone=case["timezone"],
            week_start=case["week_start"],
            origin=case["origin"],
            offset_ns=case["offset_ns"],
        )
        assert calendar_bucket_start(case["timestamp"], bucket) == case["expected"], case["case_id"]


def test_grouped_fixed_aggregates_have_explicit_null_and_tie_semantics() -> None:
    source = MemoryTemporalSource(
        temporal_descriptor=descriptor(DuplicatePolicy.PRESERVE)
    )
    table = execute(
        source,
        aggregate(
            FixedBucket(
                width_ns=600_000_000_000,
                origin="2026-08-29T00:00:00.000000000Z",
                offset_ns=0,
            ),
            (
                AggregateMeasure("rows", AggregateFunction.COUNT, None),
                AggregateMeasure("avg_price", AggregateFunction.AVG, "price"),
                AggregateMeasure("first_price", AggregateFunction.FIRST, "price"),
                AggregateMeasure("last_price", AggregateFunction.LAST, "price"),
            ),
        ),
    )

    assert table["symbol"].to_pylist() == ["AAPL", "MSFT"]
    assert table["rows"].to_pylist() == [3, 3]
    assert table["avg_price"].to_pylist() == [101.0, 201.0]
    assert table["first_price"].to_pylist() == [100.0, 200.0]
    assert table["last_price"].to_pylist() == [102.0, 202.0]


def test_empty_aggregate_preserves_typed_output_schema() -> None:
    empty = MemoryTemporalSource(table=MemoryTemporalSource().table.slice(0, 0))
    table = execute(
        empty,
        aggregate(
            FixedBucket(300_000_000_000, "2026-08-29T00:00:00.000000000Z", 0),
            (AggregateMeasure("rows", AggregateFunction.COUNT, None),),
        ),
    )

    assert table.num_rows == 0
    assert table.column_names == ["symbol", "bucket", "rows"]
    assert table.schema.field("bucket").type.unit == "ns"
