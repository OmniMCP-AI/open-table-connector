from __future__ import annotations


def test_dry_run_no_mutation():
    from open_table_connector.sdk.recipes import apply_recipe
    from open_table_connector.spreadsheets.recipes import parse_recipe
    from open_table_connector.contract import ExecutionOptions

    recipe = parse_recipe({"schema": "otc.spreadsheet-recipe/1.0", "version": "1.0", "requirements": ["spreadsheet.range.style/1.0"], "operations": [{"operation_id": "range.style", "target_key": "Report", "arguments": {"address": "A1", "bold": True}}]})
    result = apply_recipe(object(), "file:///tmp/book.xlsx", recipe, ExecutionOptions(dry_run=True))
    assert result.outcome.value in {"planned", "rejected"}


def test_recipe_publishes_once_and_can_be_read_back(tmp_path):
    from open_table_connector.contract import ExecutionOptions
    from open_table_connector.local_files import LocalFilesConnector
    from open_table_connector.sdk import Client, ConnectorRegistry
    from open_table_connector.sdk.recipes import apply_recipe
    from open_table_connector.spreadsheets import parse_recipe

    uri = (tmp_path / "recipe.xlsx").as_uri()
    recipe = parse_recipe({"schema": "otc.spreadsheet-recipe/1.0", "version": "1.0",
        "requirements": ["spreadsheet.range.style/1.0"], "operations": [
        {"operation_id": "range.style", "target_key": "Report", "arguments": {"address": "A1", "bold": True}}]})
    with Client(registry=ConnectorRegistry([LocalFilesConnector()])) as client:
        book = client.workbook.create(uri)
        book.worksheet.create("Report").range("A1").write([["literal"]])
        book.write()
        result = apply_recipe(client, uri, recipe, ExecutionOptions())
        assert result.commit.value == "committed"
        from openpyxl import load_workbook
        observed = load_workbook(tmp_path / "recipe.xlsx")
        assert observed["Report"]["A1"].font.bold is True
        observed.close()
