from __future__ import annotations

from open_table_connector.sdk import Client, ConnectorRegistry


def test_missing_remote_export_no_synthetic_snapshot():
    from open_table_connector.artifacts import ViewRequest
    from open_table_connector.contract import TargetSelector

    result = Client(registry=ConnectorRegistry()).artifacts().view(ViewRequest(TargetSelector("https://www.maybe.ai/docs/spreadsheets/d/doc"), "html"))
    assert result.outcome.value in {"rejected", "unknown"}
    assert result.value is None


def test_view_passes_disposable_copy_and_preserves_source(tmp_path, monkeypatch):
    from open_table_connector.artifacts import ViewRequest
    from open_table_connector.contract import TargetSelector
    from open_table_connector.sdk.artifacts import ArtifactAccess
    source = tmp_path / "source.xlsx"
    source.write_bytes(b"source")
    class Adapter:
        def render(self, path, request):
            assert path != source
            assert path.read_bytes() == b"source"
            path.write_bytes(b"preview edits")
            return {"outputs": [{"uri": "file:///tmp/view.html"}], "renderer": {"version": "fake"}}
    monkeypatch.setattr(ArtifactAccess, "_adapter", lambda self: Adapter())
    result = Client(registry=ConnectorRegistry()).artifacts().view(ViewRequest(TargetSelector(source.as_uri()), "html"))
    assert result.outcome.value == "succeeded"
    assert result.value.source_hash.startswith("sha256:")
    assert source.read_bytes() == b"source"
