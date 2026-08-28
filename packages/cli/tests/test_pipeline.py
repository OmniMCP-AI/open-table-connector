import json
from dataclasses import dataclass

import pyarrow as pa
import pytest

from open_table_connector.cli.model import CliOptions, FormatName, parse_endpoint
from open_table_connector.cli.pipeline import convert_endpoint, import_endpoint, inspect_endpoint, read_endpoint
from open_table_connector.cli.registry import ConnectorRegistry, build_default_registry
from open_table_connector.contract import (
    CapabilityIdentity,
    ConnectorError,
    ConnectorErrorCode,
    ConnectorIdentity,
    NeutralReceipt,
    TableMode,
    TableURI,
    TableWriteResult,
)
from open_table_connector.contract.fingerprints import arrow_content_fingerprint


@dataclass
class RecordedCall:
    method: str
    url: str
    headers: dict[str, str]
    body: dict | None
    timeout: int | None


class RecordingTransport:
    def __init__(self, responses: dict[str, dict]) -> None:
        self.responses = responses
        self.calls: list[RecordedCall] = []

    def request(self, method, url, *, headers, body=None, timeout=None):
        self.calls.append(RecordedCall(method, url, dict(headers), body, timeout))
        return self.responses[method]


class RecordingProcess:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], object, str | None]] = []
        self.stdin_payload: str | None = None

    def run(self, argv, *, credentials=None, stdin=None):
        self.calls.append((argv, credentials, stdin))
        self.stdin_payload = stdin
        if argv[2] == "write":
            return {"rows_written": 1, "receipt_id": "write-ref"}
        return {"rows": [{"id": "a"}], "receipt_id": "read-ref"}


class OverReturningProcess:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], object, str | None]] = []

    def run(self, argv, *, credentials=None, stdin=None):
        self.calls.append((argv, credentials, stdin))
        return {
            "rows": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
            "source_revision": "rev-over-return",
            "receipt_id": "read-ref",
        }


def test_convert_csv_to_json_writes_union_rows(tmp_path) -> None:
    source = tmp_path / "orders.csv"
    destination = tmp_path / "orders.json"
    source.write_text("id,amount\na,1\n")

    summary = convert_endpoint(
        parse_endpoint(str(source)),
        parse_endpoint(str(destination)),
        build_default_registry(env={}),
        CliOptions(),
    )

    assert summary.status == "completed"
    assert json.loads(destination.read_text()) == [{"id": "a", "amount": "1"}]
    assert summary.rows_read == 1
    assert summary.rows_written == 1


class RecordingAdapter:
    schemes = ("fake",)
    identity = ConnectorIdentity("fake", "1", "1")
    capabilities = (CapabilityIdentity("table.write", "1"),)

    def __init__(self) -> None:
        self.read_calls = 0
        self.write_calls = 0
        self.inspection_calls = 0
        self.tables: list[pa.Table] = []
        self.receipt = object()

    def read(self, endpoint, options):
        self.read_calls += 1
        return type("Read", (), {"table": pa.table({"id": ["a"]}), "receipt": self.receipt})()

    def inspect(self, endpoint, options):
        self.inspection_calls += 1
        return self.receipt

    def write(self, endpoint, table, options):
        self.write_calls += 1
        self.tables.append(table)
        return TableWriteResult(self.receipt, table.num_rows)


class RecordingRegistry(ConnectorRegistry):
    def __init__(self, adapter):
        super().__init__([adapter])
        self.capability_checked = False

    def require_capability(self, endpoint, capability_id):
        self.capability_checked = True
        return super().require_capability(endpoint, capability_id)


def test_import_uses_destination_adapter_and_returns_both_receipts(tmp_path) -> None:
    adapter = RecordingAdapter()
    registry = RecordingRegistry(adapter)

    summary = import_endpoint(
        parse_endpoint("fake://book/Orders"),
        parse_endpoint("fake://book/Orders"),
        registry,
        CliOptions(token="token"),
    )

    assert registry.capability_checked
    assert adapter.read_calls == 1
    assert adapter.write_calls == 1
    assert summary.rows_read == 1
    assert summary.rows_written == 1
    assert summary.source_receipt is adapter.receipt
    assert summary.destination_receipt is adapter.receipt


def test_inspect_delegates_to_adapter_without_cli_read() -> None:
    adapter = RecordingAdapter()
    registry = ConnectorRegistry([adapter])

    result = inspect_endpoint(parse_endpoint("fake://book/Orders"), registry, CliOptions())

    assert result is adapter.receipt
    assert adapter.inspection_calls == 1
    assert adapter.read_calls == 0


