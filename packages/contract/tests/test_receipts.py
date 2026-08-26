from __future__ import annotations

from open_connectors.contract import (
    BaseConvention,
    CapabilityIdentity,
    ConnectorIdentity,
    SheetConvention,
    TableMode,
    TableURI,
)
from open_connectors.contract.receipts import NeutralReceipt


def test_read_receipt_round_trips_without_vendor_credentials() -> None:
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

    wire = receipt.to_wire()
    restored = NeutralReceipt.from_wire(wire)

    assert restored == receipt
    assert wire["coordinate_convention"]["mode"] == "sheet"


def test_base_receipt_keeps_base_convention_parallel_to_frame_schema() -> None:
    receipt = NeutralReceipt(
        connector=ConnectorIdentity("postgres", "0.1.0", "1.0"),
        capability=CapabilityIdentity("table.read.arrow", "1.0"),
        operation_id="op-2",
        safe_uri=TableURI("postgres://warehouse/public.orders"),
        mode=TableMode.BASE,
        source_revision="revision-1",
        schema_fingerprint="schema-1",
        content_fingerprint="content-1",
        coordinate_convention=BaseConvention(key_fields=("order_id",)),
        row_count=1,
        batch_count=1,
    )

    assert receipt.to_wire()["coordinate_convention"] == {
        "mode": "base",
        "record_id_field": None,
        "key_fields": ["order_id"],
        "ordinal_snapshot_id": None,
    }
