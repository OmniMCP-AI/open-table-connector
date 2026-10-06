from __future__ import annotations

from open_table_connector.sdk import Client, ConnectorRegistry


def test_missing_remote_export_no_synthetic_snapshot():
    from open_table_connector.artifacts import ViewRequest
    from open_table_connector.contract import TargetSelector

    result = Client(registry=ConnectorRegistry()).artifacts().view(ViewRequest(TargetSelector("https://www.maybe.ai/docs/spreadsheets/d/doc"), "html"))
    assert result.outcome.value in {"rejected", "unknown"}
    assert result.value is None
