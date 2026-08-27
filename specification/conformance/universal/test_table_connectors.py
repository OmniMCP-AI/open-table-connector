from __future__ import annotations

from dataclasses import dataclass
import json
import string

import polars as pl
import pytest

from open_connectors.contract import (
    ArrowReadResult,
    BaseConvention,
    ConnectorError,
    ConnectorErrorCode,
    ResourceLimits,
    SheetConvention,
    TableMode,
    TableURI,
)
from open_connectors.local_files import LocalReadOptions, LocalTableReadRequest

from specification.conformance.universal.assertions import (
    assert_error_is_safe,
    assert_receipt_matches_table,
)
from specification.conformance.universal.cases import (
    CapabilityBinding,
    ConnectorCase,
    case,
    cases_with,
)
from specification.conformance.universal.fixtures import (
    RecordingProcessClient,
    RecordingSheetsTransport,
    UniversalFixtureBundle,
)


_TABLE_CASE_NAMES = frozenset(
    {"local_files", "google_sheets", "feishu_bitable", "maybesheet"}
)


def _case_names_with(capability: str) -> tuple[str, ...]:
    return tuple(
        item.name for item in cases_with(capability) if item.name in _TABLE_CASE_NAMES
    )


@dataclass(frozen=True)
class ReadScenario:
    case_name: str
    read_capability: str
    inspect_capability: str
    expected_columns: tuple[str, ...]
    expected_mode: TableMode

    @property
    def id(self) -> str:
        return f"{self.case_name}:{self.read_capability}"


_READ_SCENARIOS = (
    *(
        ReadScenario(
            case_name=name,
            read_capability="table.read.arrow",
            inspect_capability="table.inspect",
            expected_columns=(
                ("_record_id", "name", "score", "note")
                if name == "feishu_bitable"
                else ("id", "amount", "note")
            ),
            expected_mode=(
                TableMode.BASE if name == "feishu_bitable" else TableMode.SHEET
            ),
        )
        for name in _case_names_with("table.read.arrow")
    ),
    *(
        ReadScenario(
            case_name=name,
            read_capability="base.read",
            inspect_capability="base.inspect",
            expected_columns=("id", "amount", "note"),
            expected_mode=TableMode.BASE,
        )
        for name in _case_names_with("base.read")
    ),
    *(
        ReadScenario(
            case_name=name,
            read_capability="sheet.read",
            inspect_capability="sheet.inspect",
            expected_columns=("id", "amount", "note"),
            expected_mode=TableMode.SHEET,
        )
        for name in _case_names_with("sheet.read")
    ),
)

_WRITE_CASE_NAMES = tuple(
    name for name in _case_names_with("table.write") if name != "local_files"
)


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
    assert convention.sheet in {"data", "orders", "Orders"}


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
    tuple(
        name
        for name in _case_names_with("table.read.arrow")
        if name in {"google_sheets", "feishu_bitable"}
    ),
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

    recording = connector_case.recording
    assert isinstance(recording, RecordingSheetsTransport)
    assert recording.requests
    assert all(request.method == "GET" for request in recording.requests)
    assert all(request.timeout == 3 for request in recording.requests)
    assert all(request.body is None for request in recording.requests)
    authorization = recording.requests[0].headers["Authorization"]
    assert authorization.startswith("Bearer ")
    secret = authorization.removeprefix("Bearer ")
    _assert_credential_is_local(
        secret,
        tuple(request.url for request in recording.requests),
        result.receipt.to_wire(),
    )
    if connector_case.name == "google_sheets":
        assert len(recording.requests) == 1
        assert "Orders%21A1%3AC5" in recording.requests[0].url
        assert recording.selections[-1].range == "Orders!A1:C5"
    else:
        assert len(recording.requests) == 2
        assert "page_size=500" in recording.requests[0].url
        assert "page_token=fixture-page-2" in recording.requests[1].url
        assert recording.selections[-1].fields == ("name", "score", "note")


