from __future__ import annotations

import pytest

from open_table_connector.contract import (
    CapabilityIdentity,
    CapabilityManifest,
    ConnectorIdentity,
    TableMode,
)


def test_connector_identity_keeps_contract_and_implementation_versions_separate() -> None:
    identity = ConnectorIdentity(
        connector_id="local_files",
        connector_version="0.1.0",
        contract_version="1.0",
    )

    assert identity.to_wire() == {
        "connector_id": "local_files",
        "connector_version": "0.1.0",
        "contract_version": "1.0",
    }


def test_capability_manifest_rejects_duplicate_capability_ids() -> None:
    identity = ConnectorIdentity("local_files", "0.1.0", "1.0")
    capability = CapabilityIdentity("table.read.arrow", "1.0")

    with pytest.raises(ValueError, match="duplicate capability"):
        CapabilityManifest(
            connector=identity,
            capabilities=(capability, capability),
            modes=(TableMode.SHEET,),
            uri_schemes=("file",),
        )


def test_table_mode_is_closed_to_base_and_sheet() -> None:
    assert tuple(mode.value for mode in TableMode) == ("base", "sheet")


def test_capability_manifest_carries_plain_managed_io_facts() -> None:
    manifest = CapabilityManifest(
        connector=ConnectorIdentity("local_files", "0.2.0", "1.0"),
        capabilities=(CapabilityIdentity("table.read.polars", "1.0"),),
        modes=(TableMode.SHEET,),
        uri_schemes=("file",),
        managed_io={
            "read": {
                "capability_id": "table.read.polars",
                "config_schema": {
                    "type": "object",
                    "properties": {
                        "credential_ref": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
                "boundedness": "bounded",
                "features": [],
            }
        },
    )

    assert CapabilityManifest.from_wire(manifest.to_wire()) == manifest


def test_managed_io_rejects_secret_schema_fields() -> None:
    with pytest.raises(ValueError, match="secret"):
        CapabilityManifest(
            connector=ConnectorIdentity("local_files", "0.2.0", "1.0"),
            capabilities=(CapabilityIdentity("table.read.polars", "1.0"),),
            modes=(TableMode.SHEET,),
            uri_schemes=("file",),
            managed_io={
                "read": {
                    "capability_id": "table.read.polars",
                    "config_schema": {
                        "type": "object",
                        "properties": {"password": {"type": "string"}},
                    },
                    "boundedness": "bounded",
                    "features": [],
                }
            },
        )
