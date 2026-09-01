from __future__ import annotations

import json
from copy import deepcopy

import pytest
from open_table_connector.formulas import (
    CalculationState,
    CalculationTrigger,
    FieldFormulaObservation,
    FieldFormulaValueObservation,
    FormulaExpression,
    FormulaMutation,
    FormulaRecordValue,
    FormulaValue,
    FormulaValueCell,
    GridFormulaObservation,
    GridFormulaValueObservation,
    RecalculationObservation,
    formula_observation_from_wire,
    formula_observation_hash,
    formula_operation_from_wire,
)

HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64


def test_formula_observation_hash_is_canonical_for_reordered_keys() -> None:
    observation = FieldFormulaValueObservation(
        table_uri="airtable://app/orders",
        field_id="fld-margin",
        field_name="gross_margin",
        values=(
            FormulaRecordValue("rec-1", FormulaValue.logical("date", "2026-09-01")),
            FormulaRecordValue("rec-2", FormulaValue.from_python({"a": [1, 2]})),
        ),
        calculation_state=CalculationState.CACHED,
        calculation_trigger=CalculationTrigger.STORED_CACHE,
        dependency_scope="provider_dynamic",
        observed_revision=HASH_A,
    )

    reordered = json.loads(json.dumps(observation.to_wire(), sort_keys=True))
    assert formula_observation_hash(observation) == formula_observation_hash(
        formula_observation_from_wire(reordered)
    )


def test_formula_observation_from_wire_dispatches_closed_unions() -> None:
    grid = GridFormulaObservation(
        worksheet_id="17",
        requested_range="A1:B2",
        formulas=(),
        observed_revision=HASH_A,
    )
    field_values = FieldFormulaValueObservation(
        table_uri="airtable://app/orders",
        field_id="fld-margin",
        field_name="gross_margin",
        values=(FormulaRecordValue("rec-1", FormulaValue.from_python(True)),),
        calculation_state=CalculationState.PROVIDER_CURRENT,
        calculation_trigger=CalculationTrigger.PROVIDER_READ,
        dependency_scope="provider_dynamic",
        observed_revision=HASH_B,
    )

    assert formula_observation_from_wire(grid.to_wire()) == grid
    assert formula_observation_from_wire(field_values.to_wire()) == field_values


def test_formula_operation_from_wire_dispatches_mutation_and_recalculation() -> None:
    mutation = FormulaMutation(
        target_kind="field",
        affected_count=1,
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
    recalculation = RecalculationObservation(
        target_kind="field",
        requested_scope="field",
        effective_scope="field",
        revision_before=HASH_A,
        revision_after=HASH_B,
        provider_status="done",
        calculation_state=CalculationState.PROVIDER_CURRENT,
        verification="passed",
        value_observation=FieldFormulaValueObservation(
            table_uri="airtable://app/orders",
            field_id="fld-margin",
            field_name="gross_margin",
            values=(FormulaRecordValue("rec-1", FormulaValue.from_python(3)),),
            calculation_state=CalculationState.PROVIDER_CURRENT,
            calculation_trigger=CalculationTrigger.EXPLICIT_RECALCULATION,
            dependency_scope="provider_dynamic",
            observed_revision=HASH_B,
        ),
    )

    assert formula_operation_from_wire(mutation.to_wire()) == mutation
    assert formula_operation_from_wire(recalculation.to_wire()) == recalculation


def test_from_wire_rejects_extra_or_missing_keys_recursively() -> None:
    observation = GridFormulaValueObservation(
        worksheet_id="17",
        requested_range="A1:B2",
        values=(FormulaValueCell("A1", FormulaValue.from_python(1)),),
        calculation_state=CalculationState.CACHED,
        calculation_trigger=CalculationTrigger.STORED_CACHE,
        dependency_scope="provider_dynamic",
        observed_revision=HASH_A,
    )
    extra_key = deepcopy(observation.to_wire())
    extra_key["surplus"] = True

    with pytest.raises(ValueError, match="keys mismatch"):
        GridFormulaValueObservation.from_wire(extra_key)

    missing_nested = deepcopy(observation.to_wire())
    del missing_nested["values"][0]["value"]["kind"]

    with pytest.raises(ValueError, match="keys mismatch"):
        formula_observation_from_wire(missing_nested)


def test_formula_operation_from_wire_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        formula_operation_from_wire({"kind": "formula.unknown"})
