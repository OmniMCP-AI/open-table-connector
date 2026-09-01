from __future__ import annotations

import open_table_connector.sdk as otc
import polars as pl
import pytest
from open_table_connector.feishu_bitable import feishu_bitable_cli_plugin
from open_table_connector.google_sheets import google_sheets_cli_plugin
from open_table_connector.maybe_sheet import maybe_sheet_cli_plugin

from .conftest import legacy_descriptor, sdk_descriptor


class GoogleTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, str], dict | None]] = []

    def request(self, method, url, *, headers, body=None, timeout=None):
        del timeout
        self.calls.append((method, url, dict(headers), body))
        return {"range": "Orders!A1:A2", "values": [["order_id"], ["1"]]}


class FeishuTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, str], dict | None]] = []

    def request(self, method, url, *, headers, body=None, timeout=None):
        del timeout
        self.calls.append((method, url, dict(headers), body))
        return {
            "code": 0,
            "data": {
                "items": [{"record_id": "rec-1", "fields": {"order_id": "1"}}],
                "has_more": False,
            },
        }


class MaybeProcess:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], dict[str, str] | None, str | None]] = []

    def run(self, argv, *, credentials=None, stdin=None, timeout=None):
        del timeout
        self.calls.append((tuple(argv), dict(credentials or {}), stdin))
        return {"rows": [{"order_id": "1"}], "source_revision": "rev-1"}


def test_client_from_config_opens_through_a_descriptor_registry(fake_connector) -> None:
    config = otc.ClientConfig.empty()
    calls: list[str] = []
    client = otc.Client.from_config(
        config,
        descriptors=(sdk_descriptor(calls, fake_connector),),
        resolver=otc.EnvironmentCredentialResolver(config, {}),
    )

    table = client.open("fake://warehouse/orders").require_value()

    assert calls == ["factory"]
    assert table.mode is otc.TableMode.BASE_MODE
    assert table.schema == fake_connector.frame.schema


def test_client_open_can_attach_a_declared_schema_to_an_existing_table(fake_connector) -> None:
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    declared = pl.Schema({"order_id": pl.Int64, "status": pl.String})

    table = client.open("fake://warehouse/orders", schema=declared).require_value()

    assert table.schema == declared


def test_client_open_routes_path_targets_without_forcing_table_uri(fake_connector) -> None:
    fake_connector.schemes = ("file",)
    fake_connector.local = True
    fake_connector.handles_paths = True
    fake_connector.table_uri = "file:///tmp/orders.csv"
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))

    table = client.open("orders.csv").require_value()

    assert fake_connector.calls[0] == ("open_table", "orders.csv")
    assert table.uri.value == "file:///tmp/orders.csv"


def test_client_rejects_foreign_physical_handles_before_connector_io(fake_connector) -> None:
    left = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    right = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    table = left.open("fake://warehouse/orders").require_value()
    destination = otc.DirectDestination("fake://warehouse/other")

    with pytest.raises(otc.OTCError) as raised:
        right.materialize(table, to=destination)

    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.INVALID_TARGET
    assert fake_connector.calls.count(("create_table", "fake://warehouse/other")) == 0


def test_client_close_is_idempotent_and_closes_bound_tables(fake_connector) -> None:
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    table = client.open("fake://warehouse/orders").require_value()

    client.close()
    client.close()

    with pytest.raises(otc.OTCError) as raised:
        table.read()

    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.CLIENT_CLOSED


def test_client_materialize_is_create_only_and_preserves_conflicts(fake_connector) -> None:
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))

    created = client.materialize(
        pl.DataFrame({"order_id": [3], "status": ["queued"]}),
        to=otc.DirectDestination("fake://warehouse/created"),
    ).require_value()
    assert created.uri.value == "fake://warehouse/created"

    with pytest.raises(otc.OTCError) as raised:
        client.materialize(
            pl.DataFrame({"order_id": [4], "status": ["queued"]}),
            to=otc.DirectDestination("fake://warehouse/existing"),
        )

    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.DESTINATION_EXISTS


