from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from open_table_connector.contract import ConnectorErrorCode

ROOT = Path(__file__).parents[3]


def test_every_vendored_temporal_fixture_matches_its_closed_schema() -> None:
    fixture_root = ROOT / "specification/fixtures/timeseries/v1"
    plans = ("scan-range", "latest", "as-of", "bucket-aggregate", "gap-fill")
    pairs = [
        (
            json.loads((fixture_root / f"{name}.json").read_text(encoding="utf-8"))["plan"],
            "portable-temporal-plan-v1.schema.json",
        )
        for name in plans
    ]
    pairs.append(
        (
            json.loads((fixture_root / "temporal-receipt.json").read_text(encoding="utf-8")),
            "temporal-receipt-v1.schema.json",
        )
    )
    lifecycle = json.loads(
        (fixture_root / "managed-lifecycle.json").read_text(encoding="utf-8")
    )
    for name in ("stage", "commit", "readback", "abort"):
        pairs.append((lifecycle[name], f"managed-{name}-receipt-v1.schema.json"))
    for fixture, schema_name in pairs:
        schema = json.loads(
            (ROOT / "specification/schemas" / schema_name).read_text(encoding="utf-8")
        )
        jsonschema.Draft202012Validator(schema).validate(fixture)


def test_plan_schema_rejects_count_with_value_field() -> None:
    fixture_root = ROOT / "specification/fixtures/timeseries/v1"
    fixture = json.loads((fixture_root / "bucket-aggregate.json").read_text(encoding="utf-8"))
    fixture["plan"]["operation"]["measures"][1]["value_field"] = "price"
    schema = json.loads(
        (ROOT / "specification/schemas/portable-temporal-plan-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(fixture["plan"])


def test_connector_error_schema_enum_matches_python() -> None:
    schema = json.loads(
        (ROOT / "specification/schemas/connector-error-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert set(schema["properties"]["code"]["enum"]) == {
        item.value for item in ConnectorErrorCode
    }


def test_provider_evidence_documents_match_closed_schema() -> None:
    schema = json.loads(
        (ROOT / "specification/schemas/provider-evidence-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    validator = jsonschema.Draft202012Validator(schema)
    evidence_root = ROOT / "specification/evidence/providers"
    documents = sorted(evidence_root.glob("*.json"))
    assert documents
    for path in documents:
        document = json.loads(path.read_text(encoding="utf-8"))
        validator.validate(document)
        assert document["provider"] == path.stem
        if document["tier"] == "recording_stub":
            assert document["live_run"] is None
