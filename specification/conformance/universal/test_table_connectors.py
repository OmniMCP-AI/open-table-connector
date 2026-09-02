from __future__ import annotations

import string
import subprocess
from dataclasses import dataclass
from pathlib import Path

import polars as pl
import pytest
from open_table_connector.contract import (
    ArrowReadResult,
    BaseConvention,
    ConnectorError,
    ConnectorErrorCode,
    ResourceLimits,
    SheetConvention,
    TableMode,
    TableURI,
)
from open_table_connector.local_files import LocalReadOptions, LocalTableReadRequest
from open_table_connector.maybe_sheet import SubprocessProcessClient

from specification.conformance.universal.assertions import (
    assert_error_is_safe,
    assert_receipt_matches_table,
)
from specification.conformance.universal.cases import (
    CapabilityBinding,
    ConnectorCase,
    case,
)
from specification.conformance.universal.fixtures import (
    RecordingFeishuTransport,
    RecordingProcessClient,
    RecordingSheetsTransport,
    UniversalFixtureBundle,
)


@dataclass(frozen=True)
class ReadScenario:
    case_name: str
    read_capability: str
    inspect_capability: str
    expected_columns: tuple[str, ...]
    expected_mode: TableMode
    expected_sheet: str | None = None

    @property
    def id(self) -> str:
        return f"{self.case_name}:{self.read_capability}"


_READ_SCENARIOS = (
    ReadScenario(
        "csv",
        "table.read.arrow",
        "table.inspect",
        ("id", "amount", "note"),
        TableMode.SHEET,
        "data",
    ),
    ReadScenario(
        "excel",
        "table.read.arrow",
        "table.inspect",
        ("id", "amount", "note"),
        TableMode.SHEET,
        "orders",
    ),
    ReadScenario(
        "md",
        "table.read.arrow",
        "table.inspect",
        ("id", "amount", "note"),
        TableMode.SHEET,
        "data",
    ),
    ReadScenario(
        "local_files",
        "table.read.arrow",
        "table.inspect",
        ("id", "amount", "note"),
        TableMode.SHEET,
        "data",
    ),
    ReadScenario(
        "google_sheets",
        "table.read.arrow",
        "table.inspect",
        ("id", "amount", "note"),
        TableMode.SHEET,
        "Orders",
    ),
    ReadScenario(
        "feishu_bitable",
        "table.read.arrow",
        "table.inspect",
        ("_record_id", "name", "score", "note"),
        TableMode.BASE,
    ),
    ReadScenario(
        "maybe_sheet",
        "base.read",
        "base.inspect",
        ("id", "amount", "note"),
        TableMode.BASE,
    ),
    ReadScenario(
        "maybe_sheet",
        "sheet.read",
        "sheet.inspect",
        ("id", "amount", "note"),
        TableMode.SHEET,
        "Orders",
    ),
)

_WRITE_CASE_NAMES = ("google_sheets", "feishu_bitable", "maybe_sheet")


def _read_arrow(
    scenario: ReadScenario,
    limits: ResourceLimits,
) -> tuple[ConnectorCase, CapabilityBinding, ArrowReadResult]:
    connector_case = case(scenario.case_name)
    binding = connector_case.capability_binding(scenario.read_capability)
    assert binding.read_arrow is not None
    return connector_case, binding, binding.read_arrow(limits)


def _read_polars_capability(scenario: ReadScenario) -> str:
    if scenario.read_capability == "table.read.arrow":
        return "table.read.polars"
    return scenario.read_capability


def _assert_credential_is_local(secret: str, *safe_values: object) -> None:
    if not secret:
        pytest.fail("recorded credential was empty")
    if any(secret in repr(value) for value in safe_values):
        pytest.fail("credential escaped its provider input state")


@pytest.mark.parametrize("scenario", _READ_SCENARIOS, ids=lambda item: item.id)
def test_table_read_arrow_bounds_over_returned_rows(scenario: ReadScenario) -> None:
    limits = ResourceLimits(max_rows=2, timeout_seconds=3)

    _, _, result = _read_arrow(scenario, limits)

    assert result.table.num_rows == 2
    assert result.receipt.row_count == 2
    assert result.receipt.batch_count == 1


