"""Process-host registration for PostgreSQL temporal handlers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from open_table_connector.contract import PluginDescriptor


def provider_plugin() -> PluginDescriptor:
    from .identity import CONNECTOR_IDENTITY

    return PluginDescriptor("postgres", CONNECTOR_IDENTITY, ("postgres",), _provider_factory)


def _provider_factory(*, env: Mapping[str, str], transports: Mapping[str, Any]) -> Any:
    del env
    from .reader import PostgresConnector

    return PostgresConnector(transports.get("postgres"))


def process_plugin(**kwargs: Any) -> tuple[Any, Any]:
    from .temporal import PostgresManagedTemporalStore, PostgresTemporalExecutor

    document = kwargs["document"]
    target = kwargs["target"]
    descriptor = kwargs["descriptor"]
    root = kwargs["root"]
    table = _required_text(document, "physical_table")
    store = (
        PostgresManagedTemporalStore(target, root, descriptor)
        if bool(document["managed"])
        else None
    )
    return PostgresTemporalExecutor(descriptor, table, managed_store=store), store


def _required_text(document: dict[str, object], field: str) -> str:
    value = document.get(field)
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"process {field} must be a non-empty string")
    return value


__all__ = ["process_plugin", "provider_plugin"]
