from __future__ import annotations

from dataclasses import replace

import pytest
from open_table_connector.timeseries import (
    AggregateFunction,
    AggregateMeasure,
    BucketAggregate,
    DuplicatePolicy,
    FixedBucket,
    PolarsTemporalExecutor,
    TemporalExecutionRequest,
    TemporalExtensionError,
    TemporalTableDescriptor,
    TimestampPrecision,
    temporal_descriptor_hash,
    validate_plan_for_descriptor,
)

from packages.timeseries.tests.fixtures import TARGET, MemoryTemporalSource, descriptor, portable


def _first_last_plan(policy: DuplicatePolicy):
    source = MemoryTemporalSource(temporal_descriptor=descriptor(policy))
    operation = BucketAggregate(
        "2026-08-29T00:00:00.000000000Z",
        "2026-08-29T00:10:00.000000000Z",
        FixedBucket(600_000_000_000, "2026-08-29T00:00:00.000000000Z"),
        ("symbol",),
        (AggregateMeasure("first_price", AggregateFunction.FIRST, "price"),),
        (),
    )
    return source, replace(
        portable(operation),
        descriptor_hash=temporal_descriptor_hash(source.descriptor, source.table.schema),
    )


def test_first_and_last_are_rejected_for_preserve_policy() -> None:
    source, plan = _first_last_plan(DuplicatePolicy.PRESERVE)

    with pytest.raises(ValueError, match="duplicate resolution"):
        validate_plan_for_descriptor(plan, source.descriptor)


def test_first_and_last_are_allowed_after_replace_latest_resolution() -> None:
    source, plan = _first_last_plan(DuplicatePolicy.REPLACE_LATEST)

    validate_plan_for_descriptor(plan, source.descriptor)


def test_replace_latest_requires_ingestion_time_for_a_complete_key() -> None:
    with pytest.raises(ValueError, match="ingestion_time_field"):
        TemporalTableDescriptor(
            time_field="ts",
            timezone="UTC",
            precision=TimestampPrecision.NANOSECOND,
            series_key_fields=("symbol",),
            tag_fields=("venue",),
            value_fields=("price",),
            ingestion_time_field=None,
            duplicate_policy=DuplicatePolicy.REPLACE_LATEST,
            ordering="unspecified",
        )


def test_preserve_policy_does_not_silently_resolve_duplicate_rows() -> None:
    source, plan = _first_last_plan(DuplicatePolicy.PRESERVE)
    request = TemporalExecutionRequest(TARGET, plan, None, "duplicate-policy", None)

    with pytest.raises(TemporalExtensionError):
        PolarsTemporalExecutor(source).execute(request)