@pytest.mark.parametrize("scenario", _READ_SCENARIOS, ids=lambda item: item.id)
def test_table_read_polars_matches_arrow_values_and_fingerprints(
    scenario: ReadScenario,
) -> None:
    limits = ResourceLimits(max_rows=2, timeout_seconds=3)
    connector_case, arrow_binding, arrow_result = _read_arrow(scenario, limits)
    polars_binding = connector_case.capability_binding(
        _read_polars_capability(scenario)
    )
    assert polars_binding.read_polars is not None

    polars_result = polars_binding.read_polars(limits)

    assert polars_result.frame.to_dicts() == arrow_result.table.to_pylist()
    assert polars_result.receipt.schema_fingerprint == (
        arrow_result.receipt.schema_fingerprint
    )
    assert polars_result.receipt.content_fingerprint == (
        arrow_result.receipt.content_fingerprint
    )
    assert polars_result.receipt.operation_id == arrow_result.receipt.operation_id
    assert arrow_binding.expected_mode is scenario.expected_mode


@pytest.mark.parametrize("scenario", _READ_SCENARIOS, ids=lambda item: item.id)
def test_table_reads_keep_provider_columns_stable(scenario: ReadScenario) -> None:
    _, _, result = _read_arrow(scenario, ResourceLimits())

    assert tuple(result.table.column_names) == scenario.expected_columns


@pytest.mark.parametrize("scenario", _READ_SCENARIOS, ids=lambda item: item.id)
def test_table_inspection_matches_the_bounded_read_schema(
    scenario: ReadScenario,
) -> None:
    limits = ResourceLimits(max_rows=2, timeout_seconds=3)
    connector_case, _, result = _read_arrow(scenario, limits)
    binding = connector_case.capability_binding(scenario.inspect_capability)
    assert binding.inspect is not None

    inspection = binding.inspect(limits)

    assert inspection.columns == tuple(result.table.column_names)
    assert inspection.schema_fingerprint == result.receipt.schema_fingerprint
    assert inspection.row_count == result.table.num_rows
    assert inspection.mode is scenario.expected_mode


@pytest.mark.parametrize("scenario", _READ_SCENARIOS, ids=lambda item: item.id)
def test_table_read_receipts_fingerprint_the_bounded_table(
    scenario: ReadScenario,
) -> None:
    connector_case, binding, result = _read_arrow(
        scenario,
        ResourceLimits(max_rows=2, timeout_seconds=3),
    )

    assert binding.expected_mode is scenario.expected_mode
    assert_receipt_matches_table(
        result.receipt,
        result.table,
        expected_connector=connector_case.identity,
        expected_capability=scenario.read_capability,
        expected_mode=scenario.expected_mode,
        expected_safe_uri=connector_case.table_uri,
    )
    assert result.receipt.source_revision.startswith(("sha256:", "fixture-"))
    for fingerprint in (
        result.receipt.schema_fingerprint,
        result.receipt.content_fingerprint,
    ):
        assert len(fingerprint) == 64
        assert set(fingerprint).issubset(set(string.hexdigits.casefold()))


@pytest.mark.parametrize(
    "scenario",
    tuple(item for item in _READ_SCENARIOS if item.expected_mode is TableMode.SHEET),
    ids=lambda item: item.id,
)
def test_sheet_reads_use_one_based_header_and_data_coordinates(
    scenario: ReadScenario,
) -> None:
    _, _, result = _read_arrow(scenario, ResourceLimits(max_rows=2))

    convention = result.receipt.coordinate_convention
    assert isinstance(convention, SheetConvention)
    assert convention.header_rows == 1
    assert convention.first_data_row == 2
    assert convention.sheet == scenario.expected_sheet


@pytest.mark.parametrize(
    "scenario",
    tuple(item for item in _READ_SCENARIOS if item.expected_mode is TableMode.BASE),
    ids=lambda item: item.id,
)
def test_base_reads_publish_record_or_snapshot_coordinates(
    scenario: ReadScenario,
) -> None:
    _, _, result = _read_arrow(scenario, ResourceLimits(max_rows=2))

    convention = result.receipt.coordinate_convention
    assert isinstance(convention, BaseConvention)
    if scenario.case_name == "feishu_bitable":
        assert convention.record_id_field == "_record_id"
    else:
        assert convention.ordinal_snapshot_id == result.receipt.source_revision


