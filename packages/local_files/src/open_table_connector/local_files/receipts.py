"""Receipt construction for local-files physical reads."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import pyarrow as pa

from open_table_connector.contract import (
    BaseConvention,
    CapabilityIdentity,
    NeutralReceipt,
    SheetConvention,
    TableMode,
    TableURI,
)
from open_table_connector.contract.fingerprints import (
    arrow_content_fingerprint,
    arrow_schema_fingerprint,
    operation_identity,
)

from .identity import CONNECTOR_IDENTITY, TABLE_READ_ARROW_CAPABILITY


def source_revision(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def make_receipt(
    table: pa.Table,
    *,
    path: Path,
    uri: TableURI,
    parameters: Mapping[str, Any],
    coordinate_convention=None,
    capability: CapabilityIdentity,
    connector=CONNECTOR_IDENTITY,
    read_capability: CapabilityIdentity = TABLE_READ_ARROW_CAPABILITY,
    sheet: str = "data",
    header_row: int = 1,
    mode: TableMode = TableMode.SHEET,
) -> NeutralReceipt:
    source = source_revision(path)
    schema = arrow_schema_fingerprint(table.schema)
    content = arrow_content_fingerprint(table)
    # The operation identifies the physical read, not the materialized view
    # (Arrow and Polars are two interfaces over the same operation).
    operation = operation_identity(
        connector=connector,
        capability=read_capability,
        uri=uri,
        source_revision=source,
        schema_fingerprint=schema,
        content_fingerprint=content,
        parameters=parameters,
    )
    if coordinate_convention is not None:
        convention = coordinate_convention
    elif mode is TableMode.BASE:
        convention = BaseConvention(ordinal_snapshot_id=source)
    else:
        convention = SheetConvention(
            sheet=sheet,
            header_rows=header_row,
            first_data_row=header_row + 1,
        )
    return NeutralReceipt(
        connector=connector,
        capability=capability,
        operation_id=operation,
        safe_uri=uri,
        mode=mode,
        source_revision=source,
        schema_fingerprint=schema,
        content_fingerprint=content,
        coordinate_convention=convention,
        row_count=table.num_rows,
        batch_count=1,
        vendor_receipt_ref=None,
    )


def options_identity(options: Any, *, sheet: str | None) -> dict[str, Any]:
    payload = {
        "separator": options.separator,
        "encoding": options.encoding,
        "header_row": options.header_row,
        "sheet": sheet,
    }
    return json.loads(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def normalize_parameters(parameters: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(dict(parameters), ensure_ascii=False, sort_keys=True))
