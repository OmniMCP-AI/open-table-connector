import subprocess

import pytest

from open_connectors.contract import ConnectorError, ConnectorErrorCode, TableMode, TableURI
from open_connectors.maybesheet import MaybeSheetConnector, MaybeSheetReadRequest, SubprocessProcessClient


class Process:
    def __init__(self): self.calls = []
    def run(self, argv, *, credentials=None):
        self.calls.append((argv, credentials))
        return {"rows": [{"id": "1", "amount": "2.50"}], "source_revision": "rev-1", "receipt_id": "safe-ref"}


def test_maybesheet_has_explicit_base_and_sheet_argv_and_receipts() -> None:
    process = Process()
    connector = MaybeSheetConnector(process)
    request = MaybeSheetReadRequest(TableURI("https://www.maybe.ai/docs/spreadsheets/d/doc"), TableMode.BASE, "R_orders")

    result = connector.read_polars(request)

    assert result.frame.to_dicts() == [{"id": "1", "amount": "2.50"}]
    assert process.calls[0][0][:3] == ("mbs", "db-table", "read")
    assert result.receipt.vendor_receipt_ref == "safe-ref"


def test_maybesheet_non_read_capabilities_fail_explicitly() -> None:
    connector = MaybeSheetConnector(Process())
    with pytest.raises(ConnectorError) as error:
        connector.read_formula_values(object())
    assert error.value.code is ConnectorErrorCode.UNSUPPORTED_CAPABILITY


def test_maybesheet_subprocess_transport_redacts_diagnostics_and_prefixes_credentials(monkeypatch) -> None:
    seen = {}

    def fake_run(command, **kwargs):
        seen.update(command=command, **kwargs)
        return subprocess.CompletedProcess(command, 0, '{"ok": true}', "secret stderr")

    monkeypatch.setattr(subprocess, "run", fake_run)
    payload = SubprocessProcessClient(binary="mbs", timeout_seconds=3).run(
        ("mbs", "db-table", "read"), credentials={"access_token": "hidden"}
    )

    assert payload == {"ok": True}
    assert seen["env"]["MAYBESHEET_ACCESS_TOKEN"] == "hidden"
    assert "stderr" not in repr(seen)


def test_maybesheet_subprocess_transport_maps_timeouts_to_stable_connector_error(monkeypatch) -> None:
    def fake_run(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("mbs", 1)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(ConnectorError) as error:
        SubprocessProcessClient().run(("mbs", "db-table", "read"))
    assert error.value.code is ConnectorErrorCode.TIMEOUT
