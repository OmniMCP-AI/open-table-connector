from __future__ import annotations

from open_table_connector.sdk import Client, ConnectorRegistry


def test_core_import_without_officecli():
    client = Client(registry=ConnectorRegistry())
    assert callable(client.artifacts)


def test_xlsx_export_routes_only_excelize(tmp_path):
    from open_table_connector.artifacts import ExportRequest

    request = ExportRequest((tmp_path / "source.xlsx").as_uri(), (tmp_path / "out.xlsx").as_uri(), "officecli", {"format": "xlsx"})
    result = Client(registry=ConnectorRegistry()).artifacts().export(request)
    assert result.outcome.value in {"rejected", "succeeded"}
    if result.error:
        assert result.error.code.value == "unsupported_capability"
