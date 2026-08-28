from __future__ import annotations

from argparse import Namespace
import subprocess

import pyarrow as pa
import pytest

from open_table_connector.cli.adapters import GoogleSheetsAdapter
from open_table_connector.cli.model import CliOptions, FormatName
from open_table_connector.cli.registry import ConnectorRegistry
from open_table_connector.contract import ConnectorError, ConnectorErrorCode
from open_table_connector.google_sheets import GoogleSheetsConnector

from specification.conformance.universal.assertions import (
    parse_csv_records,
    parse_json_lines,
    parse_markdown_table,
    strict_json_loads,
)
from specification.conformance.universal.fixtures import (
    RawProviderFailure,
    RecordingCliAdapter,
    RecordedRequest,
    RecordingSheetsTransport,
    build_cli_registry_bridge,
    run_cli_command,
)


_FIXTURE_SECRET = "fixture-cli-token"
_TABLE_ROWS = (
    {"id": "1", "amount": "2.50", "note": "left|right"},
    {"id": "2", "amount": None, "note": "line1\nline2"},
)


def _args(command: str, **values: object) -> Namespace:
    return Namespace(command=command, **values)


def _fixture_adapter(
    *,
    connector_id: str = "fixture_source",
    schemes: tuple[str, ...] = ("fixture",),
    capabilities: tuple[str, ...] = (
        "table.read.arrow",
        "table.inspect",
        "table.write",
    ),
    failures: dict[str, BaseException] | None = None,
    vendor_receipt_ref: str | None = None,
) -> RecordingCliAdapter:
    return RecordingCliAdapter(
        connector_id=connector_id,
        schemes=schemes,
        capabilities=capabilities,
        table=pa.Table.from_pylist(list(_TABLE_ROWS)),
        failures=failures,
        vendor_receipt_ref=vendor_receipt_ref,
    )


def _assert_full_receipt_wire(
    actual: object,
    *,
    connector_id: str,
    capability_id: str,
    operation_id: str,
    safe_uri: str,
    source_revision: str,
    vendor_receipt_ref: str,
) -> None:
    assert actual == {
        "contract_version": "1.0",
        "connector": {
            "connector_id": connector_id,
            "connector_version": "1.0.0",
            "contract_version": "1.0",
        },
        "capability": {
            "capability_id": capability_id,
            "capability_version": "1.0",
        },
        "operation_id": operation_id,
        "safe_uri": {"value": safe_uri},
        "mode": "base",
        "source_revision": source_revision,
        "schema_fingerprint": (
            "0afe7a8a0c00e61680aa9e698490be97b75ab686535aab8f19870bdd5c209527"
        ),
        "content_fingerprint": (
            "6da705858d0c6d7797bce085687db86659938e2db56edd2e2d1e314743e083b6"
        ),
        "coordinate_convention": {
            "mode": "base",
            "record_id_field": None,
            "key_fields": [],
            "ordinal_snapshot_id": source_revision,
        },
        "row_count": 2,
        "batch_count": 1,
        "vendor_receipt_ref": vendor_receipt_ref,
    }


def test_cli_list_discovers_every_injected_table_connector_with_safe_metadata() -> None:
    bridge = build_cli_registry_bridge()

    result = run_cli_command(
        _args("list", output_format="jsonl"),
        bridge.registry,
    )

    records = parse_json_lines(result.stdout)
    assert result.exit_code == 0
    assert result.stderr == ""
    assert records == (
        {
            "connector_id": "google_sheets",
            "schemes": ["gsheets", "https"],
            "capabilities": [
                {"capability_id": "uri.resolve", "capability_version": "1.0"},
                {"capability_id": "table.inspect", "capability_version": "1.0"},
                {"capability_id": "table.read.arrow", "capability_version": "1.0"},
                {"capability_id": "table.read.polars", "capability_version": "1.0"},
                {"capability_id": "table.write", "capability_version": "1.0"},
            ],
            "modes": ["sheet"],
        },
        {
            "connector_id": "feishu_bitable",
            "schemes": ["feishu", "feishu_bitable"],
            "capabilities": [
                {"capability_id": "uri.resolve", "capability_version": "1.0"},
                {"capability_id": "table.inspect", "capability_version": "1.0"},
                {"capability_id": "table.read.arrow", "capability_version": "1.0"},
                {"capability_id": "table.read.polars", "capability_version": "1.0"},
                {"capability_id": "table.write", "capability_version": "1.0"},
            ],
            "modes": ["base"],
        },
        {
            "connector_id": "maybe_sheet",
            "schemes": ["maybe", "https"],
            "capabilities": [
                {"capability_id": "base.read", "capability_version": "1.0"},
                {"capability_id": "base.inspect", "capability_version": "1.0"},
                {"capability_id": "table.write", "capability_version": "1.0"},
            ],
            "modes": ["base"],
        },
        {
            "connector_id": "local_files",
            "schemes": ["file"],
            "capabilities": [
                {"capability_id": "table.read.arrow", "capability_version": "1.0"},
                {"capability_id": "table.read.polars", "capability_version": "1.0"},
                {"capability_id": "table.inspect", "capability_version": "1.0"},
                {"capability_id": "table.write", "capability_version": "1.0"},
            ],
            "modes": ["base"],
        },
    )
    connector_ids = [record["connector_id"] for record in records]
    assert len(connector_ids) == len(set(connector_ids))
    for record in records:
        assert set(record) == {"connector_id", "schemes", "capabilities", "modes"}
        capability_ids = [item["capability_id"] for item in record["capabilities"]]
        assert len(capability_ids) == len(set(capability_ids))
        assert len(record["schemes"]) == len(set(record["schemes"]))
        assert len(record["modes"]) == len(set(record["modes"]))
    assert "token" not in result.stdout.casefold()
    assert _FIXTURE_SECRET not in result.stdout


