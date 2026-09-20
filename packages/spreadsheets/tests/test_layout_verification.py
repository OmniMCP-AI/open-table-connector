from __future__ import annotations

from open_table_connector.spreadsheets._session import SpreadsheetSession
from open_table_connector.spreadsheets.model import SpreadsheetTarget


class Provider:
    def __init__(self, error=None):
        self.error = error
        self.commit_count = 0

    def bind(self, target):
        return {"uri": target.uri, "profile": "general/1.0"}

    def preflight(self, binding, changes):
        return {}

    def commit(self, binding, changes, **kwargs):
        self.commit_count += 1
        return {"outcome": "succeeded", "commit": "committed", "verification": "passed", "value": {}}

    def observe(self, binding, selector):
        return {"value": {}}

    def verify_layout(self, binding, expected):
        if self.error:
            raise self.error
        return {"matched": True, "physical_hash": "sha256:" + "0" * 64}


def test_layout_verification_failure_after_commit_does_not_replay_write():
    provider = Provider(TimeoutError("reader timed out"))
    session = SpreadsheetSession(provider, SpreadsheetTarget("file:///tmp/layout.xlsx"))
    session.queue("range.style", "Report", {"address": "A1", "bold": True})
    result = session.write(
        verify=True,
        layout_expectation={"kind": "spreadsheet.financial-layout.expectation/1.0"},
    )
    assert result["commit"] == "committed"
    assert result["verification"] == "unavailable"
    assert result["outcome"] == "failed"
    assert provider.commit_count == 1
    assert session.pending == ()


def test_second_write_has_no_new_changes():
    provider = Provider()
    session = SpreadsheetSession(provider, SpreadsheetTarget("file:///tmp/layout.xlsx"))
    session.queue("range.style", "Report", {"address": "A1", "bold": True})
    session.write(verify=False)
    assert session.write(verify=False) == session.write(verify=False)
    assert provider.commit_count == 1
