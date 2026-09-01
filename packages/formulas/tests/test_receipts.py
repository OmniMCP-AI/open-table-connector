from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from open_table_connector.formulas import FormulaReceiptDetails

HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
HASH_C = "sha256:" + "c" * 64
HASH_D = "sha256:" + "d" * 64
ROOT = Path(__file__).parents[3]


def test_formula_receipt_contains_hashes_not_formula_text() -> None:
    details = FormulaReceiptDetails.for_grid_set(
        target="gsheets://spreadsheet-id",
        selector="A1:B2",
        capability="formula.grid.set/1.0",
        dialect="google-sheets-a1",
        expression_sha256=HASH_A,
        observation_sha256=HASH_B,
        affected_count=4,
        revision_before=HASH_C,
        revision_after=HASH_D,
        mutation_atomicity="atomic",
        revision_enforcement="checked",
        verification="formula_text_readback",
    )
    payload = details.to_wire()

    assert payload["schema"] == "otc.formula-receipt-details/v1"
    assert payload["copy_fill_policy"] == "top_left"
    assert "expression" not in json.dumps(payload).casefold()


def test_formula_receipts_reject_unsafe_wire_fields_and_exception_objects() -> None:
    with pytest.raises(ValueError, match="exception objects"):
        FormulaReceiptDetails(
            target_kind="grid",
            table_mode="sheet",
            target="gsheets://spreadsheet-id",
            selector="A1",
            capability="formula.grid.read/1.0",
            dialect="google-sheets-a1",
            observed_count=1,
            safe_details={"provider_error": RuntimeError("=SUM\\(A:A\\)")},
        )

    payload = FormulaReceiptDetails.for_grid_read(
        target="gsheets://spreadsheet-id",
        selector="A1:B2",
        capability="formula.grid.read/1.0",
        dialect="google-sheets-a1",
        observation_sha256=HASH_A,
        observed_count=1,
        revision_after=HASH_B,
    ).to_wire()

    for forbidden_key in (
        "expression",
        "formula",
        "value",
        "values",
        "credential",
        "token",
    ):
        payload[forbidden_key] = "=IMPORTRANGE(\"https://example.com\", \"A1\")"
        with pytest.raises(ValueError, match="forbidden"):
            FormulaReceiptDetails.from_wire(payload)
        payload.pop(forbidden_key)


def test_formula_receipts_reject_url_bearing_provider_receipt_references() -> None:
    with pytest.raises(ValueError, match="provider_receipt_ref.*URL"):
        FormulaReceiptDetails(
            target_kind="grid",
            table_mode="sheet",
            target="gsheets://spreadsheet-id",
            selector="A1",
            capability="formula.grid.read/1.0",
            dialect="google-sheets-a1",
            observation_sha256=HASH_A,
            observed_count=1,
            provider_receipt_ref="https://provider.example/receipts/123",
        )

    details = FormulaReceiptDetails(
        target_kind="grid",
        table_mode="sheet",
        target="gsheets://spreadsheet-id",
        selector="A1",
        capability="formula.grid.read/1.0",
        dialect="google-sheets-a1",
        observation_sha256=HASH_A,
        observed_count=1,
        provider_receipt_ref="receipt-123",
    )
    assert details.to_wire()["provider_receipt_ref"] == "receipt-123"


def test_formula_receipts_require_calculation_metadata_for_value_evidence() -> None:
    with pytest.raises(ValueError, match="calculation_state"):
        FormulaReceiptDetails.for_grid_values_read(
            target="gsheets://spreadsheet-id",
            selector="A1:B2",
            capability="formula.grid.values.read/1.0",
            dialect="google-sheets-a1",
            observation_sha256=HASH_A,
            value_observation_sha256=HASH_B,
            observed_count=2,
            revision_after=HASH_C,
            calculation_state=None,
            calculation_trigger="provider_read",
            dependency_scope="provider_dynamic",
        )

    with pytest.raises(ValueError, match="provider_dynamic"):
        FormulaReceiptDetails.for_field_values_read(
            target="maybe://orders",
            selector="fld-1",
            capability="formula.field.values.read/1.0",
            dialect="maybe-base",
            observation_sha256=HASH_A,
            value_observation_sha256=HASH_B,
            observed_count=2,
            revision_after=HASH_C,
            calculation_state="provider_current",
            calculation_trigger="provider_read",
            dependency_scope="worksheet",
        )


def test_formula_set_receipts_require_readback_hashes_and_forbid_value_verification_claims() -> None:
    with pytest.raises(ValueError, match="expression_sha256"):
        FormulaReceiptDetails.for_field_set(
            target="maybe://orders",
            selector="fld-1",
            capability="formula.field.set/1.0",
            dialect="maybe-base",
            expression_sha256="",
            observation_sha256=HASH_A,
            affected_count=1,
            revision_before=HASH_B,
            revision_after=HASH_C,
            mutation_atomicity="atomic",
            revision_enforcement="checked",
            verification="formula_text_readback",
        )

    with pytest.raises(ValueError, match="calculated-value"):
        FormulaReceiptDetails.for_grid_set(
            target="gsheets://spreadsheet-id",
            selector="A1:B2",
            capability="formula.grid.set/1.0",
            dialect="google-sheets-a1",
            expression_sha256=HASH_A,
            observation_sha256=HASH_B,
            affected_count=4,
            revision_before=HASH_C,
            revision_after=HASH_D,
            mutation_atomicity="atomic",
            revision_enforcement="checked",
            verification="passed",
        )


def test_formula_receipt_schema_accepts_runtime_safe_details_round_trip() -> None:
    details = FormulaReceiptDetails(
        target_kind="grid",
        table_mode="sheet",
        target="gsheets://spreadsheet-id",
        selector="A1:B2",
        capability="formula.grid.read/1.0",
        dialect="google-sheets-a1",
        observation_sha256=HASH_A,
        observed_count=1,
        revision_after=HASH_B,
        safe_details={
            "status": "committed",
            "target_kind": "grid",
            "revision_hash": HASH_A,
            "provider_status_code": 200,
            "provider_status": "dropped",
            "nested": {"field_id": "fld-1"},
        },
    )
    payload = details.to_wire()
    schema = json.loads(
        (
            ROOT / "specification/schemas/formula-receipt-details-v1.schema.json"
        ).read_text(encoding="utf-8")
    )

    assert payload["safe_details"] == {
        "status": "committed",
        "target_kind": "grid",
        "revision_hash": HASH_A,
        "provider_status_code": 200,
    }
    jsonschema.Draft202012Validator(schema).validate(payload)
    assert FormulaReceiptDetails.from_wire(payload).safe_details == payload["safe_details"]