def test_read_rejects_connector_format_override_before_adapter_read() -> None:
    adapter = RecordingAdapter()
    with pytest.raises(ConnectorError) as error:
        read_endpoint(
            parse_endpoint("fake://book/Orders"),
            ConnectorRegistry([adapter]),
            CliOptions(from_format=FormatName.CSV),
        )

    assert error.value.code is ConnectorErrorCode.UNSUPPORTED_CAPABILITY
    assert error.value.safe_details == {
        "scheme": "fake",
        "option": "from-format",
        "format": "csv",
    }
    assert adapter.read_calls == 0


def test_import_rejects_connector_destination_format_before_adapter_io() -> None:
    adapter = RecordingAdapter()
    with pytest.raises(ConnectorError) as error:
        import_endpoint(
            parse_endpoint("fake://book/Orders"),
            parse_endpoint("fake://book/Orders"),
            ConnectorRegistry([adapter]),
            CliOptions(to_format=FormatName.JSON),
        )

    assert error.value.code is ConnectorErrorCode.UNSUPPORTED_CAPABILITY
    assert error.value.safe_details == {
        "scheme": "fake",
        "option": "to-format",
        "format": "json",
    }
    assert adapter.read_calls == 0
    assert adapter.write_calls == 0


def test_convert_rejects_connector_destination() -> None:
    with pytest.raises(ConnectorError) as error:
        convert_endpoint(
            parse_endpoint("orders.csv"),
            parse_endpoint("fake://book/Orders"),
            ConnectorRegistry([RecordingAdapter()]),
            CliOptions(),
        )

    assert error.value.code is ConnectorErrorCode.UNSUPPORTED_CAPABILITY


def test_convert_rejects_unknown_local_codec_before_read(tmp_path) -> None:
    adapter = RecordingAdapter()
    destination = tmp_path / "orders"

    with pytest.raises(ConnectorError) as error:
        convert_endpoint(
            parse_endpoint("fake://book/Orders"),
            parse_endpoint(str(destination)),
            ConnectorRegistry([adapter]),
            CliOptions(),
        )

    assert error.value.code is ConnectorErrorCode.UNSUPPORTED_CAPABILITY
    assert "format" in error.value.safe_details
    assert adapter.read_calls == 0


def test_convert_explicit_format_allows_extensionless_local_destination(tmp_path) -> None:
    adapter = RecordingAdapter()
    destination = tmp_path / "orders"

    summary = convert_endpoint(
        parse_endpoint("fake://book/Orders"),
        parse_endpoint(str(destination)),
        ConnectorRegistry([adapter]),
        CliOptions(to_format=FormatName.JSON),
    )

    assert summary.rows_read == 1
    assert adapter.read_calls == 1
    assert json.loads(destination.read_text()) == [{"id": "a"}]


def test_import_rejects_local_destination_before_read(tmp_path) -> None:
    adapter = RecordingAdapter()
    with pytest.raises(ConnectorError) as error:
        import_endpoint(
            parse_endpoint("fake://book/Orders"),
            parse_endpoint(str(tmp_path / "orders.json")),
            ConnectorRegistry([adapter]),
            CliOptions(),
        )

    assert error.value.code is ConnectorErrorCode.UNSUPPORTED_CAPABILITY
    assert adapter.read_calls == 0


def test_csv_to_google_sheets_import_sends_header_and_rows(tmp_path) -> None:
    source = tmp_path / "orders.csv"
    source.write_text("id,amount\na,1\n")
    transport = RecordingTransport({"GET": {"values": [["unused"]]}, "PUT": {"updatedRows": 2}})
    registry = build_default_registry(
        env={"GOOGLE_SHEETS_ACCESS_TOKEN": "token"}, transports={"google_sheets": transport}
    )

    summary = import_endpoint(
        parse_endpoint(str(source)),
        parse_endpoint("gsheets://book/Orders"),
        registry,
        CliOptions(if_exists="replace"),
    )

    assert summary.rows_read == 1
    assert summary.rows_written == 1
    assert summary.source_receipt is not None
    assert summary.destination_receipt is not None
    assert transport.calls[0].method == "PUT"
    assert transport.calls[0].body == {
        "range": "Orders",
        "majorDimension": "ROWS",
        "values": [["id", "amount"], ["a", "1"]],
    }


