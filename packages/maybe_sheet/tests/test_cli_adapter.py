from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pyarrow as pa
import pytest
from open_table_connector.contract import (
    CREDENTIAL_ACCESS_TOKEN,
    HOST_MAYBE,
    OPTION_TIMEOUT_SECONDS,
    PROVIDER_MAYBE_SHEET,
    SCHEME_HTTPS,
    SETTING_BINARY,
    AdapterOptions,
    ConnectorError,
    ConnectorErrorCode,
    ProviderConfig,
    ProviderFactoryContext,
    parse_adapter_endpoint,
)
from open_table_connector.maybe_sheet import MaybeSheetCliAdapter, maybe_sheet_cli_plugin
from open_table_connector.maybe_sheet.connector import MaybeSheetConnector


class RecordingProcess:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], dict[str, object]]] = []

    def run(self, argv, *, credentials=None, stdin=None, timeout=None):
        self.calls.append(
            (tuple(argv), {"credentials": credentials, "stdin": stdin, "timeout": timeout})
        )
        return {"rows": [{"name": "Ada"}], "source_revision": "v1"}


def test_maybe_plugin_factory_scopes_binary_credentials_and_timeout() -> None:
    process = RecordingProcess()
    descriptor = maybe_sheet_cli_plugin()
    adapter = descriptor.factory(
        ProviderFactoryContext(
            ProviderConfig(
                PROVIDER_MAYBE_SHEET,
                environment={SETTING_BINARY: "/opt/mbs"},
                options={OPTION_TIMEOUT_SECONDS: 9},
            ),
            environment={SETTING_BINARY: "/opt/mbs"},
            credentials={CREDENTIAL_ACCESS_TOKEN: "access-secret"},
            transports={PROVIDER_MAYBE_SHEET: process},
        )
    )

    assert isinstance(adapter, MaybeSheetCliAdapter)
    result = adapter.read(
        parse_adapter_endpoint("https://www.maybe.ai/docs/spreadsheets/d/doc"),
        AdapterOptions(target="table"),
    )
    assert result.table.column_names == ["name"]
    assert process.calls[0][0][:2] == ("mbs", "db-table")
    assert process.calls[0][1]["credentials"] == {CREDENTIAL_ACCESS_TOKEN: "access-secret"}
    assert process.calls[0][1]["timeout"] == 9


def test_maybe_plugin_descriptor_declares_https_document_route_only() -> None:
    descriptor = maybe_sheet_cli_plugin()
    assert descriptor.name == PROVIDER_MAYBE_SHEET
    assert descriptor.schemes == (SCHEME_HTTPS,)
    assert descriptor.hosts == (HOST_MAYBE,)


def test_maybe_adapter_rejects_non_https_uri_scheme() -> None:
    process = RecordingProcess()
    adapter = MaybeSheetCliAdapter(MaybeSheetConnector(process), {}, 13)

    with pytest.raises(ConnectorError) as error:
        adapter.read(parse_adapter_endpoint("gsheets://doc/table"), AdapterOptions())

    assert error.value.code is ConnectorErrorCode.UNSUPPORTED_CAPABILITY
    assert process.calls == []


def test_maybe_read_uses_table_id_for_stable_table_identifier() -> None:
    process = RecordingProcess()
    adapter = MaybeSheetCliAdapter.from_context(
        ProviderFactoryContext(
            ProviderConfig(PROVIDER_MAYBE_SHEET),
            credentials={},
            transports={PROVIDER_MAYBE_SHEET: process},
        )
    )
    adapter.read(parse_adapter_endpoint("https://www.maybe.ai/docs/spreadsheets/d/doc?table_id=tbl_orders"), AdapterOptions())
    argv = process.calls[0][0]
    assert argv == (
        "mbs",
        "db-table",
        "read",
        "--uri",
        "https://www.maybe.ai/docs/spreadsheets/d/doc",
        "--table-id",
        "tbl_orders",
    )


def test_maybe_write_uses_table_insert_and_scoped_credentials() -> None:
    process = RecordingProcess()
    adapter = MaybeSheetCliAdapter.from_context(
        ProviderFactoryContext(
            ProviderConfig(PROVIDER_MAYBE_SHEET),
            credentials={CREDENTIAL_ACCESS_TOKEN: "access-secret"},
            transports={PROVIDER_MAYBE_SHEET: process},
        )
    )
    adapter.write(
        parse_adapter_endpoint("https://www.maybe.ai/docs/spreadsheets/d/doc"),
        pa.table({"name": ["Ada"]}),
        AdapterOptions(if_exists="append", target="table"),
    )
    argv = process.calls[0][0]
    assert argv[:7] == (
        "mbs",
        "table",
        "insert",
        "--target",
        "https://www.maybe.ai/docs/spreadsheets/d/doc",
        "--table-name",
        "table",
    )
    assert argv[7] == "--frame-in"
    assert Path(argv[8]).suffix == ".json"
    assert not Path(argv[8]).exists()
    assert argv[9:] == ("--output", "json")
    assert process.calls[0][1]["credentials"] == {CREDENTIAL_ACCESS_TOKEN: "access-secret"}
    assert process.calls[0][1]["stdin"] is None


class FixtureProcess:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def run(self, argv, *, credentials=None, stdin=None, timeout=None):
        return self.payload


