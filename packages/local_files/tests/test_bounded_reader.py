from __future__ import annotations

import json

from open_table_connector.contract import (
    BoundedTableReadRequest,
    ResourceLimits,
    TableURI,
)
from open_table_connector.contract.bounded_reads import ReadExtent
from open_table_connector.local_files import CONNECTOR_IDENTITY, LocalBoundedReader


def test_csv_bounded_reader_returns_truthful_truncation_receipt(tmp_path) -> None:
    source = tmp_path / "rows.csv"
    source.write_text("id,name\n1,one\n2,two\n3,three\n", encoding="utf-8")

    result = LocalBoundedReader(connector=CONNECTOR_IDENTITY).read_arrow_bounded(
        BoundedTableReadRequest(
            TableURI(f"csv://{source}"),
            max_output_rows=2,
            resource_limits=ResourceLimits(max_bytes=source.stat().st_size),
        )
    )

    assert result.table.num_rows == 2
    assert result.receipt.extent is ReadExtent.TRUNCATED
    assert result.receipt.rows_emitted == 2
    assert result.receipt.to_wire()["operation_id"] == "bounded-read"


def test_jsonl_bounded_reader_uses_resource_row_limit(tmp_path) -> None:
    source = tmp_path / "rows.jsonl"
    source.write_text(
        "".join(json.dumps({"id": index}) + "\n" for index in range(3)),
        encoding="utf-8",
    )

    result = LocalBoundedReader(connector=CONNECTOR_IDENTITY).read_arrow_bounded(
        BoundedTableReadRequest(
            TableURI(f"jsonl://{source}"),
            max_output_rows=3,
            resource_limits=ResourceLimits(max_rows=1),
        )
    )

    assert result.table.num_rows == 1
    assert result.receipt.extent is ReadExtent.TRUNCATED