@pytest.mark.parametrize(
    "connector_case",
    ("google_sheets", "feishu_bitable"),
    ids=str,
    indirect=True,
)
def test_http_reads_record_method_url_timeout_selection_and_credential_locality(
    connector_case: ConnectorCase,
) -> None:
    limits = ResourceLimits(max_rows=2, timeout_seconds=3)
    binding = connector_case.capability_binding("table.read.arrow")
    assert binding.read_arrow is not None

    result = binding.read_arrow(limits)

    fixture = connector_case.http_fixture
    assert fixture is not None
    recording = fixture.transport
    assert isinstance(recording, RecordingSheetsTransport)
    assert recording.requests
    assert all(request.method == "GET" for request in recording.requests)
    assert all(request.timeout == 3 for request in recording.requests)
    assert all(request.body is None for request in recording.requests)
    assert all(
        request.headers == {"Authorization": "Bearer fixture-token"}
        for request in recording.requests
    )
    _assert_credential_is_local(
        "fixture-token",
        tuple(request.url for request in recording.requests),
        result.receipt.to_wire(),
    )
    if connector_case.name == "google_sheets":
        assert [request.url for request in recording.requests] == [
            "https://sheets.googleapis.com/v4/spreadsheets/fixture-spreadsheet/"
            "values/Orders%21A1%3AC5?majorDimension=ROWS"
        ]
    else:
        assert isinstance(recording, RecordingFeishuTransport)
        assert [request.url for request in recording.requests] == [
            "https://open.feishu.cn/open-apis/bitable/v1/apps/fixture-app/"
            "tables/orders/records?page_size=500",
            "https://open.feishu.cn/open-apis/bitable/v1/apps/fixture-app/"
            "tables/orders/records?page_size=500&page_token=fixture-page-2",
        ]
        assert recording.used_fields == (
            "name",
            "score",
            "note",
        )
        assert "internal_only" not in result.table.column_names


@pytest.mark.parametrize(
    "capability", ("base.read", "sheet.read"), ids=("base", "sheet")
)
def test_maybe_sheet_reads_record_argv_timeout_target_limit_and_credentials(
    capability: str,
) -> None:
    connector_case = case("maybe_sheet")
    binding = connector_case.capability_binding(capability)
    assert binding.read_arrow is not None

    result = binding.read_arrow(ResourceLimits(max_rows=2, timeout_seconds=3))

    fixture = connector_case.process_fixture
    assert fixture is not None
    recording = fixture.process
    assert isinstance(recording, RecordingProcessClient)
    call = recording.calls[-1]
    expected_argv = (
        (
            "mbs",
            "db-table",
            "read",
            "--uri",
            "https://www.maybe.ai/docs/spreadsheets/d/fixture-doc",
            "--name",
            "R_orders",
            "--limit",
            "2",
        )
        if capability == "base.read"
        else (
            "mbs",
            "excel-worksheet",
            "read",
            "--uri",
            "https://www.maybe.ai/docs/spreadsheets/d/fixture-doc",
            "--worksheet-name",
            "Orders",
        )
    )
    assert call.argv == expected_argv
    assert call.timeout == 3
    assert call.credentials == {"access_token": "fixture-token"}
    _assert_credential_is_local(
        "fixture-token", call.argv, call.stdin, result.receipt.to_wire()
    )


def test_recorded_http_responses_fail_closed_when_over_consumed() -> None:
    transport = RecordingSheetsTransport({"GET": {"values": []}})
    kwargs = {"headers": {"Authorization": "Bearer fixture-token"}}

    transport.request("GET", "https://fixture.invalid/first", **kwargs)

    with pytest.raises(AssertionError, match="over-consumed"):
        transport.request("GET", "https://fixture.invalid/second", **kwargs)


def test_feishu_paginates_and_preserves_record_ids_from_all_pages() -> None:
    connector_case = case("feishu_bitable")
    binding = connector_case.capability_binding("table.read.arrow")
    assert binding.read_arrow is not None

    result = binding.read_arrow(ResourceLimits(timeout_seconds=3))

    assert result.table.to_pylist() == [
        {"_record_id": "rec_1", "name": "Ada", "score": "10", "note": "first"},
        {"_record_id": "rec_2", "name": "Lin", "score": "9", "note": None},
        {"_record_id": "rec_3", "name": "Mei", "score": None, "note": "last"},
    ]
    fixture = connector_case.http_fixture
    assert fixture is not None
    recording = fixture.transport
    assert isinstance(recording, RecordingSheetsTransport)
    assert len(recording.requests) == 2


