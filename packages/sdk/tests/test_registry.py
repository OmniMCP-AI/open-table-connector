from __future__ import annotations

import open_table_connector.sdk as otc

from .conftest import sdk_descriptor


def test_registry_registers_explicit_connectors_without_activation(fake_connector) -> None:
    registry = otc.ConnectorRegistry()
    registry.register(fake_connector)

    descriptor = registry.descriptor_for("fake://warehouse/orders")

    assert descriptor.identity.connector_id == "fake"
    assert fake_connector.calls == []


def test_descriptor_registry_is_lazy_until_the_client_uses_it(fake_connector) -> None:
    calls: list[str] = []
    registry = otc.ConnectorRegistry.from_descriptors(
        (sdk_descriptor(calls, fake_connector),),
        otc.ClientConfig.empty(),
        resolver=otc.EnvironmentCredentialResolver(otc.ClientConfig.empty(), {}),
    )
    client = otc.Client(registry=registry)

    assert calls == []
    table = client.open("fake://warehouse/orders").require_value()

    assert calls == ["factory"]
    assert table.uri.value == "fake://warehouse/orders"