@pytest.mark.parametrize(
    "capability", ("base.read", "sheet.read"), ids=("base", "sheet")
)
def test_maybesheet_reads_record_argv_timeout_target_limit_and_credentials(
    capability: str,
) -> None:
    connector_case = case("maybesheet")
    binding = connector_case.capability_binding(capability)
    assert binding.read_arrow is not None

    result = binding.read_arrow(ResourceLimits(max_rows=2, timeout_seconds=3))

    recording = connector_case.recording
    assert isinstance(recording, RecordingProcessClient)
    call = recording.calls[-1]
    expected_verb = "db-table" if capability == "base.read" else "excel-worksheet"
    expected_target = "R_orders" if capability == "base.read" else "Orders"
    assert call.argv[:3] == ("mbs", expected_verb, "read")
    assert call.argv[-4:] == ("--target", expected_target, "--limit", "2")
    assert call.timeout == 3
    assert set(call.credentials) == {"access_token"}
    secret = call.credentials["access_token"]
    _assert_credential_is_local(secret, call.argv, call.stdin, result.receipt.to_wire())


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
    recording = connector_case.recording
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
        pytest.param("google_sheets", "error", id="google-sheets:error"),
        pytest.param("google_sheets", "append", id="google-sheets:append"),
        pytest.param("google_sheets", "replace", id="google-sheets:replace"),
        pytest.param("feishu_bitable", "error", id="feishu-bitable:error"),
        pytest.param("feishu_bitable", "append", id="feishu-bitable:append"),
        pytest.param("maybesheet", "append", id="maybesheet:append"),
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
        pytest.param("maybesheet", "error", id="maybesheet:error"),
        pytest.param("maybesheet", "replace", id="maybesheet:replace"),
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
    recording = connector_case.recording
    calls = (
        recording.requests
        if isinstance(recording, RecordingSheetsTransport)
        else recording.calls
    )
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

    recording = connector_case.recording
    assert isinstance(recording, RecordingSheetsTransport)
    request = recording.requests[-1]
    assert request.method == ("POST" if policy == "append" else "PUT")
    assert "Orders%21A1%3AC5" in request.url
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
    authorization = request.headers["Authorization"]
    assert authorization.startswith("Bearer ")
    _assert_credential_is_local(
        authorization.removeprefix("Bearer "),
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

    recording = connector_case.recording
    assert isinstance(recording, RecordingSheetsTransport)
    request = recording.requests[-1]
    assert request.method == "POST"
    assert request.url.endswith("/records/batch_create")
    assert request.timeout == 30
    assert request.body == {
        "records": [
            {"fields": {"id": "write-1", "amount": "3.50"}},
            {"fields": {"id": "write-2", "amount": "4.00"}},
        ]
    }
    authorization = request.headers["Authorization"]
    assert authorization.startswith("Bearer ")
    _assert_credential_is_local(
        authorization.removeprefix("Bearer "),
        request.url,
        request.body,
        result.receipt.to_wire(),
    )


def test_maybesheet_write_records_stdin_jsonl_argv_and_credential_locality(
    write_frame: pl.DataFrame,
) -> None:
    connector_case = case("maybesheet")
    assert connector_case.write is not None

    result = connector_case.write(write_frame, "append")

    recording = connector_case.recording
    assert isinstance(recording, RecordingProcessClient)
    call = recording.calls[-1]
    assert call.argv == (
        "mbs",
        "db-table",
        "write",
        "--uri",
        "https://www.maybe.ai/docs/spreadsheets/d/fixture-doc",
        "--target",
        "R_orders",
        "--input",
        "-",
    )
    assert call.timeout is None
    assert [json.loads(line) for line in call.stdin.splitlines()] == [
        {"id": "write-1", "amount": "3.50"},
        {"id": "write-2", "amount": "4.00"},
    ]
    assert set(call.credentials) == {"access_token"}
    _assert_credential_is_local(
        call.credentials["access_token"],
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
            "maybesheet",
            ConnectorErrorCode.EXECUTION_FAILED,
            id="maybesheet:process-error",
        ),
    ),
)
def test_provider_failures_map_to_safe_redacted_errors(
    case_name: str,
    expected_code: ConnectorErrorCode,
) -> None:
    connector_case = case(case_name)
    failure = connector_case.provider_failure
    assert failure is not None

    with pytest.raises(ConnectorError) as raised:
        failure()

    assert raised.value.code is expected_code
    assert_error_is_safe(
        raised.value,
        forbidden_values=("fixture-token", "fixture-secret"),
    )


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
    ),
)
def test_local_table_formats_preserve_empty_cells_mixed_values_and_coordinates(
    format_name: str,
    expected_rows: list[dict[str, str | None]],
    expected_sheet: str,
    isolated_universal_fixture_bundle: UniversalFixtureBundle,
) -> None:
    connector_case = case("local_files")
    path = (
        isolated_universal_fixture_bundle.csv_path
        if format_name == "csv"
        else isolated_universal_fixture_bundle.xlsx_path
    )
    request = LocalTableReadRequest(
        TableURI(path.as_uri()),
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
