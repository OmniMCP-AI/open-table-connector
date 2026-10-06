from __future__ import annotations

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
