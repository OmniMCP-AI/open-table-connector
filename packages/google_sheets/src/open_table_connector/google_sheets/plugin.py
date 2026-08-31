"""Provider-neutral registration metadata for Google Sheets."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from open_table_connector.contract import PluginDescriptor


def provider_plugin() -> PluginDescriptor:
    from .connector import CONNECTOR_IDENTITY

    return PluginDescriptor(
        "google_sheets",
        CONNECTOR_IDENTITY,
        ("gsheets", "https"),
        _factory,
        ("docs.google.com",),
    )


def _factory(*, env: Mapping[str, str], transports: Mapping[str, Any]) -> Any:
    from .connector import GoogleSheetsConnector

    return GoogleSheetsConnector(
        transports.get("google_sheets"),
        access_token=env.get("GOOGLE_SHEETS_ACCESS_TOKEN"),
    )


__all__ = ["provider_plugin"]
