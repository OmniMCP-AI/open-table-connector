"""Capability declaration for the local-files Connector."""

from open_table_connector.contract import CapabilityManifest, TableMode

from .identity import (
    CONNECTOR_IDENTITY,
    TABLE_INSPECT_CAPABILITY,
    TABLE_READ_ARROW_CAPABILITY,
    TABLE_READ_POLARS_CAPABILITY,
    URI_RESOLVER_CAPABILITY,
)


def capability_manifest(*, connector, uri_schemes: tuple[str, ...]) -> CapabilityManifest:
    return CapabilityManifest(
        connector=connector,
        capabilities=(
            URI_RESOLVER_CAPABILITY,
            TABLE_INSPECT_CAPABILITY,
            TABLE_READ_ARROW_CAPABILITY,
            TABLE_READ_POLARS_CAPABILITY,
        ),
        modes=(TableMode.SHEET,),
        uri_schemes=uri_schemes,
    )


CAPABILITY_MANIFEST = capability_manifest(
    connector=CONNECTOR_IDENTITY,
    uri_schemes=("file", "json", "jsonl"),
)
