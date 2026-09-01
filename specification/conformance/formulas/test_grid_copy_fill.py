from __future__ import annotations

import pytest
from open_table_connector.formulas import (
    GridFormulaObservation,
    GridFormulaValueObservation,
    formula_observation_from_wire,
)

from .grid_cases import (
    EXPECTED_GRID_CAPABILITIES,
    GRID_PROVIDER_IDS,
    grid_case_data_for_provider,
    load_grid_fixture,
    load_grid_provider_cases,
)


def test_grid_provider_cases_exist_for_every_matrix_provider() -> None:
    cases = load_grid_provider_cases()

    assert {case.provider_id for case in cases} == set(EXPECTED_GRID_CAPABILITIES)


@pytest.mark.parametrize("provider_id", tuple(EXPECTED_GRID_CAPABILITIES))
def test_provider_copy_fill_fixture_is_a_literal_two_by_three_document(provider_id: str) -> None:
    fixture = load_grid_fixture(provider_id)

    assert provider_id in GRID_PROVIDER_IDS
    assert fixture["copy_fill"]["range"] == "A1:C2"
    assert [cell["address"] for cell in fixture["copy_fill"]["expected"]] == [
        "A1",
        "B1",
        "C1",
        "A2",
        "B2",
        "C2",
    ]
    assert fixture["copy_fill"]["expected"][0]["text"] == fixture["copy_fill"]["source"]


def test_provider_copy_fill_fixture_preserves_relative_absolute_and_mixed_references() -> None:
    fixture = load_grid_fixture("google_sheets")
    formulas = {
        cell["address"]: cell["text"] for cell in fixture["copy_fill"]["expected"]
    }

    assert formulas == {
        "A1": "=B1+$C$1",
        "B1": "=C1+$C$1",
        "C1": "=D1+$C$1",
        "A2": "=B2+$C$1",
        "B2": "=C2+$C$1",
        "C2": "=D2+$C$1",
    }


def test_provider_fixture_covers_quoted_cross_sheet_and_external_formula_text() -> None:
    fixture = load_grid_fixture("maybe_sheet")
    formulas = {item["name"]: item["text"] for item in fixture["formula_text"]}

    assert formulas["quoted_reference"] == "='Quarter Plan'!$A2"
    assert formulas["provider_function"] == '=MAYBEFUNC("margin")'
    assert formulas["external_reference"] == '=IMPORT("https://api.example.test/revenue",A1)'


@pytest.mark.parametrize("provider_id", GRID_PROVIDER_IDS)
def test_provider_fixture_documents_decode_sparse_and_value_observations(provider_id: str) -> None:
    fixture = load_grid_fixture(provider_id)

    sparse = formula_observation_from_wire(fixture["sparse_observation"])
    values = formula_observation_from_wire(fixture["value_observation"])

    assert isinstance(sparse, GridFormulaObservation)
    assert [cell.address for cell in sparse.formulas] == ["A1", "C2"]
    assert isinstance(values, GridFormulaValueObservation)
    assert [cell.address for cell in values.values] == ["A1", "B1", "C1", "A2"]
    assert values.dependency_scope == "provider_dynamic"


def test_provider_case_data_uses_literal_copy_fill_and_value_documents() -> None:
    case = grid_case_data_for_provider("google_sheets")

    assert case.formula_range == "A1:C2"
    assert case.set_expression.text == "=B1+$C$1"
    assert [cell.expression.text for cell in case.expected_after_set.formulas] == [
        "=B1+$C$1",
        "=C1+$C$1",
        "=D1+$C$1",
        "=B2+$C$1",
        "=C2+$C$1",
        "=D2+$C$1",
    ]
    assert case.expected_values.calculation_trigger.value == "provider_read"


def test_grid_fixture_loader_rejects_unknown_provider() -> None:
    with pytest.raises(KeyError, match="unknown grid provider"):
        load_grid_fixture("not-a-provider")
