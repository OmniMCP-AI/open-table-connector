from __future__ import annotations

import importlib

import pytest


def test_unknown_rich_option_rejected():
    from open_table_connector.spreadsheets.rich import RichObjectRequest

    with pytest.raises(ValueError, match="unknown"):
        RichObjectRequest("image.insert", "Report", {"unsupported": True})


def test_qualification_does_not_advertise_blocked():
    from open_table_connector.spreadsheets.rich import RichQualification

    blocked = RichQualification("maybe_sheet", "chart.create", {}, "blocked", (), "no protocol")
    assert blocked.status == "blocked"


def test_image_contract_preserves_existing_wire():
    from open_table_connector.spreadsheets import ImageSpec
    from open_table_connector.spreadsheets.rich import RichObjectRequest

    image = ImageSpec("image/png", b"png", "A1")
    request = RichObjectRequest("image.insert", "Report", {"content": image.content, "mime_type": image.mime_type, "anchor": image.anchor})
    assert request.arguments["mime_type"] == "image/png"
    assert request.arguments["anchor"] == "A1"


def test_missing_remote_operation_not_inferred_from_local():
    from open_table_connector.spreadsheets.rich import qualification

    assert qualification("maybe_sheet", "chart.create").status == "blocked"


def test_rich_contract_imports_no_provider():
    module = importlib.import_module("open_table_connector.spreadsheets.rich")
    assert "local_files" not in module.__dict__
