from __future__ import annotations

import open_table_connector.sdk as otc
import polars as pl
import pytest

from .conftest import legacy_descriptor, sdk_descriptor


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