@pytest.mark.parametrize(
    (
        "case_name",
        "source",
        "extra",
        "expected_mode",
        "expected_columns",
        "expected_rows",
        "expected_facts",
    ),
    (
        pytest.param(
            "google_sheets",
            "https://docs.google.com/spreadsheets/d/fixture-spreadsheet/edit#gid=0",
            {"token": _FIXTURE_SECRET},
            "sheet",
            ["id", "amount", "note"],
            4,
            {"provider": "google_sheets"},
            id="google-sheets-shared-https-host",
        ),
        pytest.param(
            "feishu_bitable",
            "feishu://fixture-app/orders",
            {"token": _FIXTURE_SECRET},
            "base",
            ["_record_id", "name", "score", "note", "internal_only"],
            3,
            {"provider": "feishu_bitable"},
            id="feishu-scheme",
        ),
        pytest.param(
            "maybe_sheet",
            "https://www.maybe.ai/docs/spreadsheets/d/fixture-doc",
            {"token": _FIXTURE_SECRET, "target": "R_orders"},
            "base",
            ["id", "amount", "note"],
            4,
            {"transport": "process_client"},
            id="maybe_sheet-https-host",
        ),
        pytest.param(
            "local_files",
            None,
            {},
            "base",
            ["id", "amount", "note"],
            3,
            {"provider": "local"},
            id="local-file-scheme",
        ),
    ),
)
def test_cli_inspect_from_selects_exact_scheme_and_reports_safe_metadata(
    case_name: str,
    source: str | None,
    extra: dict[str, object],
    expected_mode: str,
    expected_columns: list[str],
    expected_rows: int,
    expected_facts: dict[str, str],
) -> None:
    bridge = build_cli_registry_bridge()
    selected_source = bridge.sources[case_name] if source is None else source

    result = run_cli_command(
        _args(
            "inspect",
            from_value=selected_source,
            output_format="json",
            **extra,
        ),
        bridge.registry,
    )

    payload = strict_json_loads(result.stdout)
    assert result.exit_code == 0
    assert result.stderr == ""
    assert payload["safe_uri"] == {"value": selected_source}
    assert payload["mode"] == expected_mode
    assert payload["columns"] == expected_columns
    assert payload["row_count"] == expected_rows
    assert payload["facts"] == expected_facts
    assert set(payload) == {
        "safe_uri",
        "mode",
        "columns",
        "schema_fingerprint",
        "row_count",
        "coordinate_convention",
        "facts",
    }
    assert _FIXTURE_SECRET not in result.stdout
    google_requests = bridge.cases["google_sheets"].http_fixture.transport.requests
    feishu_requests = bridge.cases["feishu_bitable"].http_fixture.transport.requests
    maybe_sheet_calls = bridge.cases["maybe_sheet"].process_fixture.process.calls
    if case_name == "google_sheets":
        assert len(google_requests) == 1
        assert feishu_requests == []
        assert maybe_sheet_calls == []
    elif case_name == "feishu_bitable":
        assert google_requests == []
        assert len(feishu_requests) == 2
        assert maybe_sheet_calls == []
    elif case_name == "maybe_sheet":
        assert google_requests == []
        assert feishu_requests == []
        assert len(maybe_sheet_calls) == 1
    else:
        assert google_requests == []
        assert feishu_requests == []
        assert maybe_sheet_calls == []