@pytest.mark.parametrize("connector_case", _WRITE_CASE_NAMES, ids=str, indirect=True)
def test_table_writes_report_exact_affected_rows(
    connector_case: ConnectorCase,
    write_frame: pl.DataFrame,
) -> None:
    assert connector_case.write is not None

    result = connector_case.write(write_frame, "append")

    assert result.affected_rows == 2
    assert result.receipt.row_count == 2


@pytest.mark.parametrize(
    ("case_name", "policy"),
    (
        pytest.param("google_sheets", "append", id="google-sheets:append"),
        pytest.param("google_sheets", "replace", id="google-sheets:replace"),
        pytest.param("feishu_bitable", "append", id="feishu-bitable:append"),
        pytest.param("maybe_sheet", "append", id="maybe_sheet:append"),
    ),
)
def test_table_writes_accept_each_supported_policy(
    case_name: str,
    policy: str,
    write_frame: pl.DataFrame,
) -> None:
    connector_case = case(case_name)
    assert connector_case.write is not None

    result = connector_case.write(write_frame, policy)

    assert result.receipt.row_count == 2


@pytest.mark.parametrize(
    ("case_name", "policy"),
    (
        pytest.param("feishu_bitable", "replace", id="feishu-bitable:replace"),
        pytest.param("feishu_bitable", "error", id="feishu-bitable:error"),
        pytest.param("google_sheets", "error", id="google-sheets:error"),
        pytest.param("maybe_sheet", "error", id="maybe_sheet:error"),
        pytest.param("maybe_sheet", "replace", id="maybe_sheet:replace"),
    ),
)
def test_table_writes_reject_unsupported_policies_before_provider_io(
    case_name: str,
    policy: str,
    write_frame: pl.DataFrame,
) -> None:
    connector_case = case(case_name)
    assert connector_case.write is not None

    with pytest.raises(ConnectorError) as raised:
        connector_case.write(write_frame, policy)

    assert raised.value.code is ConnectorErrorCode.UNSUPPORTED_CAPABILITY
    if connector_case.http_fixture is not None:
        calls = connector_case.http_fixture.transport.requests
    else:
        assert connector_case.process_fixture is not None
        calls = connector_case.process_fixture.process.calls
    assert calls == []


@pytest.mark.parametrize(
    "policy", ("append", "replace"), ids=("append", "replace")
)
def test_google_sheets_write_records_range_method_body_timeout_and_credentials(
    policy: str,
    write_frame: pl.DataFrame,
) -> None:
    connector_case = case("google_sheets")
    assert connector_case.write is not None

    result = connector_case.write(write_frame, policy)

    fixture = connector_case.http_fixture
    assert fixture is not None
    recording = fixture.transport
    assert isinstance(recording, RecordingSheetsTransport)
    request = recording.requests[-1]
    assert request.method == ("POST" if policy == "append" else "PUT")
    suffix = ":append" if policy == "append" else ""
    assert request.url == (
        "https://sheets.googleapis.com/v4/spreadsheets/fixture-spreadsheet/"
        f"values/Orders%21A1%3AC5{suffix}?valueInputOption=RAW&"
        "includeValuesInResponse=true"
    )
    assert request.timeout == 30
    assert request.body == {
        "range": "Orders!A1:C5",
        "majorDimension": "ROWS",
        "values": [
            ["id", "amount"],
            ["write-1", "3.50"],
            ["write-2", "4.00"],
        ],
    }
    assert request.headers == {"Authorization": "Bearer fixture-token"}
    _assert_credential_is_local(
        "fixture-token",
        request.url,
        request.body,
        result.receipt.to_wire(),
    )


def test_feishu_write_records_batch_shape_timeout_and_credentials(
    write_frame: pl.DataFrame,
) -> None:
    connector_case = case("feishu_bitable")
    assert connector_case.write is not None

    result = connector_case.write(write_frame, "append")

    fixture = connector_case.http_fixture
    assert fixture is not None
    recording = fixture.transport
    assert isinstance(recording, RecordingSheetsTransport)
    request = recording.requests[-1]
    assert request.method == "POST"
    assert request.url == (
        "https://open.feishu.cn/open-apis/bitable/v1/apps/fixture-app/"
        "tables/orders/records/batch_create"
    )
    assert request.timeout == 30
    assert request.body == {
        "records": [
            {"fields": {"id": "write-1", "amount": "3.50"}},
            {"fields": {"id": "write-2", "amount": "4.00"}},
        ]
    }
    assert request.headers == {"Authorization": "Bearer fixture-token"}
    _assert_credential_is_local(
        "fixture-token",
        request.url,
        request.body,
        result.receipt.to_wire(),
    )


