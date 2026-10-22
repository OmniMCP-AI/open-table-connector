from __future__ import annotations

from jsonschema import validate
from open_table_connector.mobile_table.models import (
    MobileCapabilities,
    MobileField,
    MobileInspection,
    MobileReadPage,
    MobileRecord,
    MobileUpdateResult,
)

from .conftest import load_fixture, load_schema

FIXTURES = {
    "capabilities-supported.json": "mobile-table-capabilities-v1.schema.json",
    "capabilities-unknown.json": "mobile-table-capabilities-v1.schema.json",
    "inspect-base.json": "mobile-table-inspect-v1.schema.json",
    "inspect-sheet-read-only.json": "mobile-table-inspect-v1.schema.json",
    "read-first-page.json": "mobile-table-read-v1.schema.json",
    "read-continuation.json": "mobile-table-read-v1.schema.json",
    "read-empty.json": "mobile-table-read-v1.schema.json",
    "update-success.json": "mobile-table-update-v1.schema.json",
    "update-conflict.json": "mobile-table-update-v1.schema.json",
    "update-unknown.json": "mobile-table-update-v1.schema.json",
}


def test_all_shared_fixtures_validate_against_closed_schemas() -> None:
    for fixture_name, schema_name in FIXTURES.items():
        validate(load_fixture(fixture_name), load_schema(schema_name))


def test_record_round_trip_preserves_json_scalar_distinctions() -> None:
    record = MobileRecord(
        record_id="rec_123",
        record_revision="sha256:record",
        values={
            "missing": None,
            "disabled": False,
            "count": 0,
            "empty": "",
            "numeric_text": "0012",
            "ratio": 1.25,
        },
    )

    restored = MobileRecord.from_wire(record.to_wire())

    assert restored == record
    assert restored.values["missing"] is None
    assert restored.values["disabled"] is False
    assert restored.values["count"] == 0
    assert restored.values["empty"] == ""
    assert restored.values["numeric_text"] == "0012"


def test_response_models_round_trip_without_opening_wire_objects() -> None:
    field = MobileField("status", "Status", "string", False, True, None)
    inspection = MobileInspection(
        table_uri="https://example.invalid/table/123",
        mode="base",
        schema_fingerprint="sha256:schema",
        row_count=1,
        source_revision="sha256:source",
        coordinate_convention={"mode": "base", "record_id_field": "id", "key_fields": []},
        fields=(field,),
    )
    page = MobileReadPage(
        table_uri=inspection.table_uri,
        mode="base",
        source_revision=inspection.source_revision,
        fields=(field,),
        rows=(MobileRecord("rec_123", "sha256:record", {"status": "Open"}),),
        next_page_token="opaque.cursor/1",
    )
    capabilities = MobileCapabilities.from_wire(load_fixture("capabilities-supported.json"))
    update = MobileUpdateResult.from_wire(load_fixture("update-success.json"))

    assert MobileCapabilities.from_wire(capabilities.to_wire()) == capabilities
    assert MobileInspection.from_wire(inspection.to_wire()) == inspection
    assert MobileReadPage.from_wire(page.to_wire()) == page
    assert MobileUpdateResult.from_wire(update.to_wire()) == update


def test_unknown_response_fields_are_ignored_by_models() -> None:
    payload = load_fixture("read-first-page.json")
    payload["provider_extension"] = {"ignored": True}
    payload["rows"][0]["future_field"] = "ignored"

    page = MobileReadPage.from_wire(payload)

    assert page.rows[0].record_id == "rec_123"
    assert "provider_extension" not in page.to_wire()


def test_record_values_redact_secret_looking_keys() -> None:
    record = MobileRecord("rec_secret", "rev-1", {"status": "Open", "api_token": "private"})

    assert record.to_wire()["values"] == {"status": "Open"}