@pytest.mark.parametrize(
    ("case_name", "source", "extra", "expected_first_row", "expected_rows"),
    (
        pytest.param(
            "google_sheets",
            "gsheets://fixture-spreadsheet/Orders",
            {"token": _FIXTURE_SECRET},
            {"id": "g1", "amount": "2.5", "note": "first"},
            4,
            id="google-sheets-rows",
        ),
        pytest.param(
            "feishu_bitable",
            "feishu://fixture-app/orders",
            {"token": _FIXTURE_SECRET, "field_name": ["name", "score", "note"]},
            {"_record_id": "rec_1", "name": "Ada", "score": "10", "note": "first"},
            3,
            id="feishu-rows",
        ),
        pytest.param(
            "maybe_sheet",
            "maybe://fixture-doc/R_orders",
            {"token": _FIXTURE_SECRET},
            {"id": "1", "amount": "2.5", "note": "first"},
            4,
            id="maybe_sheet-rows",
        ),
        pytest.param(
            "local_files",
            None,
            {},
            {"id": "1", "amount": "2.50", "note": "first"},
            3,
            id="local-rows",
        ),
    ),
)
def test_cli_read_from_defaults_to_jsonl_rows_followed_by_one_summary(
    case_name: str,
    source: str | None,
    extra: dict[str, object],
    expected_first_row: dict[str, object],
    expected_rows: int,
) -> None:
    bridge = build_cli_registry_bridge(case_name)
    selected_source = bridge.sources[case_name] if source is None else source

    result = run_cli_command(
        _args("read", from_value=selected_source, **extra),
        bridge.registry,
    )

    events = parse_json_lines(result.stdout)
    assert result.exit_code == 0
    assert result.stderr == ""
    assert [event["event"] for event in events] == [
        *(["row"] * expected_rows),
        "summary",
    ]
    assert events[0] == {"event": "row", "row": expected_first_row}
    assert events[-1]["status"] == "completed"
    assert events[-1]["rows"] == expected_rows
    assert events[-1]["receipt"]["safe_uri"]["value"] == selected_source
    assert len([event for event in events if event["event"] == "summary"]) == 1
    assert _FIXTURE_SECRET not in result.stdout + result.stderr


@pytest.mark.parametrize(
    ("format_name", "suffix"),
    (
        pytest.param("csv", ".csv", id="csv-round-trip"),
        pytest.param("json", ".json", id="json-round-trip"),
        pytest.param("jsonl", ".jsonl", id="jsonl-round-trip"),
        pytest.param("table", ".table", id="markdown-table-round-trip"),
    ),
)
def test_cli_local_conversion_round_trip_preserves_rows_and_columns(
    tmp_path, format_name: str, suffix: str
) -> None:
    source = tmp_path / "source.json"
    destination = tmp_path / f"round-trip{suffix}"
    source.write_text(
        '[{"id":"1","amount":"2.50","note":"left|right"},'
        '{"id":"2","amount":null,"note":"line1\\nline2"}]',
        encoding="utf-8",
    )
    bridge = build_cli_registry_bridge("local_files")

    converted = run_cli_command(
        _args(
            "convert",
            from_value=str(source),
            to_value=str(destination),
            output_format="json",
        ),
        bridge.registry,
    )
    read_back = run_cli_command(
        _args("read", from_value=str(destination), output_format="json"),
        bridge.registry,
    )

    summary = strict_json_loads(converted.stdout)
    payload = strict_json_loads(read_back.stdout)
    assert converted.exit_code == 0
    assert read_back.exit_code == 0
    assert converted.stderr == read_back.stderr == ""
    assert summary["status"] == "completed"
    assert summary["rows_read"] == summary["rows_written"] == 2
    assert payload["rows"] == list(_TABLE_ROWS)
    assert set(payload["rows"][0]) == {"id", "amount", "note"}
    if format_name != "jsonl":
        assert list(payload["rows"][0]) == ["id", "amount", "note"]
    assert destination.is_file()
    if format_name == "csv":
        assert parse_csv_records(destination.read_text(encoding="utf-8")) == _TABLE_ROWS
    elif format_name == "json":
        assert strict_json_loads(destination.read_text(encoding="utf-8")) == list(_TABLE_ROWS)
    elif format_name == "jsonl":
        assert parse_json_lines(destination.read_text(encoding="utf-8")) == _TABLE_ROWS
    else:
        assert parse_markdown_table(destination.read_text(encoding="utf-8")) == (
            ("id", "amount", "note"),
            (("1", "2.50", "left|right"), ("2", "", "line1\nline2")),
        )