def test_maybe_sheet_write_records_rows_file_argv_and_credential_locality(
    write_frame: pl.DataFrame,
) -> None:
    connector_case = case("maybe_sheet")
    assert connector_case.write is not None

    result = connector_case.write(write_frame, "append")

    fixture = connector_case.process_fixture
    assert fixture is not None
    recording = fixture.process
    assert isinstance(recording, RecordingProcessClient)
    call = recording.calls[-1]
    assert call.argv[:7] == (
        "mbs",
        "table",
        "insert",
        "--target",
        "https://www.maybe.ai/docs/spreadsheets/d/fixture-doc",
        "--table-name",
        "R_orders",
    )
    assert call.argv[7] == "--frame-in"
    assert Path(call.argv[8]).suffix == ".json"
    assert not Path(call.argv[8]).exists()
    assert call.argv[9:] == ("--output", "json")
    assert call.timeout is None
    assert call.stdin is None
    assert call.credentials == {"access_token": "fixture-token"}
    _assert_credential_is_local(
        "fixture-token",
        call.argv,
        call.stdin,
        result.receipt.to_wire(),
    )


@pytest.mark.parametrize(
    ("case_name", "expected_code"),
    (
        pytest.param(
            "google_sheets",
            ConnectorErrorCode.EXECUTION_FAILED,
            id="google-sheets:provider-error",
        ),
        pytest.param(
            "feishu_bitable",
            ConnectorErrorCode.EXECUTION_FAILED,
            id="feishu-bitable:provider-code",
        ),
        pytest.param(
            "maybe_sheet",
            ConnectorErrorCode.EXECUTION_FAILED,
            id="maybe_sheet:process-error",
        ),
    ),
)
def test_provider_failures_map_to_safe_redacted_errors(
    case_name: str,
    expected_code: ConnectorErrorCode,
) -> None:
    connector_case = case(case_name)
    fixture = connector_case.http_fixture or connector_case.process_fixture
    assert fixture is not None
    failure = fixture.failure
    assert not isinstance(failure.raw_failure, ConnectorError)
    if isinstance(failure.raw_failure, BaseException):
        assert failure.fixture_secret in str(failure.raw_failure)
    else:
        assert failure.fixture_secret in repr(failure.raw_failure)

    with pytest.raises(ConnectorError) as raised:
        failure.invoke()

    assert raised.value.code is expected_code
    assert raised.value.safe_details
    if case_name == "google_sheets":
        assert raised.value.safe_details == {
            "reason": "unexpected transport exception"
        }
    assert_error_is_safe(
        raised.value,
        forbidden_values=("fixture-token", "fixture-secret"),
    )


def test_maybe_sheet_does_not_expose_legacy_formula_aliases() -> None:
    connector = case("maybe_sheet").connector
    assert not hasattr(connector, "calculate_formulas")
    assert not hasattr(connector, "read_formula_values")


def test_maybe_sheet_process_timeouts_map_to_safe_stable_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def timeout(command: list[str], **kwargs: object) -> object:
        seen["command"] = command
        seen.update(kwargs)
        raise subprocess.TimeoutExpired(
            command,
            kwargs["timeout"],
            output="provider stdout exposed fixture-token",
            stderr="provider stderr exposed fixture-token",
        )

    monkeypatch.setattr(subprocess, "run", timeout)

    with pytest.raises(ConnectorError) as raised:
        SubprocessProcessClient(timeout_seconds=9).run(
            ("mbs", "db-table", "read"),
            credentials={"access_token": "fixture-token"},
            timeout=2.5,
        )

    provider_credentials = {
        key: value
        for key, value in seen["env"].items()
        if key
        in {
            "FEISHU_TENANT_ACCESS_TOKEN",
            "GOOGLE_SHEETS_ACCESS_TOKEN",
            "MAYBE_SHEET_ACCESS_TOKEN",
            "MAYBEAI_API_TOKEN",
        }
    }
    assert seen["command"] == ["mbs", "db-table", "read"]
    assert seen["check"] is False
    assert seen["capture_output"] is True
    assert seen["text"] is True
    assert seen["input"] is None
    assert seen["timeout"] == 2.5
    assert provider_credentials == {"MAYBEAI_API_TOKEN": "fixture-token"}

    cause = raised.value.__cause__
    assert isinstance(cause, subprocess.TimeoutExpired)
    assert cause.timeout == 2.5
    assert cause.output == "provider stdout exposed fixture-token"
    assert cause.stderr == "provider stderr exposed fixture-token"
    assert raised.value.to_wire() == {
        "code": "timeout",
        "message": "MaybeSheet process timed out",
        "safe_details": {"timeout_seconds": 2.5},
    }
    assert_error_is_safe(raised.value, forbidden_values=("fixture-token",))


