"""Provider-neutral registration metadata for Feishu Bitable."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from open_table_connector.contract import (
    PROVIDER_FEISHU_BITABLE,
    SCHEME_FEISHU,
    PluginDescriptor,
)


def provider_plugin() -> PluginDescriptor:
    from .connector import CONNECTOR_IDENTITY

    return PluginDescriptor(
        PROVIDER_FEISHU_BITABLE,
        CONNECTOR_IDENTITY,
        (SCHEME_FEISHU, PROVIDER_FEISHU_BITABLE),
        _factory,
    )


def _factory(*, env: Mapping[str, str], transports: Mapping[str, Any]) -> Any:
    from .connector import FeishuBitableConnector

    return FeishuBitableConnector(
        transports.get(PROVIDER_FEISHU_BITABLE),
        tenant_access_token=env.get("FEISHU_TENANT_ACCESS_TOKEN"),
    )


__all__ = ["provider_plugin"]
