"""Process-host registration for SQLite temporal handlers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from open_table_connector.contract import PROVIDER_SQLITE, PluginDescriptor


def provider_plugin() -> PluginDescriptor:
    from .identity import CONNECTOR_IDENTITY

    return PluginDescriptor(
        PROVIDER_SQLITE, CONNECTOR_IDENTITY, (PROVIDER_SQLITE,), _provider_factory
    )


def _provider_factory(*, env: Mapping[str, str], transports: Mapping[str, Any]) -> Any:
    del env
    from .reader import SQLiteConnector

    return SQLiteConnector(transports.get(PROVIDER_SQLITE))


def process_plugin(**kwargs: Any) -> tuple[Any, Any]:
    from .temporal import SQLiteManagedTemporalStore, SQLiteTemporalExecutor

    document = kwargs["document"]
    target = kwargs["target"]
    descriptor = kwargs["descriptor"]
    root = kwargs["root"]
    table = _required_text(document, "physical_table")
    store = (
        SQLiteManagedTemporalStore(target, root, descriptor)
        if bool(document["managed"])
        else None
    )
    return SQLiteTemporalExecutor(descriptor, table, managed_store=store), store


def _required_text(document: dict[str, object], field: str) -> str:
    value = document.get(field)
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"process {field} must be a non-empty string")
    return value


__all__ = ["process_plugin", "provider_plugin"]
