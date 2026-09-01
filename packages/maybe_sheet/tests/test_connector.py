import json
import subprocess
from pathlib import Path

import polars as pl
import pytest
from open_table_connector.contract import (
    ConnectorError,
    ConnectorErrorCode,
    ResourceLimits,
    TableMode,
    TableURI,
    TableWriteRequest,
)
from open_table_connector.contract.fingerprints import (
    arrow_content_fingerprint,
    arrow_schema_fingerprint,
)
from open_table_connector.maybe_sheet import (
    MaybeSheetConnector,
    MaybeSheetReadRequest,
    SubprocessProcessClient,
)
from open_table_connector.maybe_sheet.process import _absolute_executable, _credential_environment


class Process:
    def __init__(self): self.calls = []
    def run(self, argv, *, credentials=None, stdin=None):
        self.calls.append((argv, credentials, stdin))
        return {"rows": [{"id": "1", "amount": "2.50"}], "source_revision": "rev-1", "receipt_id": "safe-ref"}


class TimedProcess:
    def __init__(self):
        self.timeout = None

    def run(self, argv, *, credentials=None, stdin=None, timeout=None):
        self.timeout = timeout
        return {"rows": [{"id": "1"}]}


class OverReturningProcess:
    def __init__(self):
        self.calls = []

    def run(self, argv, *, credentials=None, stdin=None):
        self.calls.append((argv, credentials, stdin))
        return {
            "rows": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
            "source_revision": "rev-over-return",
            "receipt_id": "over-return-ref",
        }


class ResultEnvelopeProcess:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def run(self, argv, *, credentials=None, stdin=None, timeout=None):
        self.calls.append((argv, credentials, stdin, timeout))
        return self.payload


class WriteProcess:
    def __init__(self):
        self.calls = []
        self.rows_payloads = []

    def run(self, argv, *, credentials=None, stdin=None, timeout=None):
        self.calls.append((argv, credentials, stdin, timeout))
        rows_path = Path(argv[argv.index("--frame-in") + 1])
        self.rows_payloads.append(json.loads(rows_path.read_text(encoding="utf-8")))
        return {
            "contract_version": "1.0",
            "ok": True,
            "operation": "table.insert",
            "target": {},
            "warnings": [],
            "request_id": "write-ref",
            "result": {"inserted_rows": len(self.rows_payloads[-1])},
            "verification": {"status": "passed", "checks": ["row_count_delta"]},
            "trace": None,
        }


def test_maybe_sheet_has_explicit_base_and_sheet_argv_and_receipts() -> None:
    process = Process()
    connector = MaybeSheetConnector(process)
    request = MaybeSheetReadRequest(TableURI("https://www.maybe.ai/docs/spreadsheets/d/doc"), TableMode.BASE, "R_orders")

    result = connector.read_polars(request)

    assert result.frame.to_dicts() == [{"id": "1", "amount": "2.50"}]
    assert process.calls[0][0][:3] == ("mbs", "db-table", "read")
    assert process.calls[0][0] == (
        "mbs", "db-table", "read", "--uri",
        "https://www.maybe.ai/docs/spreadsheets/d/doc", "--name", "R_orders",
    )
    assert process.calls[0][1] == {}
    assert result.receipt.vendor_receipt_ref == "safe-ref"


def test_maybe_sheet_reads_values_from_mbs_result_envelope() -> None:
    process = ResultEnvelopeProcess(
        {
            "success": True,
            "endpoint": "/api/v1/excel/read_sheet",
            "result": {"values": [["id", "amount"], ["1", "2.50"]]},
            "target": {"worksheet_name": "R_orders"},
        }
    )

    result = MaybeSheetConnector(process).read_arrow(
        MaybeSheetReadRequest(
            TableURI("https://www.maybe.ai/docs/spreadsheets/d/doc"),
            TableMode.BASE,
            "R_orders",
        )
    )

    assert result.table.to_pylist() == [{"id": "1", "amount": "2.50"}]


def test_maybe_sheet_sheet_read_uses_worksheet_name_and_applies_limit_locally() -> None:
    process = ResultEnvelopeProcess(
        {
            "success": True,
            "endpoint": "/api/v1/excel/read_sheet",
            "result": {"values": [["id"], ["1"], ["2"]]},
            "target": {"worksheet_name": "Orders"},
        }
    )

    result = MaybeSheetConnector(process).read_arrow(
        MaybeSheetReadRequest(
            TableURI("https://www.maybe.ai/docs/spreadsheets/d/doc"),
            TableMode.SHEET,
            "Orders",
            ResourceLimits(max_rows=1),
        )
    )

    assert result.table.to_pylist() == [{"id": "1"}]
    assert process.calls[0][0] == (
        "mbs",
        "excel-worksheet",
        "read",
        "--uri",
        "https://www.maybe.ai/docs/spreadsheets/d/doc",
        "--worksheet-name",
        "Orders",
    )


