from __future__ import annotations

from pathlib import Path

import pyarrow as pa

from open_connectors.contract import ResourceLimits, TableURI
from open_connectors.local_files.reader import (
    LocalFilesConnector,
    LocalReadOptions,
    LocalTableReadRequest,
)


def test_csv_read_exposes_arrow_and_polars_with_identical_values(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    source.write_text("id,amount,label\n1,2.50,中文\n2,,last\n", encoding="utf-8")
    request = LocalTableReadRequest(TableURI(source.as_uri()))

    connector = LocalFilesConnector()
    arrow_result = connector.read_arrow(request)
    polars_result = connector.read_polars(request)

    assert isinstance(arrow_result.table, pa.Table)
    assert polars_result.frame.columns == ["id", "amount", "label"]
    assert polars_result.frame.to_dicts() == [
        {"id": "1", "amount": "2.50", "label": "中文"},
        {"id": "2", "amount": None, "label": "last"},
    ]
    assert arrow_result.receipt.operation_id == polars_result.receipt.operation_id
    assert arrow_result.receipt.content_fingerprint == polars_result.receipt.content_fingerprint
    assert arrow_result.receipt.coordinate_convention.sheet == "data"


def test_csv_read_honors_connector_owned_delimiter_option(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    source.write_text("id;amount\n1;2.50\n", encoding="utf-8")
    request = LocalTableReadRequest(
        TableURI(source.as_uri()),
        options=LocalReadOptions(separator=";"),
    )

    frame = LocalFilesConnector().read_polars(request).frame

    assert frame.to_dicts() == [{"id": "1", "amount": "2.50"}]


def test_csv_read_applies_row_limit_and_stable_duplicate_header_names(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    source.write_text("id,id,id\n1,2,3\n4,5,6\n", encoding="utf-8")
    request = LocalTableReadRequest(
        TableURI(source.as_uri()),
        resource_limits=ResourceLimits(max_rows=1),
    )

    result = LocalFilesConnector().read_arrow(request)

    assert result.table.column_names == ["id", "id_duplicated_0", "id_duplicated_1"]
    assert result.table.to_pylist() == [{"id": "1", "id_duplicated_0": "2", "id_duplicated_1": "3"}]
