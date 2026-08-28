import io
import sys

import pytest

from open_table_connector.cli.model import CliOptions, parse_endpoint
from open_table_connector.cli.registry import build_default_registry
from open_table_connector.contract import ConnectorError, ConnectorErrorCode, TableMode


class Transport:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def request(self, method, url, *, headers, body=None, timeout=None):
        self.calls.append((method, url, headers, body, timeout))
        return self.payload


class Process:
    def __init__(self):
        self.calls = []

    def run(self, argv, *, credentials=None, stdin=None):
        self.calls.append((argv, credentials, stdin))
        return {"rows": [{"id": "1"}]}


def test_default_registry_lists_all_supported_adapter_schemes() -> None:
    schemes = {scheme for adapter in build_default_registry(env={}).list() for scheme in adapter.schemes}
    assert {"gsheets", "https", "feishu", "feishu_bitable", "maybe", "file"}.issubset(schemes)


def test_registry_dispatches_google_sheet_uri() -> None:
    adapter = build_default_registry(env={}).connector_for(parse_endpoint("gsheets://book/Orders"))
    assert adapter.identity.connector_id == "google_sheets"


def test_registry_reports_unsupported_capability_before_writing() -> None:
    registry = build_default_registry(env={})
    with pytest.raises(ConnectorError) as error:
        registry.require_capability(parse_endpoint("maybe://doc/target"), "table.replace")
    assert error.value.code is ConnectorErrorCode.UNSUPPORTED_CAPABILITY


def test_google_adapter_translates_options_and_uses_cli_token() -> None:
    transport = Transport({"values": [["id"], ["1"]]})
    registry = build_default_registry(
        env={"GOOGLE_SHEETS_ACCESS_TOKEN": "env-secret"},
        transports={"google_sheets": transport},
    )

    result = registry.connector_for(parse_endpoint("gsheets://book/Orders")).read(
        parse_endpoint("gsheets://book/Orders"),
        CliOptions(token="cli-secret", range="A1:B2", sheet="Orders"),
    )

    assert result.table.to_pylist() == [{"id": "1"}]
    assert transport.calls[0][2] == {"Authorization": "Bearer cli-secret"}
    assert "/values/A1%3AB2" in transport.calls[0][1]


def test_https_dispatch_rejects_unknown_hosts_without_calling_transport() -> None:
    registry = build_default_registry(env={})
    with pytest.raises(ConnectorError) as error:
        registry.connector_for(parse_endpoint("https://example.com/table"))
    assert error.value.code is ConnectorErrorCode.INVALID_URI
    assert error.value.safe_details == {"scheme": "https", "host": "example.com"}


def test_registry_reports_unknown_connector_scheme_as_unsupported_capability() -> None:
    registry = build_default_registry(env={})

    with pytest.raises(ConnectorError) as error:
        registry.connector_for(parse_endpoint("unknown://book/Orders"))

    assert error.value.code is ConnectorErrorCode.UNSUPPORTED_CAPABILITY
    assert error.value.safe_details == {"scheme": "unknown"}


def test_google_adapter_inspect_uses_options_and_injected_transport() -> None:
    transport = Transport({"values": [["id"], ["1"], ["2"]]})
    registry = build_default_registry(
        env={"GOOGLE_SHEETS_ACCESS_TOKEN": "google-secret"},
        transports={"google_sheets": transport},
    )
    endpoint = parse_endpoint("gsheets://book/Orders")

    inspection = registry.connector_for(endpoint).inspect(
        endpoint, CliOptions(token="cli-secret", limit=1, timeout=1.1)
    )

    assert inspection.columns == ("id",)
    assert inspection.row_count == 1
    assert transport.calls[0][2] == {"Authorization": "Bearer cli-secret"}
    assert transport.calls[0][4] == 2


def test_feishu_adapter_inspect_uses_options_and_injected_transport() -> None:
    transport = Transport({"code": 0, "data": {"items": [
        {"record_id": "r1", "fields": {"id": "1"}},
        {"record_id": "r2", "fields": {"id": "2"}},
    ]}})
    registry = build_default_registry(
        env={"FEISHU_TENANT_ACCESS_TOKEN": "feishu-secret"},
        transports={"feishu_bitable": transport},
    )
    endpoint = parse_endpoint("feishu://app/table")

    inspection = registry.connector_for(endpoint).inspect(
        endpoint, CliOptions(token="cli-secret", limit=1, timeout=1.1)
    )

    assert inspection.columns == ("_record_id", "id")
    assert inspection.row_count == 1
    assert transport.calls[0][2] == {"Authorization": "Bearer cli-secret"}
    assert transport.calls[0][4] == 2


def test_default_registry_exposes_base_modes_for_local_and_maybe_sheet() -> None:
    adapters = {adapter.identity.connector_id: adapter for adapter in build_default_registry(env={}).list()}

    assert adapters["local_files"].modes == (TableMode.BASE,)
    assert adapters["maybe_sheet"].modes == (TableMode.BASE,)


