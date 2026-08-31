"""Provider-neutral registration metadata for dbt."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from open_table_connector.contract import PluginDescriptor


def provider_plugin() -> PluginDescriptor:
    from .identity import CONNECTOR_IDENTITY

    return PluginDescriptor("dbt", CONNECTOR_IDENTITY, ("dbt",), _factory)


def _factory(*, env: Mapping[str, str], transports: Mapping[str, Any]) -> Any:
    del env, transports
    from .connector import DbtConnector

    return DbtConnector()


__all__ = ["provider_plugin"]
