"""Managed I/O facts for the MaybeSheet connector."""

from open_connectors.contract import CapabilityManifest, TableMode

from .identity import (
    BASE_INSPECT_CAPABILITY,
    BASE_READ_CAPABILITY,
    CONNECTOR_IDENTITY,
    SHEET_INSPECT_CAPABILITY,
    SHEET_READ_CAPABILITY,
    TABLE_WRITE_CAPABILITY,
)


_READ_SCHEMA = {
    "type": "object",
    "properties": {
        "target": {"type": "string", "minLength": 1},
        "credential_ref": {"type": "string", "minLength": 1},
        "max_rows": {"type": ["integer", "null"], "minimum": 0},
    },
    "additionalProperties": False,
}


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
    uri_schemes=("maybe", "https"),
    managed_io={
        "read": {
            "capability_id": BASE_READ_CAPABILITY.capability_id,
            "config_schema": _READ_SCHEMA,
            "boundedness": "bounded",
            "features": [],
        },
        "write": {
            "capability_id": TABLE_WRITE_CAPABILITY.capability_id,
            "config_schema": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "minLength": 1},
                    "if_exists": {"enum": ["append"]},
                    "credential_ref": {"type": "string", "minLength": 1},
                },
                "additionalProperties": False,
            },
            "features": ["readback"],
        },
    },
)


__all__ = ["CAPABILITY_MANIFEST"]
