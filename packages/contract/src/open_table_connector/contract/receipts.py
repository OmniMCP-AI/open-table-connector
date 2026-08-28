"""Neutral physical read receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .capabilities import TableMode
from .coordinates import BaseConvention, SheetConvention
from .identity import CapabilityIdentity, ConnectorIdentity
from .uri import TableURI


def _convention_to_wire(value: BaseConvention | SheetConvention) -> dict[str, Any]:
    if isinstance(value, BaseConvention):
        return {
            "mode": "base",
            "record_id_field": value.record_id_field,
            "key_fields": list(value.key_fields),
            "ordinal_snapshot_id": value.ordinal_snapshot_id,
        }
    return {
        "mode": "sheet",
        "sheet": value.sheet,
        "header_rows": value.header_rows,
        "first_data_row": value.first_data_row,
    }


def _convention_from_wire(value: Mapping[str, Any]) -> BaseConvention | SheetConvention:
    mode = value.get("mode")
    if mode == "base":
        required = {"mode", "record_id_field", "key_fields", "ordinal_snapshot_id"}
        if set(value) != required:
            raise ValueError("base coordinate convention has unexpected keys")
        return BaseConvention(
            record_id_field=value["record_id_field"],
            key_fields=tuple(value["key_fields"]),
            ordinal_snapshot_id=value["ordinal_snapshot_id"],
        )
    if mode == "sheet":
        required = {"mode", "sheet", "header_rows", "first_data_row"}
        if set(value) != required:
            raise ValueError("sheet coordinate convention has unexpected keys")
        return SheetConvention(
            sheet=value["sheet"],
            header_rows=value["header_rows"],
            first_data_row=value["first_data_row"],
        )
    raise ValueError("coordinate convention mode must be base or sheet")


@dataclass(frozen=True)
class NeutralReceipt:
    connector: ConnectorIdentity
    capability: CapabilityIdentity
    operation_id: str
    safe_uri: TableURI
    mode: TableMode
    source_revision: str
    schema_fingerprint: str
    content_fingerprint: str
    coordinate_convention: BaseConvention | SheetConvention
    row_count: int | None
    batch_count: int | None
    vendor_receipt_ref: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "operation_id",
            "source_revision",
            "schema_fingerprint",
            "content_fingerprint",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if self.mode.value != self.coordinate_convention.mode:
            raise ValueError("receipt mode and coordinate convention disagree")
        for name in ("row_count", "batch_count"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError(f"{name} must be a non-negative integer when supplied")
        if self.vendor_receipt_ref is not None and not isinstance(self.vendor_receipt_ref, str):
            raise ValueError("vendor_receipt_ref must be a string when supplied")

    def to_wire(self) -> dict[str, Any]:
        return {
            "contract_version": self.connector.contract_version,
            "connector": self.connector.to_wire(),
            "capability": self.capability.to_wire(),
            "operation_id": self.operation_id,
            "safe_uri": self.safe_uri.to_wire(),
            "mode": self.mode.value,
            "source_revision": self.source_revision,
            "schema_fingerprint": self.schema_fingerprint,
            "content_fingerprint": self.content_fingerprint,
            "coordinate_convention": _convention_to_wire(self.coordinate_convention),
            "row_count": self.row_count,
            "batch_count": self.batch_count,
            "vendor_receipt_ref": self.vendor_receipt_ref,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> "NeutralReceipt":
        required = {
            "contract_version",
            "connector",
            "capability",
            "operation_id",
            "safe_uri",
            "mode",
            "source_revision",
            "schema_fingerprint",
            "content_fingerprint",
            "coordinate_convention",
            "row_count",
            "batch_count",
            "vendor_receipt_ref",
        }
        if set(payload) != required:
            raise ValueError("NeutralReceipt wire object has unexpected keys")
        connector = ConnectorIdentity.from_wire(payload["connector"])
        if payload["contract_version"] != connector.contract_version:
            raise ValueError("receipt contract_version does not match connector identity")
        return cls(
            connector=connector,
            capability=CapabilityIdentity.from_wire(payload["capability"]),
            operation_id=payload["operation_id"],
            safe_uri=TableURI.from_wire(payload["safe_uri"]),
            mode=TableMode(payload["mode"]),
            source_revision=payload["source_revision"],
            schema_fingerprint=payload["schema_fingerprint"],
            content_fingerprint=payload["content_fingerprint"],
            coordinate_convention=_convention_from_wire(payload["coordinate_convention"]),
            row_count=payload["row_count"],
            batch_count=payload["batch_count"],
            vendor_receipt_ref=payload["vendor_receipt_ref"],
        )
