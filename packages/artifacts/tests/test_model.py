from __future__ import annotations

import pytest


def test_export_spec_closed_and_format_matches():
    from open_table_connector.artifacts.model import ExportRequest

    request = ExportRequest("file:///tmp/source.csv", "file:///tmp/out.docx", "officecli", {"format": "docx"})
    assert request.destination_uri.endswith(".docx")
    with pytest.raises(ValueError, match="format"):
        ExportRequest("file:///tmp/source.csv", "file:///tmp/out.docx", "officecli", {"format": "pptx"})


def test_legacy_extensions_reject():
    from open_table_connector.artifacts.model import ExportRequest

    with pytest.raises(ValueError, match="legacy"):
        ExportRequest("file:///tmp/source.csv", "file:///tmp/out.doc", "officecli", {"format": "doc"})


def test_display_defaults_deterministic():
    from open_table_connector.artifacts.model import display_cell

    assert display_cell(None) == ""
    assert display_cell(True) == "true"
    assert display_cell("00123") == "00123"


def test_asset_path_traversal_reject():
    from open_table_connector.artifacts.model import validate_asset_path

    with pytest.raises(ValueError, match="asset"):
        validate_asset_path("../secret.png")
