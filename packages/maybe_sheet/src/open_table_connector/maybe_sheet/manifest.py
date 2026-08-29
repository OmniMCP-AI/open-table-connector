"""Managed I/O capability declaration for MaybeSheet."""

from open_table_connector.contract import CapabilityManifest, TableMode

from .identity import (
    BASE_INSPECT_CAPABILITY,
    BASE_READ_CAPABILITY,
    CONNECTOR_IDENTITY,
    SHEET_INSPECT_CAPABILITY,
    SHEET_READ_CAPABILITY,
    TABLE_WRITE_CAPABILITY,
)


READ_CONFIG_SCHEMA = {
    "type": "object",
    "required": ["target"],
    "properties": {
        "target": {"type": "string", "minLength": 1},
        "credential_ref": {"type": "string", "minLength": 1},
        "max_rows": {"type": ["integer", "null"], "minimum": 1},
        "max_bytes": {"type": ["integer", "null"], "minimum": 1},
        "timeout_seconds": {"type": ["number", "null"], "exclusiveMinimum": 0},
    },
    "additionalProperties": False,
}

WRITE_CONFIG_SCHEMA = {
    "type": "object",
    "required": ["target"],
    "properties": {
        "target": {"type": "string", "minLength": 1},
        "if_exists": {"enum": ["append"]},
        "credential_ref": {"type": "string", "minLength": 1},
    },
    "additionalProperties": False,
}


CAPABILITY_MANIFEST = CapabilityManifest(
    connector=CONNECTOR_IDENTITY,
    capabilities=(
        BASE_READ_CAPABILITY,
        SHEET_READ_CAPABILITY,
        BASE_INSPECT_CAPABILITY,
        SHEET_INSPECT_CAPABILITY,
        TABLE_WRITE_CAPABILITY,
    ),
    modes=(TableMode.BASE, TableMode.SHEET),
    uri_schemes=("maybe", "https"),
    managed_io={
        "read": {
            "capability_id": BASE_READ_CAPABILITY.capability_id,
            "config_schema": READ_CONFIG_SCHEMA,
            "boundedness": "bounded",
            "features": [],
        },
        "write": {
            "capability_id": TABLE_WRITE_CAPABILITY.capability_id,
            "config_schema": WRITE_CONFIG_SCHEMA,
            "features": ["readback"],
        },
    },
)