def test_google_sheets_to_maybe_sheet_import_sends_jsonl_to_process(tmp_path) -> None:
    source = tmp_path / "orders.jsonl"
    source.write_text('{"id":"a"}\n')
    process = RecordingProcess()
    registry = build_default_registry(
        env={"MAYBE_SHEET_ACCESS_TOKEN": "token"}, transports={"maybe_sheet": process}
    )

    summary = import_endpoint(
        parse_endpoint(str(source)),
        parse_endpoint("maybe://doc/R_orders"),
        registry,
        CliOptions(if_exists="append", token="explicit-write-token"),
    )

    assert summary.rows_read == 1
    assert summary.rows_written == 1
    assert summary.source_receipt is not None
    assert summary.destination_receipt is not None
    assert summary.destination_receipt.vendor_receipt_ref == "write-ref"
    assert process.calls[0][1] == {"access_token": "explicit-write-token"}
    assert "explicit-write-token" not in repr(process.calls[0][0])
    assert "explicit-write-token" not in process.stdin_payload
    assert "explicit-write-token" not in repr(summary.destination_receipt.to_wire())
    assert process.calls[0][0] == (
        "mbs", "db-table", "write", "--uri", "maybe://doc/R_orders",
        "--target", "R_orders", "--input", "-",
    )
    assert process.stdin_payload == '{"id":"a"}\n'


def test_feishu_to_jsonl_preserves_record_id(tmp_path) -> None:
    destination = tmp_path / "records.jsonl"
    transport = RecordingTransport({
        "GET": {"code": 0, "data": {"items": [{"record_id": "rec_1", "fields": {"name": "Ada"}}], "has_more": False}}
    })
    registry = build_default_registry(
        env={"FEISHU_TENANT_ACCESS_TOKEN": "token"}, transports={"feishu_bitable": transport}
    )

    summary = convert_endpoint(
        parse_endpoint("feishu://app/table"), parse_endpoint(str(destination)), registry, CliOptions()
    )

    assert summary.rows_read == 1
    assert summary.rows_written == 1
    assert summary.source_receipt is not None
    assert [json.loads(line) for line in destination.read_text().splitlines()] == [
        {"_record_id": "rec_1", "name": "Ada"}
    ]
    assert transport.calls[0].body is None


def test_feishu_to_feishu_import_removes_destination_owned_record_id() -> None:
    transport = RecordingTransport({
        "GET": {
            "code": 0,
            "data": {
                "items": [
                    {
                        "record_id": "rec_source_1",
                        "fields": {"name": "Ada", "score": 10},
                    }
                ],
                "has_more": False,
            },
        },
        "POST": {
            "code": 0,
            "data": {"records": [{"record_id": "rec_destination_1"}]},
        },
    })
    registry = build_default_registry(
        env={"FEISHU_TENANT_ACCESS_TOKEN": "tenant-token"},
        transports={"feishu_bitable": transport},
    )

    summary = import_endpoint(
        parse_endpoint("feishu://source-app/source-table"),
        parse_endpoint("feishu://destination-app/destination-table"),
        registry,
        CliOptions(if_exists="append"),
    )

    assert summary.rows_read == summary.rows_written == 1
    assert [call.method for call in transport.calls] == ["GET", "POST"]
    assert transport.calls[1].url == (
        "https://open.feishu.cn/open-apis/bitable/v1/apps/destination-app/"
        "tables/destination-table/records/batch_create"
    )
    assert transport.calls[1].headers == {
        "Authorization": "Bearer tenant-token"
    }
    assert transport.calls[1].body == {
        "records": [{"fields": {"name": "Ada", "score": 10}}]
    }


def test_row_limit_is_applied_before_destination_write(tmp_path) -> None:
    transport = RecordingTransport({
        "GET": {"code": 0, "data": {"items": [
            {"record_id": "rec_1", "fields": {"id": "a"}},
            {"record_id": "rec_2", "fields": {"id": "b"}},
        ], "has_more": False}},
        "PUT": {"updatedRows": 1},
    })
    registry = build_default_registry(
        env={"FEISHU_TENANT_ACCESS_TOKEN": "token", "GOOGLE_SHEETS_ACCESS_TOKEN": "token"},
        transports={"feishu_bitable": transport, "google_sheets": transport},
    )

    summary = import_endpoint(
        parse_endpoint("feishu://app/table"), parse_endpoint("gsheets://book/Orders"), registry,
        CliOptions(limit=1, if_exists="replace"),
    )

    assert summary.rows_read == 1
    assert summary.rows_written == 1
    assert transport.calls[0].method == "GET"
    assert transport.calls[1].body == {
        "range": "Orders", "majorDimension": "ROWS",
        "values": [["_record_id", "id"], ["rec_1", "a"]],
    }


