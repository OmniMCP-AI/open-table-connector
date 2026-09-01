from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pytest
from jsonschema import Draft202012Validator, ValidationError
from open_table_connector.timeseries import (
    TemporalTableDescriptor,
    descriptor_from_wire,
    plan_from_wire,
    temporal_descriptor_hash,
)

ROOT = Path(__file__).parents[3]
SCHEMA_ROOT = ROOT / "specification" / "schemas"
FIXTURE_ROOT = ROOT / "specification" / "fixtures" / "timeseries" / "v1"
PLAN_FIXTURES = (
    "as-of.json",
    "bucket-aggregate.json",
    "gap-fill.json",
    "latest.json",
    "scan-range.json",
)
ALL_FIXTURES = (
    "as-of.json",
    "bucket-aggregate.json",
    "gap-fill.json",
    "latest.json",
    "managed-lifecycle.json",
    "scan-range.json",
    "temporal-receipt.json",
)


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_published_schemas_are_valid_draft_2020_12_documents() -> None:
    for name in (
        "temporal-table-descriptor-v1.schema.json",
        "portable-temporal-plan-v1.schema.json",
    ):
        schema = load_json(SCHEMA_ROOT / name)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        Draft202012Validator.check_schema(schema)


def test_descriptor_fixture_shape_validates_and_hashes_with_arrow_schema() -> None:
    fixture = load_json(FIXTURE_ROOT / "scan-range.json")
    descriptor_wire = fixture["descriptor"]
    plan_wire = fixture["plan"]
    descriptor_schema = load_json(SCHEMA_ROOT / "temporal-table-descriptor-v1.schema.json")
    plan_schema = load_json(SCHEMA_ROOT / "portable-temporal-plan-v1.schema.json")

    Draft202012Validator(descriptor_schema).validate(descriptor_wire)
    Draft202012Validator(plan_schema).validate(plan_wire)
    descriptor = descriptor_from_wire(descriptor_wire)
    arrow_schema = pa.schema(
        [
                pa.field("ts", pa.timestamp("ns", tz="UTC")),
                pa.field("symbol", pa.string()),
            pa.field("venue", pa.string()),
            pa.field("price", pa.float64()),
            pa.field("size", pa.int64()),
                pa.field("received_at", pa.timestamp("ns", tz="UTC")),
        ]
    )
    assert isinstance(descriptor, TemporalTableDescriptor)
    assert plan_wire["descriptor_hash"] == temporal_descriptor_hash(descriptor, arrow_schema)


@pytest.mark.parametrize("name", PLAN_FIXTURES)
def test_every_golden_plan_validates_and_round_trips(name: str) -> None:
    fixture = load_json(FIXTURE_ROOT / name)
    plan_wire = fixture["plan"]
    schema = load_json(SCHEMA_ROOT / "portable-temporal-plan-v1.schema.json")

    Draft202012Validator(schema).validate(plan_wire)
    assert plan_from_wire(plan_wire).to_wire() == plan_wire


def test_plan_schema_rejects_unknown_fields_recursively() -> None:
    fixture = load_json(FIXTURE_ROOT / "scan-range.json")
    fixture["plan"]["operation"]["raw_sql"] = "select * from ticks"
    schema = load_json(SCHEMA_ROOT / "portable-temporal-plan-v1.schema.json")

    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(fixture["plan"])


def test_manifest_covers_fixture_bytes_in_lexical_order() -> None:
    manifest_path = FIXTURE_ROOT / "manifest.sha256"
    lines = manifest_path.read_text(encoding="utf-8").splitlines()
    assert [line.split("  ", 1)[1] for line in lines] == list(ALL_FIXTURES)

    for line in lines:
        expected, name = line.split("  ", 1)
        actual = hashlib.sha256((FIXTURE_ROOT / name).read_bytes()).hexdigest()
        assert expected == actual
