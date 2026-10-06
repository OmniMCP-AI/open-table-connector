from __future__ import annotations


def test_rich_profile_uses_excelize_and_never_openpyxl_save(tmp_path, monkeypatch):
    from openpyxl.workbook.workbook import Workbook
    from open_table_connector.local_files import LocalFilesConnector
    from open_table_connector.sdk import Client, ConnectorRegistry

    def forbidden_save(*args, **kwargs):
        raise AssertionError("rich XLSX must be authored exclusively by Excelize")

    monkeypatch.setattr(Workbook, "save", forbidden_save)
    with Client(registry=ConnectorRegistry([LocalFilesConnector()])) as client:
        book = client.workbook.create((tmp_path / "rich.xlsx").as_uri(), profile="rich-artifact/1.0")
        book.worksheet.create("Report").range("A1:B1").write([["=literal", ""]])
        result = book.write()
        assert result.commit.value == "committed"
        assert result.verification.value == "passed"

from open_table_connector.local_files import LocalFilesConnector
from open_table_connector.sdk import Client, ConnectorRegistry


def test_rich_profile_selects_excelize_only(tmp_path):
    client = Client(registry=ConnectorRegistry([LocalFilesConnector()]))
    book = client.workbook.create((tmp_path / "rich.xlsx").as_uri(), profile="rich-artifact/1.0")
    book.worksheet.create("Report").range("A1").write([["00123"]])
    assert book.write().commit.value == "committed"


def test_general_and_literal_profiles_unchanged(tmp_path):
    client = Client(registry=ConnectorRegistry([LocalFilesConnector()]))
    general = client.workbook.create((tmp_path / "general.xlsx").as_uri(), profile="general/1.0")
    general.worksheet.create("Report")
    assert general.write().commit.value == "committed"
