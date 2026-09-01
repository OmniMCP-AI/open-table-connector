from __future__ import annotations

import pytest
from open_table_connector.formulas import (
    FIELD_READ,
    GRID_READ,
    GRID_RECALCULATE,
    CalculationState,
    CalculationTrigger,
    FieldFormulaObservation,
    FieldFormulaValueObservation,
    FormulaCapabilityDetails,
    FormulaCapabilitySet,
    FormulaCell,
    FormulaErrorValue,
    FormulaExpression,
    FormulaMutation,
    FormulaRecordValue,
    FormulaValue,
    FormulaValueCell,
    GridFormulaObservation,
    GridFormulaValueObservation,
    IdempotencyStrength,
    MutationAtomicity,
    RecalculationObservation,
    RevisionEnforcement,
)

HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64


def test_grid_formula_observation_is_sparse_and_round_trips() -> None:
    observation = GridFormulaObservation(
        worksheet_id="17",
        requested_range="A1:B2",
        formulas=(FormulaCell("A1", FormulaExpression("=B1+1", "google-sheets-a1")),),
        observed_revision=HASH_A,
    )

    assert GridFormulaObservation.from_wire(observation.to_wire()) == observation
    assert [cell.address for cell in observation.formulas] == ["A1"]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), object()])
def test_formula_values_reject_non_json_or_non_finite_values(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        FormulaValue.from_python(value)


def test_provider_error_values_are_data_and_record_ids_are_stable() -> None:
    observation = FieldFormulaValueObservation(
        table_uri="airtable://app/orders",
        field_id="fld-margin",
        field_name="gross_margin",
        values=(
            FormulaRecordValue("rec-1", FormulaValue.provider_error(FormulaErrorValue("DIVIDE_BY_ZERO"))),
        ),
        calculation_state=CalculationState.PROVIDER_CURRENT,
        calculation_trigger=CalculationTrigger.PROVIDER_READ,
        dependency_scope="provider_dynamic",
        observed_revision=HASH_A,
    )

    restored = FieldFormulaValueObservation.from_wire(observation.to_wire())
    assert restored == observation
    assert restored.values[0].record_id == "rec-1"
    assert restored.values[0].value.to_python() == {"provider_error": {"code": "DIVIDE_BY_ZERO"}}


def test_observations_require_non_empty_revisions() -> None:
    with pytest.raises(ValueError, match="observed_revision"):
        GridFormulaObservation("17", "A1", (), "")

    with pytest.raises(ValueError, match="observed_revision"):
        FieldFormulaObservation(
            table_uri="airtable://app/orders",
            field_id="fld-margin",
            field_name="gross_margin",
            expression=FormulaExpression("price-cost", "maybe-base"),
            result_type=None,
            observed_revision=" ",
        )


def test_grid_and_field_value_observations_reject_duplicates_and_non_provider_dynamic_scope() -> None:
    with pytest.raises(ValueError, match="duplicate cell"):
        GridFormulaValueObservation(
            worksheet_id="17",
            requested_range="A1:B2",
            values=(
                FormulaValueCell("A1", FormulaValue.from_python(1)),
                FormulaValueCell("A1", FormulaValue.from_python(2)),
            ),
            calculation_state=CalculationState.CACHED,
            calculation_trigger=CalculationTrigger.STORED_CACHE,
            dependency_scope="provider_dynamic",
            observed_revision=HASH_A,
        )

    with pytest.raises(ValueError, match="provider_dynamic"):
        GridFormulaValueObservation(
            worksheet_id="17",
            requested_range="A1:B2",
            values=(FormulaValueCell("A1", FormulaValue.from_python(1)),),
            calculation_state=CalculationState.CACHED,
            calculation_trigger=CalculationTrigger.STORED_CACHE,
            dependency_scope="worksheet",
            observed_revision=HASH_A,
        )

    with pytest.raises(ValueError, match="duplicate record"):
        FieldFormulaValueObservation(
            table_uri="airtable://app/orders",
            field_id="fld-margin",
            field_name="gross_margin",
            values=(
                FormulaRecordValue("rec-1", FormulaValue.from_python(1)),
                FormulaRecordValue("rec-1", FormulaValue.from_python(2)),
            ),
            calculation_state=CalculationState.PROVIDER_CURRENT,
            calculation_trigger=CalculationTrigger.PROVIDER_READ,
            dependency_scope="provider_dynamic",
            observed_revision=HASH_A,
        )


def test_formula_capability_set_rejects_duplicates_mismatches_and_empty_recalc_scopes() -> None:
    details = FormulaCapabilityDetails(
        target_kind="grid",
        dialects=("google-sheets-a1",),
        max_cells_per_operation=100,
        max_expression_bytes=1024,
        recalculation_scopes=("range",),
        calculation_states=(CalculationState.PROVIDER_CURRENT, CalculationState.CACHED),
        mutation_atomicity=MutationAtomicity.ATOMIC,
        revision_enforcement=RevisionEnforcement.CHECKED,
        idempotency_strength=IdempotencyStrength.HOST_LEDGER,
    )

    capability_set = FormulaCapabilitySet((GRID_READ, GRID_RECALCULATE), details)
    assert capability_set.to_wire()["details"]["target_kind"] == "grid"

    with pytest.raises(ValueError, match="duplicate capability"):
        FormulaCapabilitySet((GRID_READ, GRID_READ), details)

    with pytest.raises(ValueError, match="target kind"):
        FormulaCapabilitySet((FIELD_READ,), details)

    with pytest.raises(ValueError, match="recalculation"):
        FormulaCapabilitySet(
            (GRID_RECALCULATE,),
            FormulaCapabilityDetails(
                target_kind="grid",
                dialects=("google-sheets-a1",),
                max_cells_per_operation=100,
                max_expression_bytes=1024,
                recalculation_scopes=(),
                calculation_states=(CalculationState.UNKNOWN,),
                mutation_atomicity=MutationAtomicity.UNKNOWN,
                revision_enforcement=RevisionEnforcement.UNAVAILABLE,
                idempotency_strength=IdempotencyStrength.PROVIDER,
            ),
        )

    with pytest.raises(ValueError, match="FORMULA_DIALECTS"):
        FormulaCapabilityDetails(
            target_kind="field",
            dialects=("sql",),
            max_cells_per_operation=None,
            max_expression_bytes=1024,
            recalculation_scopes=("field",),
            calculation_states=(CalculationState.UNKNOWN,),
            mutation_atomicity=MutationAtomicity.UNKNOWN,
            revision_enforcement=RevisionEnforcement.UNAVAILABLE,
            idempotency_strength=IdempotencyStrength.RECONCILED,
        )


def test_formula_mutation_requires_count_consistency() -> None:
    observation = GridFormulaObservation(
        worksheet_id="17",
        requested_range="A1:B2",
        formulas=(
            FormulaCell("A1", FormulaExpression("=1", "google-sheets-a1")),
            FormulaCell("A2", FormulaExpression("=2", "google-sheets-a1")),
        ),
        observed_revision=HASH_A,
    )

    mutation = FormulaMutation(
        target_kind="grid",
        affected_count=2,
        formula_observation=observation,
        revision_before=None,
        revision_after=HASH_B,
    )
    assert FormulaMutation.from_wire(mutation.to_wire()) == mutation

    with pytest.raises(ValueError, match="affected_count"):
        FormulaMutation(
            target_kind="grid",
            affected_count=1,
            formula_observation=observation,
            revision_before=None,
            revision_after=HASH_B,
        )

    with pytest.raises(ValueError, match="affected_count"):
        FormulaMutation(
            target_kind="field",
            affected_count=2,
            formula_observation=FieldFormulaObservation(
                table_uri="airtable://app/orders",
                field_id="fld-margin",
                field_name="gross_margin",
                expression=FormulaExpression("price-cost", "maybe-base"),
                result_type="number",
                observed_revision=HASH_A,
            ),
            revision_before=HASH_A,
            revision_after=HASH_B,
        )


def test_recalculation_observation_requires_consistent_scope_and_target_family() -> None:
    observation = RecalculationObservation(
        target_kind="grid",
        requested_scope="range",
        effective_scope="worksheet",
        revision_before=HASH_A,
        revision_after=HASH_B,
        provider_status="queued",
        calculation_state=CalculationState.UNKNOWN,
        verification="unavailable",
        value_observation=None,
    )

    assert RecalculationObservation.from_wire(observation.to_wire()) == observation

    with pytest.raises(ValueError, match="scope"):
        RecalculationObservation(
            target_kind="grid",
            requested_scope="field",
            effective_scope="worksheet",
            revision_before=HASH_A,
            revision_after=HASH_B,
            provider_status="queued",
            calculation_state=CalculationState.UNKNOWN,
            verification="unavailable",
            value_observation=None,
        )

    with pytest.raises(ValueError, match="verification"):
        RecalculationObservation(
            target_kind="field",
            requested_scope="field",
            effective_scope="table",
            revision_before=HASH_A,
            revision_after=HASH_B,
            provider_status="done",
            calculation_state=CalculationState.PROVIDER_CURRENT,
            verification="passed",
            value_observation=None,
        )
