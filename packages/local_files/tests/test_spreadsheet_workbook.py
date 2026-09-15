from __future__ import annotations

from pathlib import Path

import pytest
from open_table_connector.local_files import LocalFilesConnector
from open_table_connector.sdk import Client, ConnectorRegistry, OTCError
from open_table_connector.spreadsheets import CellStyle


def _client() -> Client:
    return Client(registry=ConnectorRegistry([LocalFilesConnector()]))


def test_literal_workbook_is_written_exclusively_and_verified(tmp_path: Path) -> None:
    destination = tmp_path / "report.xlsx"
    client = _client()
    workbook = client.workbook.create(destination.as_uri())
    sheet = workbook.worksheet.create("Report")
    sheet.range("A1:B2").write([["Revenue", "Cost"], ["10", "4"]])
    sheet.range("A1:B1").style(CellStyle(bold=True))

    result = workbook.write()
    assert result.require_value()["status"] == "verified"
    assert workbook.verify().require_value()["cells"] == 4

    with pytest.raises(OTCError) as raised:
        client.workbook.create(destination.as_uri())
    assert raised.value.result.error is not None
    assert raised.value.result.error.code.value == "destination_exists"


def test_literal_profile_rejects_formula_and_cleans_failed_artifact(tmp_path: Path) -> None:
    destination = tmp_path / "formula.xlsx"
    workbook = _client().workbook.create(destination.as_uri())
    sheet = workbook.worksheet.create("Report")
    sheet.range("A1").write("literal")
    with pytest.raises(OTCError) as raised:
        sheet.formulas().set("B1", "=1+2").with_results()
    assert raised.value.result.error is not None
    assert raised.value.result.error.code.value in {"artifact_integrity", "invalid_formula", "invalid_configuration"}
    assert not destination.exists()


def test_workbook_open_and_concise_worksheet_and_range_operations(tmp_path: Path) -> None:
    destination = tmp_path / "existing.xlsx"
    client = _client()
    created = client.workbook.create(destination.as_uri())
    created.worksheet.create("Inputs").range("A1:B3").write([["key", "value"], ["b", "2"], ["a", "1"]])
    created.write()

    opened = client.workbook(destination.as_uri())
    assert opened.worksheet.list() == ("Inputs",)
    assert opened.worksheet("Inputs").range("A1:B3").read().require_value() == [["key", "value"], ["b", "2"], ["a", "1"]]
    opened.worksheet("Inputs").range("A2:B3").sort()
    assert opened.worksheet("Inputs").range("A1:B3").read().require_value() == [["key", "value"], ["a", "1"], ["b", "2"]]
    opened.write()
    assert client.workbook(destination.as_uri()).worksheet("Inputs").range("A1:B3").read().require_value() == [["key", "value"], ["a", "1"], ["b", "2"]]
