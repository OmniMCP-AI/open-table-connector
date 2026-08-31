from __future__ import annotations

from types import SimpleNamespace

from open_table_connector.maybe_sheet.process import SubprocessProcessClient


def test_process_environment_is_explicit_and_scoped(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(returncode=0, stdout='{"ok": true}', stderr="")

    monkeypatch.setenv("UNRELATED_HOST_SENTINEL", "must-not-leak")
    monkeypatch.setattr("open_table_connector.maybe_sheet.process.subprocess.run", fake_run)
    result = SubprocessProcessClient(
        binary="mbs", environment={"MAYBE_SHEET_REGION": "test"}
    ).run(("mbs", "read"), credentials={"access_token": "secret"})

    assert result == {"ok": True}
    child_environment = captured["env"]
    assert child_environment == {
        "MAYBE_SHEET_REGION": "test",
        "MAYBE_SHEET_ACCESS_TOKEN": "secret",
    }
