"""Capability declaration for the local-files Connector."""

from open_table_connector.contract import CapabilityManifest, TableMode

from .identity import (
    CONNECTOR_IDENTITY,
    TABLE_INSPECT_CAPABILITY,
    TABLE_READ_ARROW_CAPABILITY,
    TABLE_READ_POLARS_CAPABILITY,
    URI_RESOLVER_CAPABILITY,
)


LOCAL_READ_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "separator": {"type": "string", "minLength": 1, "maxLength": 1},
        "encoding": {"type": "string", "minLength": 1},
        "sheet": {"type": ["string", "null"]},
        "header_row": {"type": "integer", "minimum": 1},
        "max_rows": {"type": ["integer", "null"], "minimum": 1},
        "max_bytes": {"type": ["integer", "null"], "minimum": 1},
        "timeout_seconds": {"type": ["number", "null"], "exclusiveMinimum": 0},
        "credential_ref": {"type": "string", "minLength": 1},
    },
    "additionalProperties": False,
}


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
        managed_io={
            "read": {
                "capability_id": TABLE_READ_POLARS_CAPABILITY.capability_id,
                "config_schema": LOCAL_READ_CONFIG_SCHEMA,
                "boundedness": "bounded",
                "features": [],
            }
        },
    )


CAPABILITY_MANIFEST = capability_manifest(connector=CONNECTOR_IDENTITY, uri_schemes=("file",))