def test_cli_convert_infers_local_source_and_destination_formats(tmp_path) -> None:
    source = tmp_path / "orders.csv"
    destination = tmp_path / "orders.jsonl"
    source.write_text("id,amount\na,1\nb,2\n", encoding="utf-8")
    bridge = build_cli_registry_bridge("local_files")

    result = run_cli_command(
        _args(
            "convert",
            from_value=str(source),
            to_value=str(destination),
            output_format="json",
        ),
        bridge.registry,
    )

    assert result.exit_code == 0
    assert result.stderr == ""
    assert parse_json_lines(destination.read_text(encoding="utf-8")) == (
        {"amount": "1", "id": "a"},
        {"amount": "2", "id": "b"},
    )
    assert strict_json_loads(result.stdout)["rows_written"] == 2


def test_cli_convert_explicit_format_overrides_allow_extensionless_paths(tmp_path) -> None:
    source = tmp_path / "source.data"
    destination = tmp_path / "destination.data"
    source.write_text('{"id":"a"}\n{"id":"b"}\n', encoding="utf-8")
    bridge = build_cli_registry_bridge("local_files")

    result = run_cli_command(
        _args(
            "convert",
            from_value=str(source),
            to_value=str(destination),
            from_format="jsonl",
            to_format="csv",
            output_format="json",
        ),
        bridge.registry,
    )

    assert result.exit_code == 0
    assert result.stderr == ""
    assert parse_csv_records(destination.read_text(encoding="utf-8")) == (
        {"id": "a"},
        {"id": "b"},
    )


def test_cli_convert_preserves_complete_source_receipt_wire(tmp_path) -> None:
    source = _fixture_adapter(
        connector_id="convert_source_fixture",
        schemes=("convert-source",),
        vendor_receipt_ref="convert-source-fixture-receipt",
    )
    destination = tmp_path / "converted.json"

    result = run_cli_command(
        _args(
            "convert",
            from_value="convert-source://fixture/orders",
            to_value=str(destination),
            output_format="json",
        ),
        ConnectorRegistry([source]),
    )

    payload = strict_json_loads(result.stdout)
    assert result.exit_code == 0
    assert result.stderr == ""
    assert set(payload) == {
        "status",
        "rows_read",
        "rows",
        "rows_written",
        "source_receipt",
        "receipt",
    }
    _assert_full_receipt_wire(
        payload["source_receipt"],
        connector_id="convert_source_fixture",
        capability_id="table.read.arrow",
        operation_id="convert_source_fixture-read-operation",
        safe_uri="convert-source://fixture/orders",
        source_revision="convert_source_fixture-read-revision",
        vendor_receipt_ref="convert-source-fixture-receipt",
    )
    assert payload["receipt"] == payload["source_receipt"]
    assert strict_json_loads(destination.read_text(encoding="utf-8")) == list(
        _TABLE_ROWS
    )


def test_cli_import_preserves_exact_source_and_destination_receipts() -> None:
    source = _fixture_adapter(
        connector_id="source_fixture",
        schemes=("source",),
        vendor_receipt_ref="source-fixture-receipt",
    )
    destination = _fixture_adapter(
        connector_id="destination_fixture",
        schemes=("destination",),
        vendor_receipt_ref="destination-fixture-receipt",
    )
    registry = ConnectorRegistry([source, destination])

    result = run_cli_command(
        _args(
            "import",
            from_value="source://fixture/orders",
            to_value="destination://fixture/archive",
            if_exists="append",
            output_format="json",
        ),
        registry,
    )

    payload = strict_json_loads(result.stdout)
    assert result.exit_code == 0
    assert result.stderr == ""
    assert payload["status"] == "completed"
    assert payload["rows_read"] == payload["rows_written"] == 2
    assert set(payload) == {
        "status",
        "rows_read",
        "rows",
        "rows_written",
        "source_receipt",
        "receipt",
        "destination_receipt",
    }
    _assert_full_receipt_wire(
        payload["source_receipt"],
        connector_id="source_fixture",
        capability_id="table.read.arrow",
        operation_id="source_fixture-read-operation",
        safe_uri="source://fixture/orders",
        source_revision="source_fixture-read-revision",
        vendor_receipt_ref="source-fixture-receipt",
    )
    assert payload["receipt"] == payload["source_receipt"]
    _assert_full_receipt_wire(
        payload["destination_receipt"],
        connector_id="destination_fixture",
        capability_id="table.write",
        operation_id="destination_fixture-write-operation",
        safe_uri="destination://fixture/archive",
        source_revision="destination_fixture-write-revision",
        vendor_receipt_ref="destination-fixture-receipt",
    )
    assert source.read_calls[0].endpoint.raw == "source://fixture/orders"
    assert destination.preflight_calls[0].endpoint.raw == "destination://fixture/archive"
    assert destination.write_calls[0].endpoint.raw == "destination://fixture/archive"
    assert destination.write_calls[0].table.to_pylist() == list(_TABLE_ROWS)
    assert destination.write_calls[0].options == CliOptions(
        output_format=FormatName.JSON,
        if_exists="append",
    )


