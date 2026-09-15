"""Public workbook conformance through the SDK rather than provider internals."""

import pytest
from open_table_connector.local_files import LocalFilesConnector
from open_table_connector.sdk import Client, ConnectorRegistry, OTCError
from open_table_connector.spreadsheets import CellFormat, CellStyle


@pytest.mark.parametrize(
    "operation",
    ["clear", "sort", "merge", "style", "format", "formula", "rename", "move", "delete"],
)
def test_local_general_operation_save_reopen(tmp_path, operation):
    client = Client(registry=ConnectorRegistry([LocalFilesConnector()]))
    uri = (tmp_path / "model.xlsx").as_uri()
    book = client.workbook.create(uri, profile="general/1.0")
    sheet = book.worksheet.create("Data")
    book.worksheet.create("Other")
    sheet.range("A1:B2").write([["b", "2"], ["a", "1"]])
    if operation == "clear":
        sheet.range("A1").clear()
    elif operation == "sort":
        sheet.range("A1:B2").sort()
    elif operation == "merge":
        sheet.range("D1:E1").merge()
    elif operation == "style":
        sheet.range("A1").style(CellStyle(bold=True))
    elif operation == "format":
        sheet.range("A1").format(CellFormat("text"))
    elif operation == "formula":
        sheet.formulas().set("C1", "=1+2")
    elif operation == "rename":
        sheet.rename("Renamed")
    elif operation == "move":
        sheet.move(1)
    elif operation == "delete":
        book.worksheet("Other").delete()
    result = book.write()
    assert result.commit.value == "committed"
    assert result.verification.value == "passed"
    reopened = client.workbook(uri)
    names = reopened.worksheet.list()
    if operation == "rename":
        assert names == ("Renamed", "Other")
    elif operation == "move":
        assert names == ("Other", "Data")
    elif operation == "delete":
        assert names == ("Data",)
    elif operation == "clear":
        assert reopened.worksheet("Data").range("A1").read().require_value() == [[None]]
    elif operation == "sort":
        assert reopened.worksheet("Data").range("A1").read().require_value() == [["a"]]
    elif operation == "formula":
        assert reopened.worksheet("Data").range("C1").read().require_value() == [["=1+2"]]


def test_unknown_operation_rejects_before_publish(tmp_path):
    client = Client(registry=ConnectorRegistry([LocalFilesConnector()]))
    path = tmp_path / "model.xlsx"
    book = client.workbook.create(path.as_uri(), profile="general/1.0")
    book.worksheet.create("Data")
    with pytest.raises(OTCError):
        book._queue("pivot.create", "Data", {})
    assert not path.exists()


def test_file_discovery_matches_workbook_dispatch_and_rejects_non_xlsx(tmp_path):
    connector = LocalFilesConnector()
    capabilities = {item.capability_id for item in connector.manifest.capabilities}
    assert {
        "spreadsheet.workbook.write",
        "spreadsheet.workbook.verify",
        "spreadsheet.range.read",
    } <= capabilities
    client = Client(registry=ConnectorRegistry([connector]))
    with pytest.raises(OTCError):
        client.workbook.create((tmp_path / "data.csv").as_uri())
    book = client.workbook.create((tmp_path / "data.xlsx").as_uri())
    book.worksheet.create("Data").range("A1").write("x")
    book.write()
    assert book.verify().verification.value == "passed"


def test_every_local_advertised_workbook_binding_executes():
    from specification.conformance.universal.cases import all_cases

    case = next(case for case in all_cases() if case.name == "local_files")
    for capability, binding in case.capability_bindings.items():
        if capability.startswith("spreadsheet."):
            result = binding.invoke()
            if hasattr(result, "outcome"):
                assert result.outcome.value == "succeeded"
            else:
                assert result == ("Data", "Other")
