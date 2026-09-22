import pytest
from open_table_connector.sdk import OTCError
from open_table_connector.sdk.client import Client as OtcClient
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


SOURCE = "https://www.maybe.ai/docs/spreadsheets/d/source"
DESTINATION = "https://www.maybe.ai/docs/spreadsheets/d/destination"


class CopyProvider(Provider):
    """Provider that advertises (or withholds) the copy capability."""

    def __init__(self, capabilities=("workbook.copy",)):
        super().__init__()
        self.capabilities = capabilities

    def bind(self, target):
        return {
            "uri": target.uri,
            "profile": "general/1.0",
            "capabilities": self.capabilities,
        }


class _Connector:
    def __init__(self, provider):
        self.spreadsheet_provider = (lambda: provider) if provider is not None else None


class _Registry:
    def __init__(self, provider):
        self._provider = provider

    def connector_for(self, _uri):
        return _Connector(self._provider)


def _copy_client(provider):
    return OtcClient(registry=_Registry(provider))


def test_copy_workbook_carries_the_source_into_the_buffered_session():
    provider = CopyProvider()
    client = _copy_client(provider)
    book = client.copy_workbook(SOURCE, to=DESTINATION, title="report copy")
    binding = book._session.binding
    assert binding["copy_from"] == SOURCE
    assert binding["copy_title"] == "report copy"
    # The session binds to the requested destination until the provider returns
    # the document id it actually allocated.
    assert binding["uri"] == DESTINATION
    assert "workbook.copy" in book.capabilities


def test_copy_workbook_fails_closed_without_the_capability():
    client = _copy_client(CopyProvider(capabilities=()))
    with pytest.raises(OTCError):
        client.copy_workbook(SOURCE, to=DESTINATION)


def test_copy_workbook_fails_closed_when_the_transport_is_absent():
    client = _copy_client(None)
    with pytest.raises(OTCError):
        client.copy_workbook(SOURCE, to=DESTINATION)


def test_copy_workbook_accepts_the_versioned_capability_spelling():
    client = _copy_client(CopyProvider(capabilities=("spreadsheet.workbook.copy/1.0",)))
    book = client.workbook.copy(SOURCE, to=DESTINATION)
    assert book._session.binding["copy_from"] == SOURCE


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