def test_cli_limit_and_timeout_reach_google_transport_and_bound_rows() -> None:
    bridge = build_cli_registry_bridge("google_sheets")

    result = run_cli_command(
        _args(
            "read",
            from_value="gsheets://fixture-spreadsheet/Orders",
            token=_FIXTURE_SECRET,
            limit=2,
            timeout=2.2,
        ),
        bridge.registry,
    )

    events = parse_json_lines(result.stdout)
    request = bridge.cases["google_sheets"].http_fixture.transport.requests[0]
    assert result.exit_code == 0
    assert [event["event"] for event in events] == ["row", "row", "summary"]
    assert request.method == "GET"
    assert request.timeout == 3
    assert request.url == (
        "https://sheets.googleapis.com/v4/spreadsheets/fixture-spreadsheet/"
        "values/Orders?majorDimension=ROWS"
    )
    assert request.headers == {"Authorization": f"Bearer {_FIXTURE_SECRET}"}
    assert _FIXTURE_SECRET not in result.stdout + result.stderr


def test_cli_sheet_and_range_reach_google_adapter_as_exact_value_ranges() -> None:
    bridge = build_cli_registry_bridge("google_sheets")
    source = "gsheets://fixture-spreadsheet/Default"

    sheet_result = run_cli_command(
        _args(
            "read",
            from_value=source,
            token=_FIXTURE_SECRET,
            sheet="Orders Sheet",
            limit=1,
            timeout=2.2,
        ),
        bridge.registry,
    )
    range_result = run_cli_command(
        _args(
            "read",
            from_value=source,
            token=_FIXTURE_SECRET,
            sheet="Ignored Sheet",
            range="Orders!A1:B2",
            limit=1,
            timeout=4.1,
        ),
        bridge.registry,
    )

    requests = bridge.cases["google_sheets"].http_fixture.transport.requests
    assert sheet_result.exit_code == range_result.exit_code == 0
    assert sheet_result.stderr == range_result.stderr == ""
    assert requests == [
        RecordedRequest(
            method="GET",
            url=(
                "https://sheets.googleapis.com/v4/spreadsheets/fixture-spreadsheet/"
                "values/Orders%20Sheet?majorDimension=ROWS"
            ),
            headers={"Authorization": f"Bearer {_FIXTURE_SECRET}"},
            body=None,
            timeout=3,
        ),
        RecordedRequest(
            method="GET",
            url=(
                "https://sheets.googleapis.com/v4/spreadsheets/fixture-spreadsheet/"
                "values/Orders%21A1%3AB2?majorDimension=ROWS"
            ),
            headers={"Authorization": f"Bearer {_FIXTURE_SECRET}"},
            body=None,
            timeout=5,
        ),
    ]
    assert _FIXTURE_SECRET not in (
        sheet_result.stdout
        + sheet_result.stderr
        + range_result.stdout
        + range_result.stderr
    )


def test_parse_csv_records_rejects_rows_with_missing_cells() -> None:
    with pytest.raises(AssertionError, match="fewer values than the header"):
        parse_csv_records("id,amount,note\n1,2.50\n")


def test_cli_field_names_reach_feishu_adapter_and_filter_exact_columns() -> None:
    bridge = build_cli_registry_bridge("feishu_bitable")

    result = run_cli_command(
        _args(
            "read",
            from_value="feishu://fixture-app/orders",
            token=_FIXTURE_SECRET,
            field_name=["name", "note"],
            limit=2,
            output_format="json",
        ),
        bridge.registry,
    )

    payload = strict_json_loads(result.stdout)
    fixture = bridge.cases["feishu_bitable"].http_fixture
    assert result.exit_code == 0
    assert payload["rows"] == [
        {"_record_id": "rec_1", "name": "Ada", "note": "first"},
        {"_record_id": "rec_2", "name": "Lin", "note": None},
    ]
    assert fixture.transport.used_fields == ("name", "note")
    assert fixture.transport.requests[0].url == (
        "https://open.feishu.cn/open-apis/bitable/v1/apps/fixture-app/"
        "tables/orders/records?page_size=500"
    )


