from __future__ import annotations

import open_table_connector.sdk as otc
import polars as pl
from open_table_connector.contract import (
    ConnectorIdentity,
    PluginDescriptor,
    ProviderConfig,
)
from open_table_connector.contract import TableMode as LegacyTableMode

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


def test_descriptor_activation_disposes_credential_lease_after_factory_use() -> None:
    class TrackingLease(otc.CredentialLease):
        def __init__(self, values: dict[str, str], events: list[str]) -> None:
            super().__init__(values)
            self._events = events
            self.disposed = False

        def dispose(self) -> None:
            if not self.disposed:
                self._events.append("dispose")
            self.disposed = True
            super().dispose()

    class TrackingResolver:
        def __init__(self, events: list[str]) -> None:
            self.events = events
            self.last_lease: TrackingLease | None = None

        def resolve(self, provider: ProviderConfig) -> TrackingLease:
            self.events.append(f"resolve:{provider.provider_id}")
            self.last_lease = TrackingLease({"token": "secret"}, self.events)
            return self.last_lease

    events: list[str] = []
    resolver = TrackingResolver(events)
    observed: dict[str, object] = {}

    def factory(context):
        assert resolver.last_lease is not None
        observed["credentials"] = dict(context.credentials)
        observed["environment"] = dict(context.environment)
        observed["options"] = dict(context.config.options)
        observed["lease_disposed_during_factory"] = resolver.last_lease.disposed
        return type(
            "LeaseConnector",
            (),
            {
                "identity": ConnectorIdentity("leasey", "0.1.0", "1.0"),
                "schemes": ("leasey",),
                "hosts": (),
                "capabilities": (),
                "modes": (otc.TableMode.BASE_MODE,),
                "local": False,
                "handles_paths": False,
                "open_table": lambda self, _address: otc.OperationResult(
                    value=otc.TableBinding(
                        uri=otc.DirectTableAddress("leasey://warehouse/orders").uri,
                        mode=otc.TableMode.BASE_MODE,
                        schema=pl.Schema({"order_id": pl.Int64}),
                        observed_revision=None,
                        connector_id="leasey",
                    ),
                    outcome=otc.Outcome.SUCCEEDED,
                    commit=otc.CommitState.NOT_APPLICABLE,
                    verification=otc.VerificationState.PASSED,
                    receipts=(),
                ),
                "inspect_table": lambda self, _binding: None,
                "capabilities_for": lambda self, _binding: None,
                "read_table": lambda self, _binding, **_kwargs: None,
                "insert_rows": lambda self, _binding, _frame: None,
                "update_rows": lambda self, _binding, _frame, **_kwargs: None,
                "delete_rows": lambda self, _binding, **_kwargs: None,
                "drop_table": lambda self, _binding: None,
                "begin_transaction": lambda self, _binding: None,
                "create_table": lambda self, _source, _destination: None,
                "close": lambda self: None,
            },
        )()

    descriptor = PluginDescriptor(
        "leasey",
        ConnectorIdentity("leasey", "0.1.0", "1.0"),
        ("leasey",),
        factory,
        modes=(LegacyTableMode.BASE,),
    )
    config = otc.ClientConfig(
        providers={
            "leasey": ProviderConfig(
                "leasey",
                credential_reference="warehouse",
                environment={"region": "OTC_REGION"},
                options={"batch_size": 1000},
            )
        },
        credentials={"warehouse": {"token": otc.CredentialBinding("OTC_TOKEN")}},
    )
    registry = otc.ConnectorRegistry.from_descriptors(
        (descriptor,),
        config,
        resolver=resolver,
        environ={"OTC_REGION": "apac"},
    )
    client = otc.Client(registry=registry)

    client.open("leasey://warehouse/orders").require_value()

    assert observed == {
        "credentials": {"token": "secret"},
        "environment": {"region": "apac"},
        "options": {"batch_size": 1000},
        "lease_disposed_during_factory": False,
    }
    assert resolver.last_lease is not None
    assert resolver.last_lease.disposed is True
    assert events == ["resolve:leasey", "dispose"]
