"""Capability declaration for the local-files Connector."""

from open_table_connector.contract import CapabilityManifest, TableMode

from .identity import (
    CONNECTOR_IDENTITY,
    TABLE_INSPECT_CAPABILITY,
    TABLE_READ_ARROW_CAPABILITY,
    TABLE_READ_POLARS_CAPABILITY,
    URI_RESOLVER_CAPABILITY,
)

CAPABILITY_MANIFEST = CapabilityManifest(
    connector=CONNECTOR_IDENTITY,
    capabilities=(
        URI_RESOLVER_CAPABILITY,
        TABLE_INSPECT_CAPABILITY,
        TABLE_READ_ARROW_CAPABILITY,
        TABLE_READ_POLARS_CAPABILITY,
    ),
    modes=(TableMode.SHEET,),
    uri_schemes=("file",),
)
