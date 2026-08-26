from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import polars as pl
import pyarrow as pa
import pytest

from open_connectors.contract import (
    ArrowReadResult,
    ArrowTableReader,
    CapabilityIdentity,
    ConnectorIdentity,
    NeutralReceipt,
    PolarsReadResult,
    PolarsTableReader,
    SheetConvention,
    TableMode,
    TableReadRequest,
    TableURI,
)
from open_connectors.conformance.assertions import (
    assert_arrow_polars_equal,
    assert_read_connector_conformance,
    assert_receipt_safe,
)


def _receipt(*, operation_id: str = "op-1", content: str = "content-1") -> NeutralReceipt:
    return NeutralReceipt(
        connector=ConnectorIdentity("reference", "0.1.0", "1.0"),
        capability=CapabilityIdentity("table.read", "1.0"),
        operation_id=operation_id,
        safe_uri=TableURI("file:///fixture.csv"),
        mode=TableMode.SHEET,
        source_revision="source-1",
        schema_fingerprint="schema-1",
        content_fingerprint=content,
        coordinate_convention=SheetConvention(sheet="data"),
        row_count=2,
        batch_count=1,
    )


class ReferenceReader(ArrowTableReader, PolarsTableReader):
    def __init__(self) -> None:
        self.table = pa.table(
            {
                "id": pa.array(["a", "b"], type=pa.string()),
                "amount": pa.array([Decimal("1.20"), None], type=pa.decimal128(10, 2)),
            }
        )

    def read_arrow(self, request: TableReadRequest) -> ArrowReadResult:
        return ArrowReadResult(self.table, _receipt())

    def read_polars(self, request: TableReadRequest) -> PolarsReadResult:
        return PolarsReadResult(pl.from_arrow(self.table), _receipt())


class BrokenReader(ReferenceReader):
    def read_polars(self, request: TableReadRequest) -> PolarsReadResult:
        result = super().read_polars(request)
        return PolarsReadResult(
            result.frame.with_columns(pl.col("amount").cast(pl.Decimal(10, 3))),
            result.receipt,
        )


class BrokenReceiptReader(ReferenceReader):
    def read_polars(self, request: TableReadRequest) -> PolarsReadResult:
        result = super().read_polars(request)
        return PolarsReadResult(result.frame, replace(result.receipt, operation_id="op-different"))


class BrokenOrderReader(ReferenceReader):
    def read_polars(self, request: TableReadRequest) -> PolarsReadResult:
        result = super().read_polars(request)
        return PolarsReadResult(result.frame.reverse(), result.receipt)


def test_reference_reader_passes_arrow_polars_and_receipt_conformance() -> None:
    request = TableReadRequest(TableURI("file:///fixture.csv"))

    assert_read_connector_conformance(ReferenceReader(), request)


def test_conformance_rejects_decimal_scale_changes() -> None:
    request = TableReadRequest(TableURI("file:///fixture.csv"))

    with pytest.raises(AssertionError, match="schema|Decimal|dtype"):
        assert_read_connector_conformance(BrokenReader(), request)


def test_conformance_rejects_receipt_identity_changes() -> None:
    request = TableReadRequest(TableURI("file:///fixture.csv"))

    with pytest.raises(AssertionError, match="operation"):
        assert_read_connector_conformance(BrokenReceiptReader(), request)


def test_conformance_rejects_row_order_changes() -> None:
    request = TableReadRequest(TableURI("file:///fixture.csv"))

    with pytest.raises(AssertionError, match="values or order"):
        assert_read_connector_conformance(BrokenOrderReader(), request)


def test_receipt_conformance_rejects_unsafe_values() -> None:
    receipt = replace(_receipt(), safe_uri=TableURI("file:///fixture.csv"))

    assert_receipt_safe(receipt)


def test_direct_parity_assertion_accepts_matching_order_and_nulls() -> None:
    reader = ReferenceReader()
    result = reader.read_arrow(TableReadRequest(TableURI("file:///fixture.csv")))

    assert_arrow_polars_equal(result.table, reader.read_polars(TableReadRequest(result.receipt.safe_uri)).frame)