def test_cli_target_reaches_maybe_sheet_process_boundary() -> None:
    bridge = build_cli_registry_bridge("maybe_sheet")

    result = run_cli_command(
        _args(
            "read",
            from_value="https://www.maybe.ai/docs/spreadsheets/d/fixture-doc",
            token=_FIXTURE_SECRET,
            target="R_orders",
            limit=2,
            timeout=4,
        ),
        bridge.registry,
    )

    call = bridge.cases["maybe_sheet"].process_fixture.process.calls[0]
    assert result.exit_code == 0
    assert call.argv == (
        "mbs",
        "db-table",
        "read",
        "--uri",
        "https://www.maybe.ai/docs/spreadsheets/d/fixture-doc",
        "--target",
        "R_orders",
        "--limit",
        "2",
    )
    assert call.credentials == {"access_token": _FIXTURE_SECRET}
    assert call.timeout == 4
    assert _FIXTURE_SECRET not in result.stdout + result.stderr


def test_cli_if_exists_reaches_destination_preflight_and_write() -> None:
    source = _fixture_adapter(connector_id="source", schemes=("source",))
    destination = _fixture_adapter(connector_id="sink", schemes=("sink",))

    result = run_cli_command(
        _args(
            "import",
            from_value="source://fixture/orders",
            to_value="sink://fixture/orders",
            if_exists="replace",
        ),
        ConnectorRegistry([source, destination]),
    )

    assert result.exit_code == 0
    assert destination.preflight_calls[0].options.if_exists == "replace"
    assert destination.write_calls[0].options.if_exists == "replace"
    assert destination.write_calls[0].table.to_pylist() == list(_TABLE_ROWS)


def test_cli_provider_source_format_override_is_rejected_before_io() -> None:
    source = _fixture_adapter(connector_id="provider", schemes=("provider",))

    result = run_cli_command(
        _args(
            "read",
            from_value="provider://fixture/orders",
            from_format="csv",
        ),
        ConnectorRegistry([source]),
    )

    payload = strict_json_loads(result.stderr)
    assert result.exit_code == 3
    assert result.stdout == ""
    assert payload == {
        "code": "unsupported_capability",
        "message": "connector sources do not support --from-format; omit the override",
        "safe_details": {
            "scheme": "provider",
            "option": "from-format",
            "format": "csv",
        },
    }
    assert source.read_calls == []
    assert source.inspect_calls == []
    assert source.preflight_calls == []
    assert source.write_calls == []


def test_cli_provider_destination_format_override_is_rejected_before_any_io() -> None:
    source = _fixture_adapter(connector_id="source", schemes=("source",))
    destination = _fixture_adapter(connector_id="provider", schemes=("provider",))

    result = run_cli_command(
        _args(
            "import",
            from_value="source://fixture/orders",
            to_value="provider://fixture/orders",
            to_format="json",
        ),
        ConnectorRegistry([source, destination]),
    )

    payload = strict_json_loads(result.stderr)
    assert result.exit_code == 3
    assert result.stdout == ""
    assert payload["safe_details"] == {
        "scheme": "provider",
        "option": "to-format",
        "format": "json",
    }
    assert source.read_calls == []
    assert destination.preflight_calls == []
    assert destination.write_calls == []


def test_cli_unknown_scheme_uses_stable_unsupported_exit_code() -> None:
    result = run_cli_command(
        _args("read", from_value="unknown://fixture/orders"),
        ConnectorRegistry([]),
    )

    assert result.exit_code == 3
    assert result.stdout == ""
    assert strict_json_loads(result.stderr) == {
        "code": "unsupported_capability",
        "message": "no connector advertises this endpoint scheme",
        "safe_details": {"scheme": "unknown"},
    }


def test_cli_missing_write_capability_uses_stable_exit_code_before_source_read() -> None:
    source = _fixture_adapter(connector_id="source", schemes=("source",))
    destination = _fixture_adapter(
        connector_id="read_only",
        schemes=("readonly",),
        capabilities=("table.read.arrow", "table.inspect"),
    )

    result = run_cli_command(
        _args(
            "import",
            from_value="source://fixture/orders",
            to_value="readonly://fixture/orders",
        ),
        ConnectorRegistry([source, destination]),
    )

    payload = strict_json_loads(result.stderr)
    assert result.exit_code == 3
    assert payload["safe_details"] == {
        "scheme": "readonly",
        "capability": "table.write",
    }
    assert source.read_calls == []
    assert destination.preflight_calls == []
    assert destination.write_calls == []


