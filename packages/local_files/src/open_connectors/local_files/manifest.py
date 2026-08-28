"""Capability declaration for the local-files Connector."""

from open_connectors.contract import CapabilityManifest, TableMode

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
    managed_io={
        "read": {
            "capability_id": TABLE_READ_POLARS_CAPABILITY.capability_id,
            "config_schema": {
                "type": "object",
                "properties": {
                    "separator": {"type": "string", "minLength": 1, "maxLength": 1},
                    "encoding": {"type": "string", "minLength": 1},
                    "sheet": {"type": ["string", "null"]},
                    "header_row": {"type": "integer", "minimum": 1},
                    "max_rows": {"type": ["integer", "null"], "minimum": 1},
                    "max_bytes": {"type": ["integer", "null"], "minimum": 1},
                    "timeout_seconds": {"type": ["integer", "null"], "minimum": 1},
                    "credential_ref": {"type": "string", "minLength": 1},
                },
                "additionalProperties": False,
            },
            "boundedness": "bounded",
            "features": [],
        }
    },
)
