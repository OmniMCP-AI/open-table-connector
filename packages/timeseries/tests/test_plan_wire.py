from __future__ import annotations

import json

import pytest

from open_table_connector.timeseries import (
    AggregateFunction,
    AggregateMeasure,
    AsOf,
    BucketAggregate,
    CalendarBucket,
    CalendarUnit,
    DuplicatePolicy,
    FillMode,
    FillRule,
    FixedBucket,
    GapFill,
    Latest,
    OrderDirection,
    OrderKey,
    PortableTemporalPlan,
    ResourceBounds,
    ScanRange,
    TagOperator,
    TagPredicate,
    TemporalOrdering,
    TemporalTableDescriptor,
    TimestampPrecision,
    plan_from_wire,
    portable_plan_hash,
    validate_plan_for_descriptor,
)


DESCRIPTOR_HASH = "sha256:" + "a" * 64
START = "2026-08-29T00:00:00.000000000Z"
END = "2026-08-30T00:00:00.000000000Z"


def descriptor() -> TemporalTableDescriptor:
    return TemporalTableDescriptor(
        time_field="ts",
        timezone="UTC",
        precision=TimestampPrecision.NANOSECOND,
        series_key_fields=("symbol",),
        tag_fields=("venue",),
        value_fields=("price", "size"),
        ingestion_time_field="received_at",
        duplicate_policy=DuplicatePolicy.REPLACE_LATEST,
        ordering=TemporalOrdering.UNSPECIFIED,
    )


def plan(operation: object) -> PortableTemporalPlan:
    return PortableTemporalPlan(
        schema_version="otc.portable-temporal-plan/v1",
        descriptor_hash=DESCRIPTOR_HASH,
        relation="ticks",
        required_capabilities=("timeseries.scan.range/1.0",),
        resource_bounds=ResourceBounds(
            max_rows=1_000,
            max_bytes=1_000_000,
            max_duration_ms=5_000,
        ),
        operation=operation,
        output_order=(
            OrderKey(field="symbol", direction=OrderDirection.ASC),
            OrderKey(field="ts", direction=OrderDirection.ASC),
        ),
        result_row_limit=500,
    )


def predicates() -> tuple[TagPredicate, ...]:
    return (
        TagPredicate(field="symbol", operator=TagOperator.IN, values=("AAPL", "MSFT")),
        TagPredicate(field="venue", operator=TagOperator.EQ, values=("XNAS",)),
    )


def measures() -> tuple[AggregateMeasure, ...]:
    return (
        AggregateMeasure(output_field="avg_price", function=AggregateFunction.AVG, value_field="price"),
        AggregateMeasure(output_field="rows", function=AggregateFunction.COUNT, value_field=None),
    )


def operations() -> tuple[object, ...]:
    fixed = FixedBucket(width_ns=300_000_000_000, origin=START, offset_ns=0)
    return (
        ScanRange(
            start=START,
            end=END,
            projection=("ts", "symbol", "price"),
            tag_predicates=predicates(),
        ),
        Latest(
            at_or_before=END,
            projection=("ts", "symbol", "price"),
            tag_predicates=predicates(),
        ),
        AsOf(
            at=END,
            projection=("ts", "symbol", "price"),
            tag_predicates=predicates(),
        ),
        BucketAggregate(
            start=START,
            end=END,
            bucket=fixed,
            group_by=("symbol",),
            measures=measures(),
            tag_predicates=predicates(),
        ),
        GapFill(
            start=START,
            end=END,
            bucket=CalendarBucket(
                count=1,
                unit=CalendarUnit.DAY,
                timezone="America/New_York",
                week_start=1,
                origin=START,
                offset_ns=0,
            ),
            group_by=("symbol",),
            measures=measures(),
            tag_predicates=predicates(),
            fills=(
                FillRule(field="avg_price", mode=FillMode.LINEAR, value=None),
                FillRule(field="rows", mode=FillMode.CONSTANT, value=0),
            ),
        ),
    )


@pytest.mark.parametrize("operation", operations())
def test_every_operation_round_trips_as_a_closed_document(operation: object) -> None:
    document = plan(operation)

    assert plan_from_wire(document.to_wire()) == document
    assert list(document.to_wire()) == [
        "schema_version",
        "descriptor_hash",
        "relation",
        "required_capabilities",
        "resource_bounds",
        "operation",
        "output_order",
        "result_row_limit",
    ]
    validate_plan_for_descriptor(document, descriptor())


def test_plan_hash_is_canonical_and_excludes_physical_configuration() -> None:
    document = plan(operations()[0])
    reordered = json.loads(json.dumps(document.to_wire(), sort_keys=True))

    assert portable_plan_hash(document) == portable_plan_hash(plan_from_wire(reordered))
    assert portable_plan_hash(document).startswith("sha256:")
    assert "uri" not in json.dumps(document.to_wire()).casefold()
    assert "credential" not in json.dumps(document.to_wire()).casefold()


def test_unknown_fields_are_rejected_recursively() -> None:
    wire = plan(operations()[0]).to_wire()
    wire["operation"]["sql"] = "select *"

    with pytest.raises(ValueError, match="unknown scan_range fields"):
        plan_from_wire(wire)


@pytest.mark.parametrize(
    "start,end",
    [
        (START, START),
        (END, START),
        ("2026-08-29T08:00:00+08:00", END),
    ],
)
def test_scan_range_rejects_empty_reversed_or_non_utc_ranges(start: str, end: str) -> None:
    with pytest.raises(ValueError):
        ScanRange(start=start, end=end, projection=("ts",), tag_predicates=())


def test_plan_rejects_zero_bounds_duplicate_fields_and_oversized_limit() -> None:
    with pytest.raises(ValueError, match="positive"):
        ResourceBounds(max_rows=0, max_bytes=1, max_duration_ms=1)

    with pytest.raises(ValueError, match="duplicate projection"):
        ScanRange(start=START, end=END, projection=("ts", "ts"), tag_predicates=())

    with pytest.raises(ValueError, match="duplicate output order"):
        PortableTemporalPlan(
            **{
                **plan(operations()[0]).to_wire(),
                "operation": operations()[0],
                "resource_bounds": ResourceBounds(10, 100, 100),
                "output_order": (
                    OrderKey("ts", OrderDirection.ASC),
                    OrderKey("ts", OrderDirection.DESC),
                ),
                "result_row_limit": 11,
            }
        )


def test_descriptor_validation_rejects_undeclared_predicate_and_measure_fields() -> None:
    invalid_predicate = plan(
        ScanRange(
            start=START,
            end=END,
            projection=("ts", "symbol"),
            tag_predicates=(TagPredicate("price", TagOperator.EQ, (1.0,)),),
        )
    )
    with pytest.raises(ValueError, match="predicate field"):
        validate_plan_for_descriptor(invalid_predicate, descriptor())

    invalid_measure = plan(
        BucketAggregate(
            start=START,
            end=END,
            bucket=FixedBucket(1_000_000_000, START, 0),
            group_by=("symbol",),
            measures=(AggregateMeasure("bad", AggregateFunction.SUM, "venue"),),
            tag_predicates=(),
        )
    )
    with pytest.raises(ValueError, match="aggregate value field"):
        validate_plan_for_descriptor(invalid_measure, descriptor())