def test_maybe_sheet_unsupported_policy_is_rejected_before_source_read() -> None:
    source_adapter = RecordingAdapter()
    process = RecordingProcess()
    registry = build_default_registry(transports={"maybe_sheet": process})
    registry.register(source_adapter)

    with pytest.raises(ConnectorError) as error:
        import_endpoint(
            parse_endpoint("fake://book/Orders"), parse_endpoint("maybe://doc/R_orders"), registry,
            CliOptions(if_exists="error"),
        )

    assert error.value.code is ConnectorErrorCode.UNSUPPORTED_CAPABILITY
    assert error.value.safe_details == {"if_exists": "error"}
    assert source_adapter.read_calls == 0
    assert process.calls == []


def test_feishu_replace_is_rejected_before_source_read_or_destination_write() -> None:
    source_adapter = RecordingAdapter()
    transport = RecordingTransport({"GET": {"code": 0, "data": {"items": []}}, "POST": {}})
    registry = build_default_registry(
        env={"FEISHU_TENANT_ACCESS_TOKEN": "token"}, transports={"feishu_bitable": transport}
    )
    registry.register(source_adapter)

    with pytest.raises(ConnectorError) as error:
        import_endpoint(
            parse_endpoint("fake://book/Orders"), parse_endpoint("feishu://app/table"), registry,
            CliOptions(if_exists="replace"),
        )

    assert error.value.code is ConnectorErrorCode.UNSUPPORTED_CAPABILITY
    assert error.value.safe_details == {"if_exists": "replace"}
    assert source_adapter.read_calls == 0
    assert transport.calls == []


def test_feishu_error_policy_conflicts_before_source_read_when_destination_has_rows() -> None:
    source_adapter = RecordingAdapter()
    transport = RecordingTransport({
        "GET": {"code": 0, "data": {"items": [{"record_id": "r1", "fields": {"id": "1"}}]}},
        "POST": {},
    })
    registry = build_default_registry(
        env={"FEISHU_TENANT_ACCESS_TOKEN": "token"}, transports={"feishu_bitable": transport}
    )
    registry.register(source_adapter)

    with pytest.raises(ConnectorError) as error:
        import_endpoint(
            parse_endpoint("fake://book/Orders"), parse_endpoint("feishu://app/table"), registry,
            CliOptions(if_exists="error"),
        )

    assert error.value.code is ConnectorErrorCode.CONFLICT
    assert source_adapter.read_calls == 0
    assert [call.method for call in transport.calls] == ["GET"]


def test_feishu_empty_destination_allows_error_policy_write() -> None:
    source_adapter = RecordingAdapter()
    transport = RecordingTransport({
        "GET": {"code": 0, "data": {"items": [], "has_more": False}},
        "POST": {"data": {}},
    })
    registry = build_default_registry(
        env={"FEISHU_TENANT_ACCESS_TOKEN": "token"}, transports={"feishu_bitable": transport}
    )
    registry.register(source_adapter)

    summary = import_endpoint(
        parse_endpoint("fake://book/Orders"), parse_endpoint("feishu://app/table"), registry,
        CliOptions(if_exists="error"),
    )

    assert summary.rows_read == 1
    assert source_adapter.read_calls == 1
    assert [call.method for call in transport.calls] == ["GET", "POST"]


def test_google_error_policy_conflicts_before_source_read_when_destination_has_rows() -> None:
    source_adapter = RecordingAdapter()
    transport = RecordingTransport({
        "GET": {"values": [["id"], ["existing"]]},
        "PUT": {},
    })
    registry = build_default_registry(
        env={"GOOGLE_SHEETS_ACCESS_TOKEN": "token"}, transports={"google_sheets": transport}
    )
    registry.register(source_adapter)

    with pytest.raises(ConnectorError) as error:
        import_endpoint(
            parse_endpoint("fake://book/Orders"), parse_endpoint("gsheets://book/Orders"), registry,
            CliOptions(if_exists="error"),
        )

    assert error.value.code is ConnectorErrorCode.CONFLICT
    assert source_adapter.read_calls == 0
    assert [call.method for call in transport.calls] == ["GET"]


