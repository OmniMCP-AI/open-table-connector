"""Bounded CSV/JSONL reader for the explicit contract v2."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pyarrow as pa
from open_table_connector.contract import (
    BaseConvention,
    BoundedArrowTableReadResult,
    BoundedReadReceipt,
    BoundedTableReadRequest,
    ConnectorIdentity,
    ReadExtent,
    TableMode,
)
from open_table_connector.contract.fingerprints import (
    arrow_content_fingerprint,
    arrow_schema_fingerprint,
)


class LocalBoundedReader:
    def __init__(self, *, connector: ConnectorIdentity) -> None:
        self.connector = connector

    def read_arrow_bounded(self, request: BoundedTableReadRequest) -> BoundedArrowTableReadResult:
        parsed = urlsplit(request.uri.value)
        if parsed.netloc not in {"", "localhost"} or parsed.query:
            raise ValueError("bounded local reads require a hostless URI without a query")
        path = Path(unquote(parsed.path))
        if not path.is_absolute() or not path.is_file() or path.is_symlink():
            raise ValueError("bounded local reads require one regular absolute file")
        data = path.read_bytes()
        if len(data) > (request.resource_limits.max_bytes or len(data)):
            raise ValueError("bounded read exceeds max_bytes")
        if request.uri.scheme == "jsonl" or path.suffix.casefold() == ".jsonl":
            rows = [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]
        else:
            records = list(csv.reader(data.decode("utf-8").splitlines()))
            rows = (
                [dict(zip(records[0], row, strict=False)) for row in records[1:]]
                if records
                else []
            )
        row_limit = request.max_output_rows
        if request.resource_limits.max_rows is not None:
            row_limit = min(row_limit, request.resource_limits.max_rows)
        truncated = len(rows) > row_limit
        rows = rows[:row_limit]
        table = pa.Table.from_pylist(rows)
        receipt = BoundedReadReceipt(
            connector=self.connector,
            safe_uri=request.uri,
            mode=TableMode.BASE,
            source_snapshot_reference="sha256:" + hashlib.sha256(data).hexdigest(),
            schema_fingerprint=arrow_schema_fingerprint(table.schema),
            emitted_content_fingerprint=arrow_content_fingerprint(table),
            coordinate_convention=BaseConvention(ordinal_snapshot_id="bounded-source"),
            rows_emitted=table.num_rows,
            batches_emitted=1 if table.num_rows else 0,
            extent=ReadExtent.TRUNCATED if truncated else ReadExtent.COMPLETE,
        )
        return BoundedArrowTableReadResult(table, receipt)


__all__ = ["LocalBoundedReader"]
