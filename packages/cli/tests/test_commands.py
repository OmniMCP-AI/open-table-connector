import io
import json

import pyarrow as pa
import pytest

from open_connectors.cli.commands import run_command
from open_connectors.cli.output import emit_error
from open_connectors.cli.registry import ConnectorRegistry
from open_connectors.contract import (
    ArrowReadResult,
    CapabilityIdentity,
    ConnectorError,
    ConnectorErrorCode,
    ConnectorIdentity,
    NeutralReceipt,
    TableMode,
    TableURI,
)
from open_connectors.contract.coordinates import BaseConvention


class FakeAdapter:
    schemes = ("gsheets", "file")
    identity = ConnectorIdentity("fake", "1", "1")
    capabilities = (CapabilityIdentity("table.read.arrow", "1"),)

    def read(self, endpoint, options):
        if endpoint.uri is not None:
            raise ConnectorError(
                ConnectorErrorCode.AUTHENTICATION,
                "authentication failed",
                {"token": "must not be emitted"},
            )
        table = pa.table({"id": ["a"], "amount": [1]})
        receipt = NeutralReceipt(
            self.identity,
            self.capabilities[0],
            "op-1",
            TableURI("file:///data.jsonl"),
            TableMode.BASE,
            "local",
            "schema",
            "content",
            BaseConvention(ordinal_snapshot_id="local"),
            1,
            1,
        )
        return ArrowReadResult(table, receipt)

    def inspect(self, endpoint, options):
        raise NotImplementedError

    def write(self, endpoint, table, options):
        raise NotImplementedError


@pytest.fixture
def fake_registry(tmp_path):
    source = tmp_path / "data.jsonl"
    source.write_text('{"id":"a","amount":1}\n')
    return ConnectorRegistry([FakeAdapter()])


def test_read_defaults_to_jsonl_row_events_then_summary(fake_registry, tmp_path) -> None:
    source = tmp_path / "data.jsonl"
    source.write_text('{"id":"a"}\n')
    out, err = io.StringIO(), io.StringIO()
    code = run_command(
        type("Args", (), {"command": "read", "from_value": str(source), "output_format": "jsonl"})(),
        fake_registry,
        out,
        err,
    )
    events = [json.loads(line) for line in out.getvalue().splitlines()]
    assert code == 0
    assert events[0]["event"] == "row"
    assert events[-1]["event"] == "summary"
    assert err.getvalue() == ""


def test_auth_error_is_safe_json_on_stderr(fake_registry) -> None:
    out, err = io.StringIO(), io.StringIO()
    code = run_command(
        type("Args", (), {"command": "read", "from_value": "gsheets://book/Orders", "output_format": "jsonl"})(),
        fake_registry,
        out,
        err,
    )
    payload = json.loads(err.getvalue())
    assert code == 4
    assert out.getvalue() == ""
    assert payload["code"] == "authentication"
    assert "token" not in err.getvalue().casefold()


def test_provider_auth_failure_maps_to_exit_code_four(fake_registry) -> None:
    out, err = io.StringIO(), io.StringIO()
    code = run_command(
        type("Args", (), {"command": "read", "from_value": "gsheets://book/Orders", "output_format": "jsonl"})(),
        fake_registry,
        out,
        err,
    )

    assert code == 4
    assert out.getvalue() == ""
    assert "must not be emitted" not in out.getvalue() + err.getvalue()


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (OSError("credential-bearing provider failure"), 5),
        (ConnectorError(ConnectorErrorCode.EXECUTION_FAILED, "provider failure", {}), 5),
        (ConnectorError(ConnectorErrorCode.CONFLICT, "write conflict", {}), 6),
    ],
)
def test_error_exit_codes_are_stable_and_safe(error, expected_code) -> None:
    err = io.StringIO()
    assert emit_error(error, err) == expected_code
    payload = json.loads(err.getvalue())
    assert payload["code"] in {"execution", "execution_failed", "conflict"}
    assert "credential-bearing" not in err.getvalue()


def test_connector_error_output_contains_no_access_token() -> None:
    error = ConnectorError.authentication(
        "authentication failed", safe_details={"token": "access-token"}
    )
    output = io.StringIO()

    assert emit_error(error, output) == 4
    assert "access-token" not in output.getvalue()
