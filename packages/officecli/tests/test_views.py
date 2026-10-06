from __future__ import annotations

import pytest
from open_table_connector.artifacts import ViewRequest
from open_table_connector.contract import TargetSelector


def test_missing_browser_explicit(tmp_path):
    from open_table_connector.officecli.views import render_view

    with pytest.raises(RuntimeError, match="renderer"):
        render_view(tmp_path / "snapshot.docx", ViewRequest(TargetSelector((tmp_path / "snapshot.docx").as_uri()), "screenshot"))


def test_qualified_html_runtime_preserves_snapshot(tmp_path, monkeypatch):
    from open_table_connector.officecli.document import OfficeCliAdapter
    from open_table_connector.officecli.process import ProcessResult

    source = tmp_path / "snapshot.xlsx"
    source.write_bytes(b"authoritative bytes")
    destination = tmp_path / "view.html"
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        if argv[-1] == "--version":
            return ProcessResult(0, "1.0.154", "")
        Path(argv[argv.index("--out") + 1]).write_text("<html><body>Report</body></html>")
        return ProcessResult(0, "", "")

    from pathlib import Path
    monkeypatch.setattr("open_table_connector.officecli.capabilities.run_officecli", run)
    monkeypatch.setattr("open_table_connector.officecli.document.run_officecli", run)
    binary = tmp_path / "officecli"
    binary.write_text("binary")
    binary.chmod(0o700)
    adapter = OfficeCliAdapter(binary=str(binary))
    evidence = adapter.render(source, ViewRequest(TargetSelector(source.as_uri()), "html", destination.as_uri()))
    assert evidence["outputs"][0]["uri"] == destination.as_uri()
    assert evidence["renderer"]["version"] == "1.0.154"
    assert source.read_bytes() == b"authoritative bytes"
    assert calls[-1][1:4] == ["view", str(source), "html"]


def test_missing_binary_and_browser_are_capability_results(tmp_path, monkeypatch):
    from open_table_connector.officecli.capabilities import check_officecli
    from open_table_connector.officecli.process import ProcessResult

    assert not check_officecli(str(tmp_path / "missing")).supported
    binary = tmp_path / "officecli"
    binary.write_text("binary")
    binary.chmod(0o700)
    monkeypatch.setattr("open_table_connector.officecli.capabilities.run_officecli", lambda *a, **k: ProcessResult(0, "1.0.154", ""))
    capability = check_officecli(str(binary), renderer="screenshot")
    assert not capability.supported
    assert "browser" in capability.reason


def test_renderer_rejects_asset_paths_and_existing_destination(tmp_path, monkeypatch):
    from open_table_connector.officecli.document import OfficeCliAdapter
    from open_table_connector.officecli.process import ProcessResult

    source = tmp_path / "snapshot.docx"
    source.write_bytes(b"docx")
    binary = tmp_path / "officecli"
    binary.write_text("binary")
    binary.chmod(0o700)
    monkeypatch.setattr("open_table_connector.officecli.capabilities.run_officecli", lambda *a, **k: ProcessResult(0, "1.0.154", ""))
    def run(argv, **kwargs):
        from pathlib import Path
        Path(argv[argv.index("--out") + 1]).write_text('<html><img src="../secret.png"></html>')
        return ProcessResult(0, "", "")
    monkeypatch.setattr("open_table_connector.officecli.document.run_officecli", run)
    adapter = OfficeCliAdapter(binary=str(binary))
    with pytest.raises(RuntimeError, match="asset"):
        adapter.render(source, ViewRequest(TargetSelector(source.as_uri()), "html"))
    destination = tmp_path / "existing.html"
    destination.write_text("keep")
    with pytest.raises(FileExistsError):
        adapter.render(source, ViewRequest(TargetSelector(source.as_uri()), "html", destination.as_uri()))
    assert destination.read_text() == "keep"
