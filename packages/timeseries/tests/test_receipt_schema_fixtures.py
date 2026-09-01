from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError
from open_table_connector.timeseries import (
    ManagedAbortReceipt,
    ManagedCommitReceipt,
    ManagedReadbackReceipt,
    ManagedStageReceipt,
    TemporalReceipt,
)

ROOT = Path(__file__).parents[3]
SCHEMA_ROOT = ROOT / "specification" / "schemas"
FIXTURE_ROOT = ROOT / "specification" / "fixtures" / "timeseries" / "v1"
SCHEMA_NAMES = (
    "temporal-receipt-v1.schema.json",
    "managed-stage-receipt-v1.schema.json",
    "managed-commit-receipt-v1.schema.json",
    "managed-readback-receipt-v1.schema.json",
    "managed-abort-receipt-v1.schema.json",
)


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_receipt_schemas_are_closed_valid_draft_2020_12_documents() -> None:
    for name in SCHEMA_NAMES:
        schema = load(SCHEMA_ROOT / name)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        Draft202012Validator.check_schema(schema)


def test_temporal_receipt_fixture_validates_and_round_trips() -> None:
    wire = load(FIXTURE_ROOT / "temporal-receipt.json")
    schema = load(SCHEMA_ROOT / "temporal-receipt-v1.schema.json")

    Draft202012Validator(schema).validate(wire)
    assert TemporalReceipt.from_wire(wire).to_wire() == wire


def test_lifecycle_fixture_validates_round_trips_and_shares_identities() -> None:
    fixture = load(FIXTURE_ROOT / "managed-lifecycle.json")
    cases = (
        ("stage", ManagedStageReceipt, "managed-stage-receipt-v1.schema.json"),
        ("commit", ManagedCommitReceipt, "managed-commit-receipt-v1.schema.json"),
        ("readback", ManagedReadbackReceipt, "managed-readback-receipt-v1.schema.json"),
        ("abort", ManagedAbortReceipt, "managed-abort-receipt-v1.schema.json"),
    )
    for key, receipt_type, schema_name in cases:
        wire = fixture[key]
        Draft202012Validator(load(SCHEMA_ROOT / schema_name)).validate(wire)
        assert receipt_type.from_wire(wire).to_wire() == wire

    assert fixture["stage"]["stage_id"] == fixture["commit"]["stage_id"]
    assert fixture["stage"]["stage_id"] == fixture["abort"]["stage_id"]
    assert fixture["commit"]["snapshot_id"] == fixture["readback"]["snapshot_id"]


@pytest.mark.parametrize("forbidden", ("ots_plan_hash", "acceptance", "credential", "raw_sql"))
def test_receipt_schemas_reject_ots_and_secret_fields(forbidden: str) -> None:
    wire = deepcopy(load(FIXTURE_ROOT / "managed-lifecycle.json")["commit"])
    wire[forbidden] = "forbidden"
    schema = load(SCHEMA_ROOT / "managed-commit-receipt-v1.schema.json")

    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(wire)
