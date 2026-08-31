"""Provider-neutral registration metadata for Feishu Bitable."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from open_table_connector.contract import PluginDescriptor


def provider_plugin() -> PluginDescriptor:
    from .connector import CONNECTOR_IDENTITY

    return PluginDescriptor(
        "feishu_bitable",
        CONNECTOR_IDENTITY,
        ("feishu", "feishu_bitable"),
        _factory,
    )


def _factory(*, env: Mapping[str, str], transports: Mapping[str, Any]) -> Any:
    from .connector import FeishuBitableConnector

    return FeishuBitableConnector(
        transports.get("feishu_bitable"),
        tenant_access_token=env.get("FEISHU_TENANT_ACCESS_TOKEN"),
    )


__all__ = ["provider_plugin"]
