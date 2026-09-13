import pytest
from open_table_connector.sdk import OTCError
from open_table_connector.sdk.workbook import WorkbookSession


class Client:
    def _assert_open(self):
        pass


class Provider:
    def __init__(self):
        self.commits = []
        self.result = {
            "outcome": "succeeded",
            "commit": "committed",
            "verification": "passed",
            "value": {"saved": True},
        }

    def bind(self, target):
        return {"uri": target.uri}

    def preflight(self, binding, changes):
        return {}

    def commit(self, binding, changes, **kwargs):
        self.commits.append(tuple(changes))
        return self.result

    def observe(self, binding, selector):
        return {
            "value": [[selector["changes"][-1].arguments["values"][0][0]]],
            "receipts": [
                {"details": {"source": "pending" if selector["changes"] else "committed"}}
            ],
        }


def test_buffered_sdk_captures_results_and_previews():
    provider = Provider()
    book = WorkbookSession(Client(), provider, "file:///tmp/sdk.xlsx", new=True)
    first = book.worksheet.create("Report").range("A1").write([["x"]])
    captured = first.with_results()
    assert not provider.commits
    assert book.worksheet("Report").range("A1").read().require_value() == [["x"]]
    book.write(dry_run=True)
    assert not provider.commits
    book.write()
    assert len(provider.commits) == 1
    assert first.with_results() is captured and captured.outcome.value == "planned"
    book.write()
    assert len(provider.commits) == 1


def test_unknown_effects_block_unsafe_retry():
    provider = Provider()
    provider.result = {
        "outcome": "unknown",
        "commit": "unknown",
        "verification": "unavailable",
        "value": {"created_id": "123"},
        "error": {"code": "uncertain_mutation", "message": "timeout"},
    }
    book = WorkbookSession(Client(), provider, "file:///tmp/sdk.xlsx")
    book.worksheet("Sheet").range("A1").write("x")
    with pytest.raises(OTCError) as raised:
        book.write()
    assert raised.value.result.value == {"created_id": "123"}
    with pytest.raises(OTCError):
        book.write()
    with pytest.raises(OTCError):
        book.worksheet("Sheet").range("A1").write("y")
    assert len(provider.commits) == 1


def test_neutral_receipts_retain_known_effects_and_unknown_code():
    provider = Provider()
    provider.result = {
        "outcome": "unknown",
        "commit": "unknown",
        "verification": "unavailable",
        "value": {"created_ids": {"Report": "42"}},
        "receipts": [
            {"operation": "worksheet.create", "request_id": "r1", "result": {"gid": "42"}}
        ],
    }
    book = WorkbookSession(Client(), provider, "file:///tmp/evidence.xlsx")
    book.worksheet.create("Report")
    with pytest.raises(OTCError) as raised:
        book.write()
    result = raised.value.result
    assert result.error.code.value == "uncertain_mutation"
    assert result.receipts[0].details["result"]["gid"] == "42"
    assert result.to_wire()["receipts"][0]["details"]["request_id"] == "r1"
    with pytest.raises(TypeError):
        result.receipts[0].details["result"]["gid"] = "changed"


def test_deleted_recreated_worksheet_invalidates_old_resource_handles():
    provider = Provider()
    book = WorkbookSession(Client(), provider, "file:///tmp/generations.xlsx")
    sheet = book.worksheet.create("Data")
    old_range = sheet.range("A1")
    old_formulas = sheet.formulas()
    sheet.delete()
    replacement = book.worksheet.create("Data")
    for invoke in (
        lambda: old_range.write("wrong"),
        lambda: old_range.read(),
        lambda: sheet.range("A1"),
        lambda: old_formulas.set("A1", "=1"),
    ):
        with pytest.raises(OTCError) as raised:
            invoke()
        assert raised.value.result.error.code.value == "stale_revision"
    replacement.range("A1").write("right")
    book.write()
    assert provider.commits[0][-1].arguments["values"][0][0] == "right"


def test_second_literal_write_rejects_sealed_session():
    book = WorkbookSession(
        Client(), Provider(), "file:///tmp/sealed.xlsx", profile="literal-artifact/1.0"
    )
    book.worksheet.create("Data")
    book.write()
    with pytest.raises(OTCError):
        book.write()
