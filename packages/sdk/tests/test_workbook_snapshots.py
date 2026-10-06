from __future__ import annotations

from open_table_connector.contract import TargetSelector
from open_table_connector.sdk import Client, ConnectorRegistry
from open_table_connector.sdk.snapshots import capture_workbook_snapshot


def test_snapshot_local_hash_unchanged(tmp_path):
    path = tmp_path / "book.xlsx"
    path.write_bytes(b"xlsx snapshot")
    result = capture_workbook_snapshot(Client(registry=ConnectorRegistry()), TargetSelector(path.as_uri()), tmp_path)
    assert result.outcome.value == "succeeded"
    snapshot = result.require_value()
    assert snapshot.consistency == "revision_bound"
    assert snapshot.content_hash.startswith("sha256:")


def test_export_unavailable_not_synthesized(tmp_path):
    result = capture_workbook_snapshot(Client(registry=ConnectorRegistry()), TargetSelector("https://www.maybe.ai/docs/spreadsheets/d/doc"), tmp_path)
    assert result.outcome.value in {"rejected", "unknown"}
    assert result.value is None