@pytest.mark.parametrize(
    "format_name",
    (
        pytest.param("csv", id="truthful-csv"),
        pytest.param("json", id="truthful-json"),
        pytest.param("jsonl", id="truthful-jsonl"),
        pytest.param("table", id="truthful-table"),
    ),
)
def test_cli_read_output_is_truthful_for_selected_codec(format_name: str) -> None:
    adapter = _fixture_adapter()

    result = run_cli_command(
        _args(
            "read",
            from_value="fixture://source/orders",
            output_format=format_name,
            token=_FIXTURE_SECRET,
        ),
        ConnectorRegistry([adapter]),
    )

    assert result.exit_code == 0
    assert result.stderr == ""
    assert _FIXTURE_SECRET not in result.stdout
    if format_name == "csv":
        assert parse_csv_records(result.stdout) == _TABLE_ROWS
    elif format_name == "json":
        assert strict_json_loads(result.stdout)["rows"] == list(_TABLE_ROWS)
    elif format_name == "jsonl":
        events = parse_json_lines(result.stdout)
        assert tuple(event["row"] for event in events[:-1]) == _TABLE_ROWS
        assert events[-1]["event"] == "summary"
    else:
        assert parse_markdown_table(result.stdout) == (
            ("id", "amount", "note"),
            (("1", "2.50", "left|right"), ("2", "", "line1\nline2")),
        )


def test_cli_malformed_local_input_redacts_token_like_content(tmp_path) -> None:
    source = tmp_path / "malformed.json"
    source.write_text('[{"id":"fixture-cli-token"}', encoding="utf-8")
    bridge = build_cli_registry_bridge("local_files")

    result = run_cli_command(
        _args(
            "read",
            from_value=str(source),
            from_format="json",
            token=_FIXTURE_SECRET,
        ),
        bridge.registry,
    )

    payload = strict_json_loads(result.stderr)
    assert result.exit_code == 5
    assert result.stdout == ""
    assert payload["code"] == "execution_failed"
    assert payload["message"] == "JSON input is malformed"
    assert _FIXTURE_SECRET not in result.stderr


def test_cli_authentication_failure_redacts_fixture_token_before_output() -> None:
    failure = ConnectorError.authentication(
        "fixture provider authentication failed",
        safe_details={"token": _FIXTURE_SECRET, "provider": "fixture"},
    )
    adapter = _fixture_adapter(failures={"read": failure})

    result = run_cli_command(
        _args(
            "read",
            from_value="fixture://source/orders",
            token=_FIXTURE_SECRET,
        ),
        ConnectorRegistry([adapter]),
    )

    assert result.exit_code == 4
    assert result.stdout == ""
    assert strict_json_loads(result.stderr) == {
        "code": "authentication",
        "message": "fixture provider authentication failed",
        "safe_details": {"provider": "fixture"},
    }
    assert _FIXTURE_SECRET not in result.stderr


def test_cli_conflict_failure_redacts_fixture_token_and_skips_source_read() -> None:
    source = _fixture_adapter(connector_id="source", schemes=("source",))
    conflict = ConnectorError(
        ConnectorErrorCode.CONFLICT,
        "destination already contains rows",
        {"token": _FIXTURE_SECRET, "scheme": "sink"},
    )
    destination = _fixture_adapter(
        connector_id="sink",
        schemes=("sink",),
        failures={"preflight": conflict},
    )

    result = run_cli_command(
        _args(
            "import",
            from_value="source://fixture/orders",
            to_value="sink://fixture/orders",
            token=_FIXTURE_SECRET,
        ),
        ConnectorRegistry([source, destination]),
    )

    assert result.exit_code == 6
    assert result.stdout == ""
    assert strict_json_loads(result.stderr)["safe_details"] == {"scheme": "sink"}
    assert source.read_calls == []
    assert len(destination.preflight_calls) == 1
    assert destination.write_calls == []
    assert _FIXTURE_SECRET not in result.stderr


