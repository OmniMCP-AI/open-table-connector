"""Assertions shared by Connector implementations and framework suites."""

from __future__ import annotations

import json
from typing import Any

import polars as pl
import pyarrow as pa

from open_connectors.contract import (
    ArrowTableReader,
    NeutralReceipt,
    PolarsTableReader,
    TableReadRequest,
)


def _schema_signature(schema: pa.Schema) -> tuple[tuple[str, str, bool], ...]:
    def semantic_type(field: pa.Field) -> str:
        # Polars' Arrow export uses large_string for an ordinary UTF-8 string.
        # Both are the same logical text type for this contract; Decimal
        # precision/scale and every other type remain exact.
        if pa.types.is_string(field.type) or pa.types.is_large_string(field.type):
            return "utf8"
        return str(field.type)

    return tuple((field.name, semantic_type(field), field.nullable) for field in schema)


def _rows(table: pa.Table) -> list[dict[str, Any]]:
    return table.to_pylist()


def assert_arrow_polars_equal(table: pa.Table, frame: pl.DataFrame) -> None:
    """Compare schema and ordered values without relying on debug strings."""

    converted = frame.to_arrow()
    assert _schema_signature(table.schema) == _schema_signature(converted.schema), (
        f"schema mismatch: {_schema_signature(table.schema)!r} != "
        f"{_schema_signature(converted.schema)!r}"
    )
    assert _rows(table) == _rows(converted), "Arrow/Polars row values or order differ"


def assert_receipt_safe(receipt: NeutralReceipt) -> None:
    payload = receipt.to_wire()
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    forbidden = ("access_token", "api_key", "password", "secret", "token")
    assert not any(term in encoded.casefold() for term in forbidden)
    assert NeutralReceipt.from_wire(payload) == receipt


def assert_read_connector_conformance(
    connector: ArrowTableReader & PolarsTableReader,
    request: TableReadRequest,
) -> None:
    arrow_result = connector.read_arrow(request)
    polars_result = connector.read_polars(request)
    assert_arrow_polars_equal(arrow_result.table, polars_result.frame)
    assert arrow_result.receipt.operation_id == polars_result.receipt.operation_id, "operation identity differs"
    assert arrow_result.receipt.content_fingerprint == polars_result.receipt.content_fingerprint, "content fingerprint differs"
    assert arrow_result.receipt.schema_fingerprint == polars_result.receipt.schema_fingerprint, "schema fingerprint differs"
    assert arrow_result.receipt.safe_uri == polars_result.receipt.safe_uri, "safe URI differs"
    assert arrow_result.receipt.mode == polars_result.receipt.mode, "table mode differs"
    assert arrow_result.receipt.coordinate_convention == polars_result.receipt.coordinate_convention, "coordinate convention differs"
    assert_receipt_safe(arrow_result.receipt)
    assert_receipt_safe(polars_result.receipt)
