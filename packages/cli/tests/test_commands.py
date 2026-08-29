import io
import json
import csv
from datetime import date, datetime, timezone
from decimal import Decimal

import pyarrow as pa
import pytest

from open_table_connector.cli.commands import run_command
from open_table_connector.cli.output import emit_error
from open_table_connector.cli.registry import ConnectorRegistry
from open_table_connector.contract import (
    ArrowReadResult,
    CapabilityIdentity,
    ConnectorError,
    ConnectorErrorCode,
    ConnectorIdentity,
    NeutralReceipt,
    TableWriteResult,
    TableMode,
    TableURI,
)
from open_table_connector.contract.coordinates import BaseConvention


def _strict_json_loads(text: str):
    def reject_constant(value: str):
        raise ValueError(f"non-standard JSON constant: {value}")

    return json.loads(text, parse_constant=reject_constant)


class FakeAdapter:
    schemes = ("gsheets", "file")
    identity = ConnectorIdentity("fake", "1", "1")
    capabilities = (
        CapabilityIdentity("table.read.arrow", "1"),
        CapabilityIdentity("table.write", "1"),
    )

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
        return ArrowReadResult(table, self._receipt())

    def _receipt(self):
        return NeutralReceipt(
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

    def inspect(self, endpoint, options):
        raise NotImplementedError

    def write(self, endpoint, table, options):
        self.write_calls += 1
        return TableWriteResult(self._receipt(), table.num_rows)


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
        type("Args", (), {"command": "read", "from_value": str(source)})(),
        fake_registry,
        out,
        err,
    )
    events = [json.loads(line) for line in out.getvalue().splitlines()]
    assert code == 0
    assert events[0]["event"] == "row"
    assert events[-1]["event"] == "summary"
    assert err.getvalue() == ""


@pytest.mark.parametrize("format_name", ("json", "jsonl"))
def test_read_normalizes_arrow_scalars_to_strict_json(format_name, fake_registry, tmp_path) -> None:
    adapter = fake_registry.list()[0]
    table = pa.table(
        {
            "nan": [float("nan")],
            "positive_infinity": [float("inf")],
            "negative_infinity": [float("-inf")],
            "date": [date(2026, 8, 28)],
            "timestamp": [datetime(2026, 8, 28, 1, 2, 3, tzinfo=timezone.utc)],
            "decimal": pa.array([Decimal("12.30")], type=pa.decimal128(4, 2)),
            "nested": pa.array([[float("nan"), float("inf"), float("-inf")]]),
        }
    )
    adapter.read = lambda endpoint, options: ArrowReadResult(table, adapter._receipt())
    source = tmp_path / "source.jsonl"
    source.write_text('{}\n')
    out, err = io.StringIO(), io.StringIO()
    args = type(
        "Args",
        (),
        {"command": "read", "from_value": str(source), "output_format": format_name},
    )()

    assert run_command(args, fake_registry, out, err) == 0

    if format_name == "json":
        row = _strict_json_loads(out.getvalue())["rows"][0]
    else:
        row = _strict_json_loads(out.getvalue().splitlines()[0])["row"]
    assert row == {
        "nan": None,
        "positive_infinity": None,
        "negative_infinity": None,
        "date": "2026-08-28",
        "timestamp": "2026-08-28T01:02:03+00:00",
        "decimal": "12.30",
        "nested": [None, None, None],
    }
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
            "output_format": format_name,
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


def test_list_json_output_is_one_array_document(fake_registry) -> None:
    out, err = io.StringIO(), io.StringIO()
    args = type("Args", (), {"command": "list", "output_format": "json"})()

    assert run_command(args, fake_registry, out, err) == 0
    assert err.getvalue() == ""
    payload = json.loads(out.getvalue())
    assert isinstance(payload, list)
    assert payload[0]["connector_id"] == "fake"


def test_list_csv_output_has_header_and_rows(fake_registry) -> None:
    out, err = io.StringIO(), io.StringIO()
    args = type("Args", (), {"command": "list", "output_format": "csv"})()

    assert run_command(args, fake_registry, out, err) == 0
    rows = list(csv.DictReader(io.StringIO(out.getvalue())))
    assert rows[0]["connector_id"] == "fake"
    assert set(rows[0]) == {"connector_id", "schemes", "capabilities", "modes"}


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


def test_inspect_table_output_escapes_special_characters(fake_registry) -> None:
    inspection = type(
        "Inspection",
        (),
        {
            "safe_uri": TableURI("gsheets://book/Orders"),
            "mode": TableMode.BASE,
            "columns": ("id",),
            "schema_fingerprint": "left|right\\path\nnext",
            "row_count": 1,
            "coordinate_convention": BaseConvention(ordinal_snapshot_id="local"),
            "facts": {"provider": "fake"},
        },
    )()
    fake_registry.list()[0].inspect = lambda endpoint, options: inspection
    out, err = io.StringIO(), io.StringIO()
    args = type(
        "Args",
        (),
        {
            "command": "inspect",
            "from_value": "gsheets://book/Orders",
            "output_format": "table",
        },
    )()

    assert run_command(args, fake_registry, out, err) == 0

    lines = out.getvalue().splitlines()
    assert err.getvalue() == ""
    assert len(lines) == 9
    assert len({len(line) for line in lines}) == 1
    assert any(r"left\|right\\path\nnext" in line for line in lines)


@pytest.mark.parametrize("format_name", ("json", "csv"))
def test_inspect_structured_output_format_is_truthful(format_name, fake_registry) -> None:
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
    out, err = io.StringIO(), io.StringIO()
    args = type(
        "Args",
        (),
        {"command": "inspect", "from_value": "gsheets://book/Orders", "output_format": format_name},
    )()

    assert run_command(args, fake_registry, out, err) == 0
    assert err.getvalue() == ""
    if format_name == "json":
        assert json.loads(out.getvalue())["schema_fingerprint"] == "schema"
    else:
        row = next(csv.DictReader(io.StringIO(out.getvalue())))
        assert row["schema_fingerprint"] == "schema"


def test_convert_writes_selected_destination_codec_and_jsonl_summary(fake_registry, tmp_path) -> None:
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
    assert json.loads(out.getvalue())["rows_read"] == 1
    assert "| id" in destination.read_text()


@pytest.mark.parametrize("format_name", ("json", "csv"))
def test_import_summary_uses_requested_structured_format(format_name, fake_registry, tmp_path) -> None:
    source = tmp_path / "source.csv"
    source.write_text("id\na\n")
    out, err = io.StringIO(), io.StringIO()
    args = type(
        "Args",
        (),
        {
            "command": "import",
            "from_value": str(source),
            "to_value": "gsheets://book/Orders",
            "output_format": format_name,
        },
    )()

    assert run_command(args, fake_registry, out, err) == 0
    assert err.getvalue() == ""
    if format_name == "json":
        assert json.loads(out.getvalue())["rows_read"] == 1
    else:
        row = next(csv.DictReader(io.StringIO(out.getvalue())))
        assert row["rows_read"] == "1"
