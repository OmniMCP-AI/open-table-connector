from __future__ import annotations

from open_table_connector.formulas import FieldFormulaValueObservation, formula_observation_from_wire

from .field_cases import load_field_fixture


def test_field_value_fixture_covers_typed_values_and_stable_record_ids() -> None:
    observation = formula_observation_from_wire(load_field_fixture("value-observations.json"))

    assert isinstance(observation, FieldFormulaValueObservation)
    assert [record.record_id for record in observation.values] == [
        "rec-null",
        "rec-nested",
        "rec-bool",
        "rec-int",
        "rec-float",
        "rec-string",
        "rec-date",
        "rec-time",
        "rec-error",
    ]
    assert [record.value.kind for record in observation.values] == [
        "null",
        "mapping",
        "boolean",
        "integer",
        "number",
        "string",
        "logical",
        "logical",
        "provider_error",
    ]
    assert observation.dependency_scope == "provider_dynamic"
    assert observation.calculation_trigger.value == "provider_read"


def test_field_observation_fixture_preserves_native_expression_and_result_type() -> None:
    observation = formula_observation_from_wire(load_field_fixture("field-observation.json"))

    assert observation.expression.dialect == "maybe-base"
    assert "IF(" in observation.expression.text
    assert observation.result_type == "number"
    assert observation.field_id == "fld-gross-margin"