def test_maybe_sheet_sheet_capability_is_rejected_before_process_io() -> None:
    process = Process()
    registry = build_default_registry(transports={"maybe_sheet": process})

    with pytest.raises(ConnectorError) as error:
        registry.require_capability(parse_endpoint("maybe://doc/target"), "sheet.read")

    assert error.value.code is ConnectorErrorCode.UNSUPPORTED_CAPABILITY
    assert error.value.safe_details == {"scheme": "maybe", "capability": "sheet.read"}
    assert process.calls == []


def test_local_receipts_are_content_and_operation_specific(tmp_path) -> None:
    source = tmp_path / "orders.json"
    endpoint = parse_endpoint(str(source))
    adapter = build_default_registry(env={}).connector_for(endpoint)
    options = CliOptions(from_format="json")

    source.write_text('[{"id": 1}]')
    first = adapter.read(endpoint, options).receipt
    source.write_text('[{"id": 2}]')
    second = adapter.read(endpoint, options).receipt

    assert first.safe_uri.value == endpoint.path.resolve().as_uri()
    assert first.content_fingerprint != second.content_fingerprint
    assert first.source_revision != second.source_revision
    assert first.operation_id != second.operation_id


def test_local_inspection_uses_canonical_uri_and_receipt_revision(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    endpoint = parse_endpoint("orders.json")
    endpoint.path.write_text('[{"id": 1}]')
    adapter = build_default_registry(env={}).connector_for(endpoint)
    options = CliOptions(from_format="json")

    inspection = adapter.inspect(endpoint, options)
    receipt = adapter.read(endpoint, options).receipt

    assert inspection.safe_uri.value == endpoint.path.resolve().as_uri()
    assert inspection.coordinate_convention.ordinal_snapshot_id == receipt.source_revision


def test_local_stdin_inspection_uses_stable_uri_and_receipt_revision(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO('[{"id": 1}]'))
    endpoint = parse_endpoint("-")
    adapter = build_default_registry(env={}).connector_for(endpoint)

    inspection = adapter.inspect(endpoint, CliOptions(from_format="json"))

    assert inspection.safe_uri.value == "stdio://stdin"
    assert inspection.coordinate_convention.ordinal_snapshot_id.startswith("sha256:")


def test_registry_injects_maybe_sheet_process_transport() -> None:
    process = Process()
    registry = build_default_registry(transports={"maybe_sheet": process})

    adapter = registry.connector_for(parse_endpoint("maybe://doc/R_orders"))
    result = adapter.read(parse_endpoint("maybe://doc/R_orders"), CliOptions(token="cli-secret", limit=1))

    assert result.table.to_pylist() == [{"id": "1"}]
    assert process.calls[0] == (
        ("mbs", "db-table", "read", "--uri", "maybe://doc/R_orders", "--target", "R_orders", "--limit", "1"),
        {"access_token": "cli-secret"},
        None,
    )


def test_local_adapter_applies_limit_before_returning_rows(tmp_path) -> None:
    endpoint = parse_endpoint(str(tmp_path / "orders.json"))
    adapter = build_default_registry(env={}).connector_for(endpoint)
    options = CliOptions(from_format="json", limit=2)

    endpoint.path.write_text('[{"id": 1}, {"id": 2}, {"id": 3}]')
    result = adapter.read(endpoint, options)

    assert result.table.num_rows == 2
    assert result.receipt.row_count == 2


def test_maybe_sheet_https_document_requires_explicit_target_before_process_io() -> None:
    process = Process()
    registry = build_default_registry(transports={"maybe_sheet": process})
    endpoint = parse_endpoint("https://www.maybe.ai/docs/spreadsheets/d/doc")

    with pytest.raises(ConnectorError) as error:
        registry.connector_for(endpoint).read(endpoint, CliOptions())

    assert error.value.code is ConnectorErrorCode.INVALID_URI
    assert error.value.safe_details == {"option": "target"}
    assert process.calls == []


def test_maybe_sheet_https_document_uses_explicit_target() -> None:
    process = Process()
    registry = build_default_registry(transports={"maybe_sheet": process})
    endpoint = parse_endpoint("https://www.maybe.ai/docs/spreadsheets/d/doc")

    registry.connector_for(endpoint).read(endpoint, CliOptions(target="R_orders"))

    assert process.calls[0][0][-2:] == ("--target", "R_orders")


@pytest.mark.parametrize(
    "uri",
    (
        "maybe:///R_orders",
        "maybe://",
        "maybe://doc",
        "maybe://doc/",
        "maybe://doc/R_orders/extra",
    ),
)
def test_maybe_sheet_rejects_malformed_opaque_uris_before_process_io(uri) -> None:
    process = Process()
    registry = build_default_registry(transports={"maybe_sheet": process})
    endpoint = parse_endpoint(uri)

    with pytest.raises(ConnectorError) as error:
        registry.connector_for(endpoint).read(endpoint, CliOptions(target="R_orders"))

    assert error.value.code is ConnectorErrorCode.INVALID_URI
    assert error.value.safe_details == {"scheme": "maybe"}
    assert process.calls == []


def test_local_stdin_receipt_uses_stable_stdio_uri(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO('[{"id": 1}]'))
    endpoint = parse_endpoint("-")
    adapter = build_default_registry(env={}).connector_for(endpoint)

    result = adapter.read(endpoint, CliOptions(from_format="json"))

    assert result.receipt.safe_uri.value == "stdio://stdin"