def _many_field_typed_payload() -> dict[str, object]:
    """Load the captured 36-field payload, holding temporal cells as datetimes.

    The fixture stores temporal cells as ISO text so it stays diffable; the live
    deployment provider hands over ``datetime`` objects for those fields, so the
    helper restores that shape before the payload reaches the connector.
    """
    fixture = Path(__file__).parent / "fixtures" / "typed-read-many-field-datetime.json"
    payload = json.loads(fixture.read_text())
    result = payload["result"]
    fields = result["schema"]["fields"]
    temporal = {"Datetime": datetime.fromisoformat, "Date": date.fromisoformat}
    indexes = [
        (index, temporal[field["type"]])
        for index, field in enumerate(fields)
        if field["type"] in temporal
    ]
    for row in result["rows"]:
        for index, parse in indexes:
            if isinstance(row[index], str):
                row[index] = parse(row[index])
    return payload


def test_typed_read_payload_with_bare_datetime_inspects_every_field() -> None:
    """A many-field typed payload must not collapse to a silent empty table.

    Regression: a payload whose schema declares the bare wire dtype "Datetime"
    used to raise inside the decoder, get swallowed, and surface as a
    successful zero-column/zero-row read (schema_fingerprint of an empty schema).
    """
    adapter = MaybeSheetCliAdapter(MaybeSheetConnector(FixtureProcess(_many_field_typed_payload())), {})
    endpoint = parse_adapter_endpoint("https://www.maybe.ai/docs/spreadsheets/d/doc")

    inspection = adapter.inspect(endpoint, AdapterOptions(target="tbl_orders"))
    assert len(inspection.columns) == 36
    assert inspection.row_count == 3

    read = adapter.read(endpoint, AdapterOptions(target="tbl_orders"))
    assert len(read.table.column_names) == 36
    assert read.receipt.row_count == 3
    assert read.table.schema.field("order_created_at").type == pa.timestamp("us")


def test_unreadable_typed_payload_fails_closed_instead_of_returning_empty() -> None:
    payload = _many_field_typed_payload()
    fields = payload["result"]["schema"]["fields"]  # type: ignore[index]
    fields[0]["type"] = "NotARealDtype"

    adapter = MaybeSheetCliAdapter(MaybeSheetConnector(FixtureProcess(payload)), {})
    endpoint = parse_adapter_endpoint("https://www.maybe.ai/docs/spreadsheets/d/doc")

    with pytest.raises(ConnectorError) as error:
        adapter.read(endpoint, AdapterOptions(target="tbl_orders"))
    assert error.value.code is ConnectorErrorCode.PROTOCOL_INVALID
    assert error.value.safe_details["field_count"] == 36
    assert error.value.safe_details["row_count"] == 3


class FailingProcess:
    def __init__(self, error: BaseException) -> None:
        self.error = error

    def run(self, argv, *, credentials=None, stdin=None, timeout=None):
        raise self.error


def test_unexpected_process_failure_keeps_its_cause() -> None:
    """A non-ConnectorError failure must not collapse to an opaque message.

    Regression: every distinct provider/transport fault, including the
    deployment shim's own ValueError, surfaced as the identical
    "MaybeSheet process operation failed" text with no way to tell them apart.
    """
    cause = ValueError("Maybe complete read primary field is not unique")
    adapter = MaybeSheetCliAdapter(MaybeSheetConnector(FailingProcess(cause)), {})
    endpoint = parse_adapter_endpoint("https://www.maybe.ai/docs/spreadsheets/d/doc")

    with pytest.raises(ConnectorError) as error:
        adapter.read(endpoint, AdapterOptions(target="tbl_orders"))

    assert error.value.code is ConnectorErrorCode.EXECUTION_FAILED
    assert error.value.safe_details["exception"] == "ValueError"
    assert "primary field is not unique" in error.value.safe_details["message"]


def test_provider_limit_rejection_is_classified_as_resource_limit() -> None:
    process_error = ConnectorError(
        ConnectorErrorCode.EXECUTION_FAILED,
        "MaybeSheet process failed",
        {"returncode": 2, "stderr": "--limit must be 10000 or less."},
    )
    adapter = MaybeSheetCliAdapter(MaybeSheetConnector(FailingProcess(process_error)), {})
    endpoint = parse_adapter_endpoint("https://www.maybe.ai/docs/spreadsheets/d/doc")

    with pytest.raises(ConnectorError) as error:
        adapter.read(endpoint, AdapterOptions(target="tbl_orders", limit=50000))

    assert error.value.code is ConnectorErrorCode.RESOURCE_LIMIT_EXCEEDED
    assert error.value.safe_details["limit"] == 50000
    assert error.value.safe_details["maximum"] == 10000


def test_limit_within_the_provider_ceiling_is_not_reclassified() -> None:
    process_error = ConnectorError(
        ConnectorErrorCode.EXECUTION_FAILED,
        "MaybeSheet process failed",
        {"returncode": 2, "stderr": "--limit must be 10000 or less."},
    )
    adapter = MaybeSheetCliAdapter(MaybeSheetConnector(FailingProcess(process_error)), {})
    endpoint = parse_adapter_endpoint("https://www.maybe.ai/docs/spreadsheets/d/doc")

    with pytest.raises(ConnectorError) as error:
        adapter.read(endpoint, AdapterOptions(target="tbl_orders", limit=1000))

    assert error.value.code is ConnectorErrorCode.EXECUTION_FAILED
