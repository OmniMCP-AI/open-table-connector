from __future__ import annotations

import pyarrow as pa
import pytest

from open_table_connector.timeseries import (
    DuplicatePolicy,
    TemporalOrdering,
    TemporalTableDescriptor,
    TimestampPrecision,
    descriptor_from_wire,
    temporal_descriptor_hash,
)


def ticks_descriptor() -> TemporalTableDescriptor:
    return TemporalTableDescriptor(
        time_field="ts",
        timezone="UTC",
        precision=TimestampPrecision.NANOSECOND,
        series_key_fields=("symbol",),
        tag_fields=("venue",),
        value_fields=("price",),
        ingestion_time_field="received_at",
        duplicate_policy=DuplicatePolicy.REPLACE_LATEST,
        ordering=TemporalOrdering.UNSPECIFIED,
    )


def ticks_schema() -> pa.Schema:
    return pa.schema(
        [
            pa.field("ts", pa.timestamp("ns", tz="UTC"), nullable=False),
            pa.field("symbol", pa.string(), nullable=False),
            pa.field("venue", pa.string()),
            pa.field("price", pa.float64()),
            pa.field("received_at", pa.timestamp("ns", tz="UTC"), nullable=False),
        ]
    )


def test_descriptor_round_trips_as_a_closed_document() -> None:
    descriptor = ticks_descriptor()

    assert descriptor_from_wire(descriptor.to_wire()) == descriptor
    assert list(descriptor.to_wire()) == [
        "time_field",
        "timezone",
        "precision",
        "series_key_fields",
        "tag_fields",
        "value_fields",
        "ingestion_time_field",
        "duplicate_policy",
        "ordering",
    ]


def test_descriptor_rejects_unknown_and_overlapping_fields() -> None:
    wire = ticks_descriptor().to_wire()
    wire["provider"] = "timescale"
    with pytest.raises(ValueError, match="unknown descriptor fields"):
        descriptor_from_wire(wire)

    with pytest.raises(ValueError, match="declared in more than one role"):
        TemporalTableDescriptor(
            time_field="ts",
            timezone="UTC",
            precision=TimestampPrecision.NANOSECOND,
            series_key_fields=("symbol",),
            tag_fields=("symbol",),
            value_fields=("price",),
            ingestion_time_field=None,
            duplicate_policy=DuplicatePolicy.REJECT,
            ordering=TemporalOrdering.STRICT,
        )


def test_descriptor_hash_covers_every_descriptor_field_and_arrow_field_order() -> None:
    descriptor = ticks_descriptor()
    schema = ticks_schema()
    baseline = temporal_descriptor_hash(descriptor, schema)

    assert baseline == temporal_descriptor_hash(descriptor, schema)
    assert baseline.startswith("sha256:")
    assert baseline != temporal_descriptor_hash(
        TemporalTableDescriptor(
            **{
                **descriptor.to_wire(),
                "ordering": TemporalOrdering.NONDECREASING,
            }
        ),
        schema,
    )
    assert baseline != temporal_descriptor_hash(
        descriptor,
        pa.schema(list(reversed(schema))),
    )


def test_descriptor_rejects_invalid_timezone_and_missing_schema_fields() -> None:
    with pytest.raises(ValueError, match="IANA timezone"):
        TemporalTableDescriptor(
            time_field="ts",
            timezone="not/a-zone",
            precision=TimestampPrecision.SECOND,
            series_key_fields=(),
            tag_fields=(),
            value_fields=("value",),
            ingestion_time_field=None,
            duplicate_policy=DuplicatePolicy.PRESERVE,
            ordering=TemporalOrdering.UNSPECIFIED,
        )

    with pytest.raises(ValueError, match="missing declared fields"):
        temporal_descriptor_hash(ticks_descriptor(), pa.schema([pa.field("ts", pa.string())]))