def test_maybe_sheet_read_enforces_max_rows_when_process_over_returns() -> None:
    process = OverReturningProcess()
    request = MaybeSheetReadRequest(
        TableURI("maybe://doc/R_orders"),
        TableMode.BASE,
        "R_orders",
        ResourceLimits(max_rows=1),
    )

    result = MaybeSheetConnector(process).read_arrow(request)

    assert result.table.to_pylist() == [{"id": "1"}]
    assert process.calls[0][0][4] == "https://www.maybe.ai/docs/spreadsheets/d/doc"
    assert process.calls[0][0][-2:] == ("--limit", "1")
    assert result.receipt.row_count == 1
    assert result.receipt.schema_fingerprint == arrow_schema_fingerprint(result.table.schema)
    assert result.receipt.content_fingerprint == arrow_content_fingerprint(result.table)
    assert result.receipt.vendor_receipt_ref == "over-return-ref"


def test_maybe_sheet_non_read_capabilities_fail_explicitly() -> None:
    connector = MaybeSheetConnector(Process())
    with pytest.raises(ConnectorError) as error:
        connector.read_formula_values(object())
    assert error.value.code is ConnectorErrorCode.UNSUPPORTED_CAPABILITY


def test_maybe_sheet_subprocess_transport_redacts_diagnostics_and_prefixes_credentials(monkeypatch) -> None:
    seen = {}

    def fake_run(command, **kwargs):
        seen.update(command=command, **kwargs)
        return subprocess.CompletedProcess(command, 0, '{"ok": true}', "secret stderr")

    monkeypatch.setattr(subprocess, "run", fake_run)
    payload = SubprocessProcessClient(binary="mbs", timeout_seconds=3).run(
        ("mbs", "db-table", "read"),
        credentials={"access_token": "hidden"},
        stdin='{"id":"1"}\n',
    )

    assert payload == {"ok": True}
    assert seen["env"]["MAYBEAI_API_TOKEN"] == "hidden"
    assert seen["input"] == '{"id":"1"}\n'
    assert "stderr" not in repr(seen)


def test_credential_environment_rejects_normalized_collision() -> None:
    with pytest.raises(ConnectorError) as raised:
        _credential_environment({"api-key": "one", "api_key": "two"})
    assert raised.value.code is ConnectorErrorCode.CONFLICT


def test_maybe_sheet_binary_must_be_absolute_and_executable(tmp_path) -> None:
    binary = tmp_path / "mbs"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o700)
    assert _absolute_executable(str(binary)) == str(binary)
    with pytest.raises(ValueError, match="absolute"):
        _absolute_executable("mbs")


def test_maybe_sheet_write_uses_table_insert_and_json_rows_file() -> None:
    process = WriteProcess()
    result = MaybeSheetConnector(process).write(
        TableWriteRequest(
            TableURI("maybe://doc/R_orders"),
            pl.DataFrame({"id": ["1"]}),
            table="R_orders",
            if_exists="append",
        )
    )

    call = process.calls[0]
    assert call[0][:7] == (
        "mbs",
        "table",
        "insert",
        "--target",
        "https://www.maybe.ai/docs/spreadsheets/d/doc",
        "--table-name",
        "R_orders",
    )
    assert call[0][7] == "--frame-in"
    rows_path = Path(call[0][8])
    assert rows_path.suffix == ".json"
    assert call[0][9:] == ("--output", "json")
    assert call[2] is None
    assert process.rows_payloads == [[{"id": "1"}]]
    assert not rows_path.exists()
    assert result.affected_rows == 1
    assert result.receipt.vendor_receipt_ref == "write-ref"


def test_maybe_sheet_write_normalizes_non_finite_floats_to_strict_json() -> None:
    process = WriteProcess()

    MaybeSheetConnector(process).write(
        TableWriteRequest(
            TableURI("https://www.maybe.ai/docs/spreadsheets/d/doc"),
            pl.DataFrame({"value": [1.25, float("nan"), float("inf"), float("-inf")]}),
            table="R_orders",
            if_exists="append",
        )
    )

    assert process.rows_payloads == [[
        {"value": 1.25},
        {"value": None},
        {"value": None},
        {"value": None},
    ]]


