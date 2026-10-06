from __future__ import annotations

from types import SimpleNamespace

import pytest
from open_table_connector.contract import (
    CapabilityIdentity,
    ConnectorIdentity,
    OperationDescriptor,
    TargetSelector,
)
from open_table_connector.sdk.discovery import OperationCatalog, resolve_capabilities
from open_table_connector.sdk.result import Outcome


def descriptor(operation_id: str = "range.read", *, capability: str = "spreadsheet.range.read"):
    return OperationDescriptor(
        schema="otc.operation/1.0",
        operation_id=operation_id,
        version="1.0",
        target_kind="range",
        arguments_schema={
            "type": "object",
            "properties": {"address": {"type": "string"}},
            "required": ["address"],
            "additionalProperties": False,
        },
        capability=f"{capability}/1.0",
        effects=("read",),
        examples=({"address": "A1"},),
    )


def test_duplicate_schema_registration_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate operation descriptor"):
        OperationCatalog((descriptor(), descriptor()))


def test_help_does_not_activate_provider() -> None:
    calls: list[str] = []

    def factory(_context):
        calls.append("factory")
        raise AssertionError("static help activated provider")

    from open_table_connector.contract import PluginDescriptor, TableMode
    from open_table_connector.sdk import ClientConfig, ConnectorRegistry

    plugin = PluginDescriptor(
        "fake",
        ConnectorIdentity("fake", "0.1.0", "1.0"),
        ("fake",),
        factory,
        capabilities=(CapabilityIdentity("spreadsheet.range.read", "1.0"),),
        modes=(TableMode.SHEET,),
    )
    registry = ConnectorRegistry.from_descriptors((plugin,), ClientConfig.empty(), environ={})
    catalog = OperationCatalog((descriptor(),))
    assert catalog.describe("spreadsheet", "range.read")[0].operation_id == "range.read"
    assert calls == []
    assert registry.list()[0].identity.connector_id == "fake"


def test_absent_spreadsheet_package_keeps_core_help() -> None:
    catalog = OperationCatalog((descriptor(),))
    assert catalog.describe("spreadsheet")


def test_missing_file_uses_static_creation_only(tmp_path) -> None:
    target = TargetSelector((tmp_path / "new.xlsx").as_uri())
    result = resolve_capabilities(_client_with_descriptor(), target, catalog=OperationCatalog((descriptor(),)))
    assert result.outcome is Outcome.SUCCEEDED
    observation = result.require_value()
    assert observation.resolution == "static"


def test_remote_auth_failure_not_supported() -> None:
    class FailingRegistry:
        def descriptor_for(self, _target):
            return SimpleNamespace(
                identity=ConnectorIdentity("remote", "0.1.0", "1.0"),
                capabilities=(CapabilityIdentity("spreadsheet.range.read", "1.0"),),
            )

        def connector_for(self, _target):
            raise RuntimeError("credential failure")

    from open_table_connector.sdk import Client

    client = Client(registry=FailingRegistry())
    result = resolve_capabilities(client, TargetSelector("https://example.test/doc"), catalog=OperationCatalog((descriptor(),)))
    assert result.outcome in {Outcome.UNKNOWN, Outcome.REJECTED}
    assert result.value is None


def _client_with_descriptor():
    from open_table_connector.sdk import Client

    class Registry:
        def descriptor_for(self, _target):
            return SimpleNamespace(
                identity=ConnectorIdentity("local", "0.1.0", "1.0"),
                capabilities=(CapabilityIdentity("spreadsheet.range.read", "1.0"),),
            )

    return Client(registry=Registry())