def test_cli_raw_provider_exception_redacts_token_but_records_exact_boundary() -> None:
    raw_failure = RawProviderFailure(
        f"upstream transport exposed {_FIXTURE_SECRET}",
        credential=_FIXTURE_SECRET,
    )
    transport = RecordingSheetsTransport(
        {"GET": {"values": []}},
        failure=raw_failure,
    )
    connector = GoogleSheetsConnector(transport=transport, access_token=None)
    adapter = GoogleSheetsAdapter(connector, transport=transport)

    result = run_cli_command(
        _args(
            "read",
            from_value="gsheets://fixture-spreadsheet/Orders",
            token=_FIXTURE_SECRET,
        ),
        ConnectorRegistry([adapter]),
    )

    assert _FIXTURE_SECRET in str(raw_failure)
    assert result.exit_code == 5
    assert result.stdout == ""
    assert strict_json_loads(result.stderr) == {
        "code": "execution",
        "message": "command failed",
        "safe_details": {},
    }
    assert transport.requests[0].url == (
        "https://sheets.googleapis.com/v4/spreadsheets/fixture-spreadsheet/"
        "values/Orders?majorDimension=ROWS"
    )
    assert transport.requests[0].headers == {
        "Authorization": f"Bearer {_FIXTURE_SECRET}"
    }
    assert _FIXTURE_SECRET not in result.stderr


@pytest.mark.parametrize(
    "format_name",
    (
        pytest.param("csv", id="stdout-csv-only"),
        pytest.param("json", id="stdout-json-only"),
        pytest.param("jsonl", id="stdout-jsonl-only"),
        pytest.param("table", id="stdout-table-only"),
    ),
)
def test_cli_convert_stdout_is_owned_only_by_selected_codec(format_name: str) -> None:
    adapter = _fixture_adapter()

    result = run_cli_command(
        _args(
            "convert",
            from_value="fixture://source/orders",
            to_value="-",
            to_format=format_name,
            output_format="jsonl",
        ),
        ConnectorRegistry([adapter]),
    )

    assert result.exit_code == 0
    assert result.stderr == ""
    assert "rows_written" not in result.stdout
    assert "source_receipt" not in result.stdout
    if format_name == "csv":
        assert parse_csv_records(result.stdout) == _TABLE_ROWS
    elif format_name == "json":
        assert strict_json_loads(result.stdout) == list(_TABLE_ROWS)
    elif format_name == "jsonl":
        assert parse_json_lines(result.stdout) == _TABLE_ROWS
    else:
        assert parse_markdown_table(result.stdout) == (
            ("id", "amount", "note"),
            (("1", "2.50", "left|right"), ("2", "", "line1\nline2")),
        )


@pytest.mark.parametrize(
    "format_name",
    (
        pytest.param("jsonl", id="deterministic-jsonl"),
        pytest.param("table", id="deterministic-table"),
    ),
)
def test_cli_repeated_reads_emit_deterministic_jsonl_and_table(format_name: str) -> None:
    adapter = _fixture_adapter()
    registry = ConnectorRegistry([adapter])
    args = _args(
        "read",
        from_value="fixture://source/orders",
        output_format=format_name,
    )

    first = run_cli_command(args, registry)
    second = run_cli_command(args, registry)

    assert first.exit_code == second.exit_code == 0
    assert first.stderr == second.stderr == ""
    assert first.stdout == second.stdout
    if format_name == "jsonl":
        assert len(parse_json_lines(first.stdout)) == 3
    else:
        assert parse_markdown_table(first.stdout)[1] == (
            ("1", "2.50", "left|right"),
            ("2", "", "line1\nline2"),
        )


def test_otc_parser_error_is_one_safe_json_record_and_redacts_token(
    tmp_path,
    sanitized_subprocess_env: dict[str, str],
) -> None:
    source = tmp_path / "rows.csv"
    source.write_text("id\na\n", encoding="utf-8")

    completed = subprocess.run(
        [
            "uv",
            "run",
            "otc",
            "import",
            "--from",
            str(source),
            "--token",
            _FIXTURE_SECRET,
        ],
        capture_output=True,
        text=True,
        check=False,
        env=sanitized_subprocess_env,
    )

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert len(completed.stderr.splitlines()) == 1
    payload = strict_json_loads(completed.stderr)
    assert payload["code"] == "usage"
    assert payload["safe_details"] == {"flags": ["--to"]}
    assert _FIXTURE_SECRET not in completed.stderr


def test_otc_entry_point_parses_from_to_and_emits_only_requested_codec(
    tmp_path,
    sanitized_subprocess_env: dict[str, str],
) -> None:
    source = tmp_path / "rows.csv"
    source.write_text("id,amount\na,1\n", encoding="utf-8")

    completed = subprocess.run(
        [
            "uv",
            "run",
            "otc",
            "convert",
            "--from",
            str(source),
            "--to",
            "-",
            "--to-format",
            "jsonl",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=sanitized_subprocess_env,
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert parse_json_lines(completed.stdout) == ({"amount": "1", "id": "a"},)
    assert "rows_written" not in completed.stdout
