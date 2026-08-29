"""Capability declaration for the MaybeSheet Connector."""

from open_table_connector.contract import CapabilityManifest, TableMode

from .identity import (
    BASE_INSPECT_CAPABILITY,
    BASE_READ_CAPABILITY,
    CONNECTOR_IDENTITY,
    SHEET_INSPECT_CAPABILITY,
    SHEET_READ_CAPABILITY,
    TABLE_WRITE_CAPABILITY,
)


CAPABILITY_MANIFEST = CapabilityManifest(
    connector=CONNECTOR_IDENTITY,
    capabilities=(
        BASE_READ_CAPABILITY,
        BASE_INSPECT_CAPABILITY,
        SHEET_READ_CAPABILITY,
        SHEET_INSPECT_CAPABILITY,
        TABLE_WRITE_CAPABILITY,
    ),
    modes=(TableMode.BASE, TableMode.SHEET),
    uri_schemes=("https", "maybe"),
)


__all__ = ["CAPABILITY_MANIFEST"]
