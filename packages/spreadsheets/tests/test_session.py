import pytest
from open_table_connector.contract import ConnectorError
from open_table_connector.spreadsheets._session import SpreadsheetSession
from open_table_connector.spreadsheets.model import RangeRef, SpreadsheetTarget


class Provider:
    def __init__(self):
        self.commits = []
        self.preflights = []

    def bind(self, target):
        return {"uri": target.uri}

    def preflight(self, binding, changes):
        self.preflights.append(tuple(changes))
        return {}

    def commit(self, binding, changes, **kwargs):
        self.commits.append(tuple(changes))
        return {
            "outcome": "succeeded",
            "commit": "committed",
            "verification": "passed",
            "value": {},
        }

    def observe(self, binding, selector):
        return {"value": selector}


def test_freezes_nested_changes_and_dry_run():
    provider = Provider()
    book = SpreadsheetSession(provider, SpreadsheetTarget("file:///tmp/test.xlsx"), new=True)
    values = [["original"]]
    planned = book.queue("range.write", "Report", {"values": values, "address": "A1"})
    values[0][0] = "changed"
    assert book.pending[0].arguments["values"][0][0] == "original"
    with pytest.raises(TypeError):
        book.pending[0].arguments["values"][0][0] = "mutated"
    book.write(dry_run=True)
    assert not provider.commits
    book.write()
    assert planned["outcome"] == "planned"
    assert len(provider.commits) == 1
    book.write()
    assert len(provider.commits) == 1


def test_closed_session_rejects_edits():
    book = SpreadsheetSession(Provider(), SpreadsheetTarget("file:///tmp/test.xlsx"))
    book.close()
    with pytest.raises(ConnectorError):
        book.queue("range.clear", "Sheet", {"address": "A1"})


def test_range_direction_checks_both_axes():
    with pytest.raises(ValueError):
        RangeRef("B1:A2")


def test_unknown_commit_blocks_queue_and_reconciliation_is_observe_only():
    provider = Provider()
    provider.commit = lambda *a, **kw: {
        "outcome": "unknown",
        "commit": "unknown",
        "verification": "unavailable",
    }
    book = SpreadsheetSession(provider, SpreadsheetTarget("file:///tmp/test.xlsx"))
    book.queue("range.write", "Report", {"address": "A1", "values": [["x"]]})
    book.write()
    with pytest.raises(ConnectorError):
        book.write()
    with pytest.raises(ConnectorError):
        book.queue("range.clear", "Report", {"address": "A1"})
    book.reconcile()
    with pytest.raises(ConnectorError):
        book.write()


def test_atomic_preflight_failure_preserves_pending():
    provider = Provider()
    book = SpreadsheetSession(provider, SpreadsheetTarget("file:///tmp/test.xlsx"))
    book.queue("range.write", "Report", {"address": "A1", "values": [["x"]]})

    def reject(*args):
        raise ConnectorError.configuration("unsupported sequence")

    provider.preflight = reject
    with pytest.raises(ConnectorError):
        book.queue("range.style", "Report", {"address": "A1", "bold": True})
    assert len(book.pending) == 1
    assert not provider.commits


def test_sealed_artifact_rejects_edits_but_allows_verification():
    book = SpreadsheetSession(
        Provider(),
        SpreadsheetTarget("file:///tmp/test.xlsx"),
        new=True,
        profile="literal-artifact/1.0",
    )
    book.queue("worksheet.create", "Report", {})
    book.write()
    with pytest.raises(ConnectorError):
        book.queue("range.clear", "Report", {"address": "A1"})
    book.verify()


def test_concurrent_write_and_edit_rejected_without_second_dispatch():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    entered, release = Event(), Event()
    provider = Provider()
    original = provider.commit

    def blocking(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    provider.commit = blocking
    book = SpreadsheetSession(provider, SpreadsheetTarget("file:///tmp/concurrent.xlsx"))
    book.queue("range.clear", "Data", {"address": "A1"})
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(book.write)
        assert entered.wait(5)
        try:
            with pytest.raises(ConnectorError):
                book.write()
            with pytest.raises(ConnectorError):
                book.queue("range.clear", "Data", {"address": "B1"})
            with pytest.raises(ConnectorError):
                book.close()
            with pytest.raises(ConnectorError):
                book.observe("range.read", target_key="Data", address="A1")
        finally:
            release.set()
        assert future.result()["commit"] == "committed"
    assert len(provider.commits) == 1


@pytest.mark.parametrize("flag", ["allow_partial", "dry_run", "verify"])
def test_write_flags_require_real_booleans(flag):
    provider = Provider()
    book = SpreadsheetSession(provider, SpreadsheetTarget("file:///tmp/flags.xlsx"))
    with pytest.raises(ConnectorError):
        book.write(**{flag: "false"})
    assert provider.commits == []
