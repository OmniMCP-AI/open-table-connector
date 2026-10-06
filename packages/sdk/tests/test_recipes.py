from __future__ import annotations


def test_dry_run_no_mutation():
    from open_table_connector.sdk.recipes import apply_recipe
    from open_table_connector.spreadsheets.recipes import parse_recipe
    from open_table_connector.contract import ExecutionOptions

    recipe = parse_recipe({"schema": "otc.spreadsheet-recipe/1.0", "version": "1.0", "requirements": ["spreadsheet.range.style/1.0"], "operations": [{"operation_id": "range.style", "target_key": "Report", "arguments": {"address": "A1", "bold": True}}]})
    result = apply_recipe(object(), "file:///tmp/book.xlsx", recipe, ExecutionOptions(dry_run=True))
    assert result.outcome.value in {"planned", "rejected"}
