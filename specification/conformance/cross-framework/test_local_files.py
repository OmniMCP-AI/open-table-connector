from __future__ import annotations

from pathlib import Path

import openpyxl

from open_table_connector.contract import TableURI
from open_table_connector.local_files import LocalFilesConnector, LocalReadOptions, LocalTableReadRequest


ROOT = Path(__file__).parent


def test_shared_csv_physical_facts_are_stable_across_arrow_and_polars() -> None:
    source = ROOT / "decimal-null-order.csv"
    connector = LocalFilesConnector()
    request = LocalTableReadRequest(TableURI(source.as_uri()))
    arrow = connector.read_arrow(request)
    polars = connector.read_polars(request)

    assert arrow.table.schema == polars.frame.to_arrow().schema
    assert arrow.table.to_pylist() == polars.frame.to_arrow().to_pylist()
    assert arrow.receipt.operation_id == polars.receipt.operation_id
    assert arrow.receipt.schema_fingerprint == polars.receipt.schema_fingerprint
    assert arrow.receipt.content_fingerprint == polars.receipt.content_fingerprint
    assert arrow.receipt.coordinate_convention.mode == "sheet"


def test_shared_excel_case_preserves_sheet_coordinates(tmp_path: Path) -> None:
    source = tmp_path / "multi-sheet.xlsx"
    workbook = openpyxl.Workbook()
    workbook.active.title = "orders"
    workbook.active.append(["id", "amount"])
    workbook.active.append([1, 2.5])
    returns = workbook.create_sheet("returns")
    returns.append(["id", "amount"])
    returns.append([2, None])
    workbook.save(source)

    connector = LocalFilesConnector()
    orders = connector.read_polars(
        LocalTableReadRequest(TableURI(source.as_uri()), options=LocalReadOptions(sheet="orders"))
    )
    returns_result = connector.read_polars(
        LocalTableReadRequest(TableURI(source.as_uri()), options=LocalReadOptions(sheet="returns"))
    )

    assert orders.receipt.coordinate_convention.sheet == "orders"
    assert returns_result.receipt.coordinate_convention.sheet == "returns"
    assert orders.frame.to_dicts() == [{"id": "1", "amount": "2.5"}]
    assert returns_result.frame.to_dicts() == [{"id": "2", "amount": None}]