def test_client_materialize_collects_table_sources_and_orders_receipts(fake_connector) -> None:
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    source = client.open("fake://warehouse/orders").require_value()

    result = client.materialize(
        source,
        to=otc.DirectDestination("fake://warehouse/materialized"),
    )

    assert result.require_value().uri.value == "fake://warehouse/materialized"
    assert [receipt.operation for receipt in result.receipts[-2:]] == [
        "table.read",
        "table.create",
    ]
    assert all(
        call[0] != "create_table" or call[1] == "fake://warehouse/materialized"
        for call in fake_connector.calls
    )


def test_client_binds_and_collects_sheet_ranges_with_client_affinity(fake_connector) -> None:
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    bound = client.bind_sheet_range(
        grid="fake://warehouse/orders",
        cell_range="A1:B2",
        header=True,
        schema=fake_connector.frame.schema,
    ).require_value()

    assert bound.observed_revision == "range-rev-1"
    assert client.collect(bound).require_value().height == fake_connector.frame.height

    other = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    with pytest.raises(otc.OTCError) as raised:
        other.collect(bound)
    assert raised.value.result.error.code is otc.ErrorCode.CLIENT_AFFINITY_MISMATCH


def test_client_materialize_works_through_a_legacy_write_adapter() -> None:
    config = otc.ClientConfig.empty()
    client = otc.Client.from_config(
        config,
        descriptors=(legacy_descriptor(),),
        resolver=otc.EnvironmentCredentialResolver(config, {}),
    )

    table = client.materialize(
        pl.DataFrame({"order_id": [1]}),
        to=otc.DirectDestination("legacy://warehouse/created"),
    ).require_value()

    assert table.uri.value == "legacy://warehouse/created"


def test_client_open_reads_schema_through_a_legacy_adapter() -> None:
    config = otc.ClientConfig.empty()
    client = otc.Client.from_config(
        config,
        descriptors=(legacy_descriptor(),),
        resolver=otc.EnvironmentCredentialResolver(config, {}),
    )

    table = client.open("legacy://warehouse/orders").require_value()

    assert table.uri.value == "legacy://warehouse/orders"
    assert table.schema == pl.DataFrame({"order_id": [1]}).schema


def test_client_from_config_defaults_google_credentials_from_environment() -> None:
    transport = GoogleTransport()

    client = otc.Client.from_config(
        otc.ClientConfig.empty(),
        descriptors=(google_sheets_cli_plugin(),),
        environ={"GOOGLE_SHEETS_ACCESS_TOKEN": "google-secret"},
        transports={"google_sheets": transport},
    )

    table = client.open("gsheets://sheet-123/Orders").require_value()

    assert table.uri.value == "gsheets://sheet-123/Orders"
    assert transport.calls[0][2]["Authorization"] == "Bearer google-secret"


def test_client_from_config_defaults_feishu_credentials_from_environment() -> None:
    transport = FeishuTransport()

    client = otc.Client.from_config(
        otc.ClientConfig.empty(),
        descriptors=(feishu_bitable_cli_plugin(),),
        environ={"FEISHU_TENANT_ACCESS_TOKEN": "feishu-secret"},
        transports={"feishu_bitable": transport},
    )

    table = client.open("feishu://app-token/orders").require_value()

    assert table.uri.value == "feishu://app-token/orders"
    assert transport.calls[0][2]["Authorization"] == "Bearer feishu-secret"


def test_client_from_config_defaults_maybe_credentials_from_environment() -> None:
    process = MaybeProcess()

    client = otc.Client.from_config(
        otc.ClientConfig.empty(),
        descriptors=(maybe_sheet_cli_plugin(),),
        environ={"MAYBE_SHEET_ACCESS_TOKEN": "maybe-secret"},
        transports={"maybe_sheet": process},
    )

    table = client.open("maybe://doc/R_orders").require_value()

    assert table.uri.value == "maybe://doc/R_orders"
    assert process.calls[0][1] == {"access_token": "maybe-secret"}
