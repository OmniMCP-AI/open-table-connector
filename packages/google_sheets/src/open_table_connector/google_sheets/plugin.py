"""Provider-neutral registration metadata for Google Sheets."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from open_table_connector.contract import (
    HOST_GOOGLE_DOCS,
    PROVIDER_GOOGLE_SHEETS,
    SCHEME_GSHEETS,
    SCHEME_HTTPS,
    PluginDescriptor,
)


def provider_plugin() -> PluginDescriptor:
    from .connector import CONNECTOR_IDENTITY

    return PluginDescriptor(
        PROVIDER_GOOGLE_SHEETS,
        CONNECTOR_IDENTITY,
        (SCHEME_GSHEETS, SCHEME_HTTPS),
        _factory,
        (HOST_GOOGLE_DOCS,),
    )


def _factory(*, env: Mapping[str, str], transports: Mapping[str, Any]) -> Any:
    from .connector import GoogleSheetsConnector

    return GoogleSheetsConnector(
        transports.get(PROVIDER_GOOGLE_SHEETS),
        access_token=env.get("GOOGLE_SHEETS_ACCESS_TOKEN"),
    )


__all__ = ["provider_plugin"]
