from __future__ import annotations

import pytest
from open_table_connector.cli.configuration import CliConfig
from open_table_connector.cli.configured_registry import (
    ConfiguredConnectorRegistry,
    discover_configured_plugins,
)
from open_table_connector.cli.credentials import CredentialLease
from open_table_connector.contract import (
    CAPABILITY_TABLE_READ_ARROW,
    CapabilityIdentity,
    ConnectorAdapter,
    ConnectorIdentity,
    PluginDescriptor,
    ProviderConfig,
    ProviderFactoryContext,
    TableMode,
    parse_adapter_endpoint,
)

FIXTURE_PROVIDER_ID = "fixture"
FIXTURE_SCHEME = "fixture"
FIXTURE_CREDENTIAL_REFERENCE = "fixture-key"


class FakeAdapter:
    identity = ConnectorIdentity(FIXTURE_PROVIDER_ID, "0.1.0", "1.0")
    schemes = (FIXTURE_SCHEME,)
    hosts: tuple[str, ...] = ()
    capabilities = (CapabilityIdentity(CAPABILITY_TABLE_READ_ARROW, "1.0"),)
    modes = (TableMode.BASE,)

    def read(self, *_):
        raise AssertionError("operation is not part of this registry test")

    def inspect(self, *_):
        raise AssertionError("operation is not part of this registry test")

    def write(self, *_):
        raise AssertionError("operation is not part of this registry test")


class RecordingLease(CredentialLease):
    def __init__(self, calls: list[str]) -> None:
        super().__init__({})
        self._calls = calls

    def dispose(self) -> None:
        super().dispose()
        self._calls.append("dispose")


class RecordingResolver:
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    def resolve(self, provider: ProviderConfig) -> CredentialLease:
        assert provider.provider_id == FIXTURE_PROVIDER_ID
        self._calls.append("resolve")
        return RecordingLease(self._calls)


def fixture_descriptor(factory) -> PluginDescriptor:
    return PluginDescriptor(
        FIXTURE_PROVIDER_ID,
        FakeAdapter.identity,
        (FIXTURE_SCHEME,),
        factory,
        capabilities=FakeAdapter.capabilities,
        modes=FakeAdapter.modes,
    )


def fixture_config() -> CliConfig:
    return CliConfig(
        providers={
            FIXTURE_PROVIDER_ID: ProviderConfig(
                FIXTURE_PROVIDER_ID,
                credential_reference=FIXTURE_CREDENTIAL_REFERENCE,
            )
        },
        credentials={FIXTURE_CREDENTIAL_REFERENCE: {}},
    )


def recording_factory(calls: list[str]):
    def factory(context: ProviderFactoryContext) -> ConnectorAdapter:
        assert context.config.provider_id == FIXTURE_PROVIDER_ID
        calls.append("factory")
        return FakeAdapter()

    return factory


def test_list_does_not_call_factory_or_resolver() -> None:
    calls: list[str] = []
    descriptor = fixture_descriptor(
        factory=lambda context: calls.append("factory") or FakeAdapter()
    )
    registry = ConfiguredConnectorRegistry.from_descriptors(
        (descriptor,), CliConfig.empty(), resolver=RecordingResolver(calls)
    )

    assert registry.list() == (descriptor,)
    assert calls == []


def test_open_adapter_scopes_credentials_around_factory_and_operation() -> None:
    calls: list[str] = []
    descriptor = fixture_descriptor(factory=recording_factory(calls))
    registry = ConfiguredConnectorRegistry.from_descriptors(
        (descriptor,), fixture_config(), resolver=RecordingResolver(calls)
    )

    with registry.open_adapter(parse_adapter_endpoint("fixture://table")) as adapter:
        calls.append(adapter.identity.connector_id)

    assert calls == ["resolve", "factory", "fixture", "dispose"]


def test_disabled_descriptor_is_not_routable() -> None:
    descriptor = fixture_descriptor(factory=lambda context: FakeAdapter())
    config = CliConfig(
        providers={FIXTURE_PROVIDER_ID: ProviderConfig(FIXTURE_PROVIDER_ID, enabled=False)}
    )
    registry = ConfiguredConnectorRegistry.from_descriptors(
        (descriptor,), config, resolver=RecordingResolver([])
    )

    assert registry.list() == ()
    with pytest.raises(Exception, match="no connector"):
        registry.descriptor_for(parse_adapter_endpoint("fixture://table"))


def test_path_handler_is_unique_and_descriptor_only() -> None:
    first = PluginDescriptor(
        "first",
        ConnectorIdentity("first", "0.1.0", "1.0"),
        ("file",),
        lambda context: FakeAdapter(),
        local=True,
        handles_paths=True,
    )
    second = PluginDescriptor(
        "second",
        ConnectorIdentity("second", "0.1.0", "1.0"),
        ("json",),
        lambda context: FakeAdapter(),
        local=True,
        handles_paths=True,
    )

    with pytest.raises(Exception, match="path"):
        ConfiguredConnectorRegistry.from_descriptors(
            (first, second), CliConfig.empty(), resolver=RecordingResolver([])
        )


def test_capability_rejection_happens_before_factory() -> None:
    calls: list[str] = []
    descriptor = fixture_descriptor(factory=recording_factory(calls))
    registry = ConfiguredConnectorRegistry.from_descriptors(
        (descriptor,), CliConfig.empty(), resolver=RecordingResolver(calls)
    )

    with pytest.raises(Exception, match="capability"):
        registry.require_capability(
            parse_adapter_endpoint("fixture://table"), "table.write"
        )
    assert calls == []


def test_discovery_loads_only_zero_io_descriptors_in_deterministic_order() -> None:
    class FakeEntryPoint:
        def __init__(self, name: str, descriptor: PluginDescriptor) -> None:
            self.name = name
            self.value = f"fixture:{name}"
            self._descriptor = descriptor

        def load(self):
            return lambda: self._descriptor

    first = fixture_descriptor(lambda context: FakeAdapter())
    second = PluginDescriptor(
        "other",
        ConnectorIdentity("other", "0.1.0", "1.0"),
        ("other",),
        lambda context: FakeAdapter(),
        capabilities=FakeAdapter.capabilities,
        modes=FakeAdapter.modes,
    )
    configured = discover_configured_plugins(
        CliConfig.empty(),
        entries=(FakeEntryPoint("z", first), FakeEntryPoint("a", second)),
    )

    assert tuple(item.descriptor.name for item in configured) == ("fixture", "other")


def test_duplicate_provider_identity_is_rejected_before_activation() -> None:
    first = fixture_descriptor(lambda context: FakeAdapter())
    duplicate = PluginDescriptor(
        FIXTURE_PROVIDER_ID,
        FakeAdapter.identity,
        ("other",),
        lambda context: FakeAdapter(),
        capabilities=FakeAdapter.capabilities,
        modes=FakeAdapter.modes,
    )

    with pytest.raises(Exception, match="descriptor"):
        ConfiguredConnectorRegistry.from_descriptors(
            (first, duplicate), CliConfig.empty(), resolver=RecordingResolver([])
        )
