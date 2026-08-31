"""Explicit v2 contracts for truthful partial table reads."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

import pyarrow as pa

from .capabilities import TableMode
from .coordinates import BaseConvention
from .identity import CapabilityIdentity, ConnectorIdentity
from .read import TableReadRequest
from .receipts import _convention_to_wire
from .uri import TableURI

BOUNDED_ARROW_TABLE_READ_CAPABILITY = CapabilityIdentity("table.read.arrow.bounded", "2.0")


class ReadExtent(StrEnum):
    COMPLETE = "complete"
    TRUNCATED = "truncated"


@dataclass(frozen=True)
class BoundedTableReadRequest(TableReadRequest):
    max_output_rows: int = field(default=1)

    def __post_init__(self) -> None:
        if isinstance(self.max_output_rows, bool) or not isinstance(self.max_output_rows, int):
            raise TypeError("max_output_rows must be an integer")
        if self.max_output_rows < 1:
            raise ValueError("max_output_rows must be positive")


@dataclass(frozen=True)
class BoundedReadReceipt:
    connector: ConnectorIdentity
    safe_uri: TableURI
    mode: TableMode
    source_snapshot_reference: str | None
    schema_fingerprint: str
    emitted_content_fingerprint: str
    coordinate_convention: BaseConvention
    rows_emitted: int
    batches_emitted: int
    extent: ReadExtent
    next_token: str | None = None
    operation_id: str = "bounded-read"
    schema_version: str = "otc.bounded-read-receipt/v2"

    def to_wire(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "connector": self.connector.to_wire(),
            "safe_uri": self.safe_uri.to_wire(),
            "mode": self.mode.value,
            "source_snapshot_reference": self.source_snapshot_reference,
            "schema_fingerprint": self.schema_fingerprint,
            "emitted_content_fingerprint": self.emitted_content_fingerprint,
            "coordinate_convention": _convention_to_wire(self.coordinate_convention),
            "rows_emitted": self.rows_emitted,
            "batches_emitted": self.batches_emitted,
            "extent": self.extent.value,
            "next_token": self.next_token,
            "operation_id": self.operation_id,
        }


@dataclass(frozen=True)
class BoundedArrowTableReadResult:
    table: pa.Table
    receipt: BoundedReadReceipt


@runtime_checkable
class BoundedArrowTableReader(Protocol):
    def read_arrow_bounded(
        self, request: BoundedTableReadRequest
    ) -> BoundedArrowTableReadResult: ...


__all__ = [
    "BOUNDED_ARROW_TABLE_READ_CAPABILITY",
    "BoundedArrowTableReadResult",
    "BoundedArrowTableReader",
    "BoundedReadReceipt",
    "BoundedTableReadRequest",
    "ReadExtent",
]