def test_google_empty_destination_allows_error_policy_write() -> None:
    source_adapter = RecordingAdapter()
    transport = RecordingTransport({"GET": {"values": []}, "PUT": {"updatedRows": 1}})
    registry = build_default_registry(
        env={"GOOGLE_SHEETS_ACCESS_TOKEN": "token"}, transports={"google_sheets": transport}
    )
    registry.register(source_adapter)

    summary = import_endpoint(
        parse_endpoint("fake://book/Orders"), parse_endpoint("gsheets://book/Orders"), registry,
        CliOptions(if_exists="error"),
    )

    assert summary.rows_read == 1
    assert source_adapter.read_calls == 1
    assert [call.method for call in transport.calls] == ["GET", "PUT"]


def test_google_invalid_policy_is_rejected_before_source_read_or_destination_write() -> None:
    source_adapter = RecordingAdapter()
    transport = RecordingTransport({"GET": {}, "PUT": {}})
    registry = build_default_registry(
        env={"GOOGLE_SHEETS_ACCESS_TOKEN": "token"}, transports={"google_sheets": transport}
    )
    registry.register(source_adapter)

    with pytest.raises(ConnectorError) as error:
        import_endpoint(
            parse_endpoint("fake://book/Orders"), parse_endpoint("gsheets://book/Orders"), registry,
            CliOptions(if_exists="merge"),
        )

    assert error.value.code is ConnectorErrorCode.INVALID_URI
    assert source_adapter.read_calls == 0
    assert transport.calls == []


def test_local_source_limit_is_reflected_in_import_summary_and_destination_table(tmp_path) -> None:
    source = tmp_path / "orders.json"
    source.write_text('[{"id": 1}, {"id": 2}, {"id": 3}]')
    destination_adapter = RecordingAdapter()
    registry = build_default_registry(env={})
    registry.register(destination_adapter)

    summary = import_endpoint(
        parse_endpoint(str(source)), parse_endpoint("fake://book/Orders"), registry,
        CliOptions(from_format="json", limit=2, if_exists="append"),
    )

    assert summary.rows_read == 2
    assert summary.rows_written == 2
    assert destination_adapter.tables[0].num_rows == 2


def test_google_source_limit_is_reflected_in_import_summary_and_destination_table() -> None:
    transport = RecordingTransport({
        "GET": {"values": [["id"], ["a"], ["b"], ["c"]]},
    })
    destination_adapter = RecordingAdapter()
    registry = build_default_registry(
        env={"GOOGLE_SHEETS_ACCESS_TOKEN": "token"}, transports={"google_sheets": transport}
    )
    registry.register(destination_adapter)

    summary = import_endpoint(
        parse_endpoint("gsheets://book/Orders"), parse_endpoint("fake://book/Orders"), registry,
        CliOptions(limit=2, if_exists="append"),
    )

    assert summary.rows_read == 2
    assert summary.rows_written == 2
    assert destination_adapter.tables[0].num_rows == 2


def test_maybe_sheet_source_limit_is_enforced_when_process_over_returns_during_import() -> None:
    process = OverReturningProcess()
    destination_adapter = RecordingAdapter()
    registry = build_default_registry(transports={"maybe_sheet": process})
    registry.register(destination_adapter)

    summary = import_endpoint(
        parse_endpoint("maybe://doc/R_orders"),
        parse_endpoint("fake://book/Orders"),
        registry,
        CliOptions(limit=2, if_exists="append"),
    )

    written_table = destination_adapter.tables[0]
    assert written_table.to_pylist() == [{"id": "a"}, {"id": "b"}]
    assert process.calls[0][0][-2:] == ("--limit", "2")
    assert summary.rows_read == 2
    assert summary.rows_written == 2
    assert summary.source_receipt.row_count == 2
    assert summary.source_receipt.content_fingerprint == arrow_content_fingerprint(written_table)


def test_maybe_sheet_https_missing_target_is_rejected_before_source_or_process_io() -> None:
    source_adapter = RecordingAdapter()
    process = RecordingProcess()
    registry = build_default_registry(transports={"maybe_sheet": process})
    registry.register(source_adapter)

    with pytest.raises(ConnectorError) as error:
        import_endpoint(
            parse_endpoint("fake://book/Orders"),
            parse_endpoint("https://www.maybe.ai/docs/spreadsheets/d/doc"),
            registry,
            CliOptions(if_exists="append"),
        )

    assert error.value.code is ConnectorErrorCode.INVALID_URI
    assert error.value.safe_details == {"option": "target"}
    assert source_adapter.read_calls == 0
    assert process.calls == []
