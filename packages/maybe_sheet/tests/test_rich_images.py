from __future__ import annotations

import pytest
from open_table_connector.contract import ConnectorError
from open_table_connector.spreadsheets import SpreadsheetTarget
from open_table_connector.spreadsheets._operations import Change
from open_table_connector.contract import CapabilityIdentity

from .test_spreadsheet import Recording, provider


def change(operation, sheet="Report", **arguments):
    return Change(operation, CapabilityIdentity("spreadsheet.test", "1.0"), sheet, arguments)


def test_sheet_engine_required():
    process = Recording()
    p, binding = provider(process)
    with pytest.raises(ConnectorError):
        p.preflight(binding, [change("range.write", "Base", address="A1", values=[[1]])])


def test_mixed_base_sheet_unchanged():
    process = Recording()
    p, binding = provider(process)
    p.commit(binding, [change("image.insert", anchor="A1", mime_type="image/png", content=b"png")], allow_partial=True, expected_revision=None, idempotency_key=None)
    assert all("Base" not in call for call in process.mutations)


def test_image_bytes_anchor_and_picture_id():
    process = Recording()
    p, binding = provider(process)
    result = p.commit(binding, [change("image.insert", anchor="A1", mime_type="image/png", content=b"png")], allow_partial=True, expected_revision=None, idempotency_key=None)
    assert result["commit"] == "committed"
    assert process.mutations[-1][1:3] == ("image", "insert")


def test_explicit_size_rejected_before_dispatch():
    process = Recording()
    p, binding = provider(process)
    with pytest.raises(ConnectorError):
        p.preflight(binding, [change("image.insert", anchor="A1", mime_type="image/png", content=b"png", width=10)])
    assert not process.mutations


def test_multicommand_requires_allow_partial():
    process = Recording()
    p, binding = provider(process)
    with pytest.raises(ConnectorError):
        p.commit(binding, [change("image.insert", anchor="A1", mime_type="image/png", content=b"png"), change("range.write", address="A1", values=[[1]])], allow_partial=False, expected_revision=None, idempotency_key=None)
    assert not process.mutations
