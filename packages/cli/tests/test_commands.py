import io
import json
import csv

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

    def __init__(self):
        self.read_calls = 0
        self.write_calls = 0

    def read(self, endpoint, options):
        self.read_calls += 1
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
        self.write_calls += 1
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


def test_read_rejects_provider_from_format_override_before_adapter_io(fake_registry) -> None:
    out, err = io.StringIO(), io.StringIO()
    args = type(
        "Args",
        (),
        {
            "command": "read",
            "from_value": "gsheets://book/Orders",
            "from_format": "csv",
            "output_format": "jsonl",
        },
    )()

    code = run_command(args, fake_registry, out, err)

    payload = json.loads(err.getvalue())
    adapter = fake_registry.list()[0]
    assert code == 3
    assert payload["code"] == "unsupported_capability"
    assert payload["safe_details"] == {
        "scheme": "gsheets",
        "option": "from-format",
        "format": "csv",
    }
    assert adapter.read_calls == 0
    assert adapter.write_calls == 0
    assert out.getvalue() == ""


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


@pytest.mark.parametrize("format_name", ("json", "jsonl", "csv", "table"))
def test_convert_to_stdout_contains_only_selected_codec(format_name, fake_registry, tmp_path) -> None:
    source = tmp_path / "source.csv"
    source.write_text("id\na\n")
    out, err = io.StringIO(), io.StringIO()
    args = type(
        "Args",
        (),
        {
            "command": "convert",
            "from_value": str(source),
            "to_value": "-",
            "to_format": format_name,
            "output_format": "jsonl",
        },
    )()

    assert run_command(args, fake_registry, out, err) == 0
    assert err.getvalue() == ""
    if format_name == "json":
        assert json.loads(out.getvalue()) == [{"id": "a", "amount": 1}]
    elif format_name == "jsonl":
        assert [json.loads(line) for line in out.getvalue().splitlines()] == [
            {"id": "a", "amount": 1}
        ]
    elif format_name == "csv":
        assert list(csv.reader(io.StringIO(out.getvalue()))) == [
            ["id", "amount"], ["a", "1"]
        ]
    else:
        assert "| id" in out.getvalue()
        assert "| amount" in out.getvalue()
        assert "summary" not in out.getvalue()


def test_list_table_output_is_aligned_human_table(fake_registry) -> None:
    out, err = io.StringIO(), io.StringIO()
    args = type("Args", (), {"command": "list", "output_format": "table"})()

    assert run_command(args, fake_registry, out, err) == 0
    assert err.getvalue() == ""
    assert out.getvalue().splitlines()[0].startswith("| connector_id")
    assert "| fake" in out.getvalue()
    with pytest.raises(json.JSONDecodeError):
        json.loads(out.getvalue())


def test_inspect_table_output_is_aligned_human_table(fake_registry) -> None:
    out, err = io.StringIO(), io.StringIO()
    args = type(
        "Args",
        (),
        {"command": "inspect", "from_value": "gsheets://book/Orders", "output_format": "table"},
    )()

    # The fake adapter's inspection seam is intentionally replaced for this
    # output test so command routing can be tested without provider I/O.
    inspection = type(
        "Inspection",
        (),
        {
            "safe_uri": TableURI("gsheets://book/Orders"),
            "mode": TableMode.BASE,
            "columns": ("id",),
            "schema_fingerprint": "schema",
            "row_count": 1,
            "coordinate_convention": BaseConvention(ordinal_snapshot_id="local"),
            "facts": {"provider": "fake"},
        },
    )()
    fake_registry.list()[0].inspect = lambda endpoint, options: inspection

    assert run_command(args, fake_registry, out, err) == 0
    assert err.getvalue() == ""
    assert "| safe_uri" in out.getvalue()
    assert "| schema_fingerprint" in out.getvalue()


def test_convert_summary_table_is_not_json(fake_registry, tmp_path) -> None:
    source = tmp_path / "source.csv"
    destination = tmp_path / "destination.json"
    source.write_text("id\na\n")
    out, err = io.StringIO(), io.StringIO()
    args = type(
        "Args",
        (),
        {
            "command": "convert",
            "from_value": str(source),
            "to_value": str(destination),
            "output_format": "table",
        },
    )()

    assert run_command(args, fake_registry, out, err) == 0
    assert err.getvalue() == ""
    assert "| field" in out.getvalue()
    assert "| rows_read" in out.getvalue()