@pytest.mark.parametrize(
    ("format_name", "expected_rows", "expected_sheet"),
    (
        pytest.param(
            "csv",
            [
                {"id": "1", "amount": "2.50", "note": "first"},
                {"id": "2", "amount": None, "note": None},
                {"id": "3", "amount": "7.00", "note": "last"},
            ],
            "data",
            id="csv",
        ),
        pytest.param(
            "xlsx",
            [
                {"id": "1", "amount": "2.5", "note": "first"},
                {"id": "2", "amount": None, "note": None},
                {"id": "3", "amount": "7", "note": "last"},
            ],
            "orders",
            id="xlsx",
        ),
        pytest.param(
            "md",
            [
                {"id": "1", "amount": "2.50", "note": "first"},
                {"id": "2", "amount": None, "note": None},
                {"id": "3", "amount": "7.00", "note": "last"},
            ],
            "data",
            id="md",
        ),
    ),
)
def test_local_table_formats_preserve_empty_cells_mixed_values_and_coordinates(
    format_name: str,
    expected_rows: list[dict[str, str | None]],
    expected_sheet: str,
    isolated_universal_fixture_bundle: UniversalFixtureBundle,
) -> None:
    connector_case = case("local_files")
    paths = {
        "csv": isolated_universal_fixture_bundle.csv_path,
        "xlsx": isolated_universal_fixture_bundle.xlsx_path,
        "md": isolated_universal_fixture_bundle.md_path,
    }
    request = LocalTableReadRequest(
        TableURI(paths[format_name].as_uri()),
        options=LocalReadOptions(sheet=None, header_row=1),
    )

    arrow_result = connector_case.connector.read_arrow(request)
    polars_result = connector_case.connector.read_polars(request)

    assert arrow_result.table.to_pylist() == expected_rows
    assert polars_result.frame.to_dicts() == expected_rows
    assert arrow_result.receipt.coordinate_convention.sheet == expected_sheet
    assert arrow_result.receipt.content_fingerprint == (
        polars_result.receipt.content_fingerprint
    )


def test_local_files_facade_reads_markdown_fixture_as_sheet_resource(
    isolated_universal_fixture_bundle: UniversalFixtureBundle,
) -> None:
    connector_case = case("local_files")
    request = LocalTableReadRequest(
        TableURI(isolated_universal_fixture_bundle.md_path.as_uri()),
        options=LocalReadOptions(header_row=1),
    )

    result = connector_case.connector.read_arrow(request)

    assert result.table.to_pylist() == [
        {"id": "1", "amount": "2.50", "note": "first"},
        {"id": "2", "amount": None, "note": None},
        {"id": "3", "amount": "7.00", "note": "last"},
    ]
    assert result.receipt.connector.connector_id == "local_files"
    assert result.receipt.coordinate_convention.sheet == "data"


@pytest.mark.parametrize("scenario", _READ_SCENARIOS, ids=lambda item: item.id)
def test_repeated_table_reads_are_deterministic(scenario: ReadScenario) -> None:
    connector_case = case(scenario.case_name)
    binding = connector_case.capability_binding(scenario.read_capability)
    assert binding.read_arrow is not None
    limits = ResourceLimits(max_rows=2, timeout_seconds=3)

    first = binding.read_arrow(limits)
    second = binding.read_arrow(limits)

    assert first.table.equals(second.table)
    assert first.receipt.to_wire() == second.receipt.to_wire()
