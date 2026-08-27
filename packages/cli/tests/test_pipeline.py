import json

import pyarrow as pa
import pytest

from open_connectors.cli.model import CliOptions, FormatName, parse_endpoint
from open_connectors.cli.pipeline import convert_endpoint, import_endpoint, inspect_endpoint
from open_connectors.cli.registry import ConnectorRegistry, build_default_registry
from open_connectors.contract import (
    CapabilityIdentity,
    ConnectorError,
    ConnectorErrorCode,
    ConnectorIdentity,
    NeutralReceipt,
    TableMode,
    TableURI,
    TableWriteResult,
)


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
