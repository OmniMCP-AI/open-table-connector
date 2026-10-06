from __future__ import annotations

import pytest


def test_recipe_roundtrip_closed_envelope():
    from open_table_connector.spreadsheets.recipes import LayoutRecipe, parse_recipe

    payload = {"schema": "otc.spreadsheet-recipe/1.0", "version": "1.0", "requirements": ["spreadsheet.range.style/1.0"], "operations": [{"operation_id": "range.style", "target_key": "Report", "arguments": {"address": "A1", "bold": True}}]}
    recipe = parse_recipe(payload)
    assert recipe.to_wire() == payload
    assert isinstance(recipe, LayoutRecipe)


def test_10001_operations_reject():
    from open_table_connector.spreadsheets.recipes import parse_recipe

    operation = {"operation_id": "range.style", "target_key": "Report", "arguments": {"address": "A1"}}
    with pytest.raises(ValueError, match="10000"):
        parse_recipe({"schema": "otc.spreadsheet-recipe/1.0", "version": "1.0", "requirements": [], "operations": [operation] * 10001})


def test_requirements_recomputed_not_trusted():
    from open_table_connector.spreadsheets.recipes import parse_recipe

    operation = {"operation_id": "range.style", "target_key": "Report", "arguments": {"address": "A1"}}
    with pytest.raises(ValueError, match="requirements"):
        parse_recipe({"schema": "otc.spreadsheet-recipe/1.0", "version": "1.0", "requirements": [], "operations": [operation]})


def test_no_values_formulas_assets_in_export():
    from open_table_connector.spreadsheets.recipes import parse_recipe

    operation = {"operation_id": "range.write", "target_key": "Report", "arguments": {"address": "A1", "values": [[1]]}}
    with pytest.raises(ValueError, match="values"):
        parse_recipe({"schema": "otc.spreadsheet-recipe/1.0", "version": "1.0", "requirements": ["spreadsheet.range.write/1.0"], "operations": [operation]})