def test_maybe_sheet_write_serialization_errors_are_secret_safe_and_skip_process() -> None:
    process = Process()
    secret = "serialization-secret"

    class Unserializable:
        def __str__(self) -> str:
            raise RuntimeError(f"cannot serialize {secret}")

    request = TableWriteRequest(
        TableURI("https://www.maybe.ai/docs/spreadsheets/d/doc"),
        pl.DataFrame({"value": pl.Series([Unserializable()], dtype=pl.Object)}),
        table="R_orders",
        if_exists="append",
    )

    with pytest.raises(ConnectorError) as error:
        MaybeSheetConnector(process).write(request)

    assert error.value.code is ConnectorErrorCode.EXECUTION_FAILED
    assert secret not in repr(error.value)
    assert secret not in repr(error.value.safe_details)
    assert secret not in repr(error.value.to_wire())
    assert process.calls == []


def test_maybe_sheet_write_passes_explicit_credentials_without_serializing_them() -> None:
    process = WriteProcess()
    access_token = "explicit-write-token"
    result = MaybeSheetConnector(process).write(
        TableWriteRequest(
            TableURI("https://www.maybe.ai/docs/spreadsheets/d/doc"),
            pl.DataFrame({"id": ["1"]}),
            table="R_orders",
            if_exists="append",
        ),
        credentials={"access_token": access_token},
    )

    assert process.calls[0][1] == {"access_token": access_token}
    assert access_token not in repr(process.calls[0][0])
    assert process.calls[0][2] is None
    assert access_token not in repr(result)
    assert access_token not in repr(result.receipt.to_wire())


@pytest.mark.parametrize("if_exists", ["replace", "error"])
def test_maybe_sheet_rejects_unsupported_write_policies(if_exists) -> None:
    process = Process()
    with pytest.raises(ConnectorError) as error:
        MaybeSheetConnector(process).write(
            TableWriteRequest(
                TableURI("https://www.maybe.ai/docs/spreadsheets/d/doc"),
                pl.DataFrame({"id": ["1"]}),
                table="R_orders",
                if_exists=if_exists,
            )
        )

    assert error.value.code is ConnectorErrorCode.UNSUPPORTED_CAPABILITY
    assert error.value.safe_details == {"if_exists": if_exists}
    assert process.calls == []


@pytest.mark.parametrize("operation", ["read", "write"])
def test_maybe_sheet_unexpected_process_errors_do_not_expose_access_tokens(operation) -> None:
    access_token = "access-token-secret"

    class ExplodingProcess:
        def run(self, *_args, **_kwargs):
            raise RuntimeError(f"process failed with access_token={access_token}")

    connector = MaybeSheetConnector(ExplodingProcess())
    if operation == "read":
        request = MaybeSheetReadRequest(
            TableURI("https://www.maybe.ai/docs/spreadsheets/d/doc"),
            TableMode.BASE,
            "R_orders",
        )
        invoke = lambda: connector.read_polars(request)
    else:
        request = TableWriteRequest(
            TableURI("https://www.maybe.ai/docs/spreadsheets/d/doc"),
            pl.DataFrame({"id": ["1"]}),
            table="R_orders",
            if_exists="append",
        )
        invoke = lambda: connector.write(request, credentials={"access_token": access_token})

    with pytest.raises(ConnectorError) as error:
        invoke()

    assert error.value.code is ConnectorErrorCode.EXECUTION_FAILED
    assert access_token not in repr(error.value)
    assert access_token not in repr(error.value.safe_details)
    assert access_token not in repr(error.value.to_wire())


def test_maybe_sheet_subprocess_transport_maps_timeouts_to_stable_connector_error(monkeypatch) -> None:
    def fake_run(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("mbs", 1)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(ConnectorError) as error:
        SubprocessProcessClient().run(("mbs", "db-table", "read"))
    assert error.value.code is ConnectorErrorCode.TIMEOUT


def test_maybe_sheet_read_passes_request_timeout_to_compatible_process_client() -> None:
    process = TimedProcess()
    request = MaybeSheetReadRequest(
        TableURI("maybe://doc/R_orders"),
        TableMode.BASE,
        "R_orders",
        ResourceLimits(timeout_seconds=7),
    )

    MaybeSheetConnector(process).read_arrow(request)

    assert process.timeout == 7


def test_maybe_sheet_subprocess_client_accepts_per_request_timeout(monkeypatch) -> None:
    seen = {}

    def fake_run(command, **kwargs):
        seen.update(command=command, **kwargs)
        return subprocess.CompletedProcess(command, 0, '{"ok": true}', "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    SubprocessProcessClient(timeout_seconds=120).run(
        ("mbs", "db-table", "read"), timeout=3.5
    )

    assert seen["timeout"] == 3.5
