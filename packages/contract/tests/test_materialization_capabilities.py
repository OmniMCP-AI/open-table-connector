from __future__ import annotations

import pytest
from open_table_connector.contract import (
    CAPABILITY_TABLE_MATERIALIZE_CREATE,
    CapabilityIdentity,
    CapabilityManifest,
    ConnectorIdentity,
    MaterializationCapability,
    TableMode,
)


def test_manifest_advertises_create_profile_per_destination_mode() -> None:
    manifest = CapabilityManifest(
        connector=ConnectorIdentity("example", "1.0.0", "1.0"),
        capabilities=(
            CapabilityIdentity("table.write", "1.0"),
            CapabilityIdentity(CAPABILITY_TABLE_MATERIALIZE_CREATE, "1.0"),
        ),
        modes=(TableMode.BASE, TableMode.SHEET),
        uri_schemes=("example",),
        materialization=(
            MaterializationCapability(
                capability=CapabilityIdentity(CAPABILITY_TABLE_MATERIALIZE_CREATE, "1.0"),
                profiles=("otc.portable-table/v1",),
                modes=(TableMode.SHEET,),
            ),
        ),
    )

    assert manifest.materialization[0].profiles == ("otc.portable-table/v1",)
    assert manifest.materialization[0].modes == (TableMode.SHEET,)
    assert CapabilityManifest.from_wire(manifest.to_wire()) == manifest


def test_materialization_capability_allows_additional_profiles() -> None:
    capability = MaterializationCapability(
        capability=CapabilityIdentity(CAPABILITY_TABLE_MATERIALIZE_CREATE, "1.0"),
        profiles=("otc.portable-table/v1", "provider.experimental/v1"),
        modes=(TableMode.SHEET,),
    )
    assert capability.profiles[-1] == "provider.experimental/v1"


def test_materialization_capability_requires_the_portable_profile() -> None:
    with pytest.raises(ValueError, match="portable"):
        MaterializationCapability(
            capability=CapabilityIdentity(CAPABILITY_TABLE_MATERIALIZE_CREATE, "1.0"),
            profiles=("provider.experimental/v1",),
            modes=(TableMode.SHEET,),
        )


def test_manifest_rejects_create_without_portable_materialization_metadata() -> None:
    with pytest.raises(ValueError, match="materialization"):
        CapabilityManifest(
            connector=ConnectorIdentity("example", "1.0.0", "1.0"),
            capabilities=(CapabilityIdentity(CAPABILITY_TABLE_MATERIALIZE_CREATE, "1.0"),),
            modes=(TableMode.BASE,),
            uri_schemes=("example",),
        )
