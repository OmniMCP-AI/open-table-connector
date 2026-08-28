from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate
import pytest

from open_connectors.contract import (
    BaseConvention,
    CapabilityIdentity,
    CapabilityManifest,
    ConnectorIdentity,
    NeutralReceipt,
    SheetConvention,
    TableMode,
    TableURI,
)
from open_connectors.contract.errors import ConnectorError


SCHEMA_ROOT = Path(__file__).parents[3] / "specification" / "schemas"


def _schema(name: str) -> dict:
    return json.loads((SCHEMA_ROOT / name).read_text(encoding="utf-8"))


def test_capability_manifest_wire_validates_against_schema() -> None:
    manifest = CapabilityManifest(
        connector=ConnectorIdentity("local_files", "0.1.0", "1.0"),
        capabilities=(CapabilityIdentity("table.read.arrow", "1.0"),),
        modes=(TableMode.SHEET,),
        uri_schemes=("file",),
    )

    validate(manifest.to_wire(), _schema("capability-manifest-v1.schema.json"))


def test_capability_manifest_managed_io_round_trips_and_validates() -> None:
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
                },
                "boundedness": "bounded",
                "features": ["readback"],
            }
        },
    )

    wire = manifest.to_wire()
    validate(wire, _schema("capability-manifest-v2.schema.json"))
    assert CapabilityManifest.from_wire(wire) == manifest


@pytest.mark.parametrize(
    "managed_io",
    [
        {"scan": {}},
        {"read": {"capability_id": "unlisted", "config_schema": {}, "boundedness": "bounded", "features": []}},
        {"read": {"capability_id": "table.read.arrow", "config_schema": {}, "boundedness": "bounded", "features": ["unknown"]}},
        {"read": {"capability_id": "table.read.arrow", "config_schema": {"properties": {"token": {"default": "secret"}}}, "boundedness": "bounded", "features": []}},
    ],
)
def test_capability_manifest_rejects_invalid_managed_io(managed_io) -> None:
    manifest = CapabilityManifest(
        connector=ConnectorIdentity("local_files", "0.2.0", "1.0"),
        capabilities=(CapabilityIdentity("table.read.arrow", "1.0"),),
        modes=(TableMode.SHEET,),
        uri_schemes=("file",),
    )

    with pytest.raises(ValueError):
        CapabilityManifest(
            connector=manifest.connector,
            capabilities=manifest.capabilities,
            modes=manifest.modes,
            uri_schemes=manifest.uri_schemes,
            managed_io=managed_io,
        )


def test_receipt_wire_validates_against_schema() -> None:
    receipt = NeutralReceipt(
        connector=ConnectorIdentity("local_files", "0.1.0", "1.0"),
        capability=CapabilityIdentity("table.read.arrow", "1.0"),
        operation_id="op-1",
        safe_uri=TableURI("file:///data/orders.csv"),
        mode=TableMode.SHEET,
        source_revision="sha256:source",
        schema_fingerprint="sha256:schema",
        content_fingerprint="sha256:content",
        coordinate_convention=SheetConvention(sheet="data"),
        row_count=2,
        batch_count=1,
    )

    validate(receipt.to_wire(), _schema("neutral-receipt-v1.schema.json"))


def test_error_wire_validates_against_schema() -> None:
    error = ConnectorError.authentication("authentication failed")

    validate(error.to_wire(), _schema("connector-error-v1.schema.json"))
