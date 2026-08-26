from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook

from open_connectors.contract import InspectRequest, TableURI
from open_connectors.contract import ConnectorError, ConnectorErrorCode
from open_connectors.local_files.reader import (
    LocalFilesConnector,
    LocalReadOptions,
    LocalTableReadRequest,
)


def _workbook(path: Path) -> None:
    workbook = Workbook()
    workbook.active.title = "orders"
    workbook.active.append(["id", "amount"])
    workbook.active.append(["1", "2.50"])
    refunds = workbook.create_sheet("refunds")
    refunds.append(["refund_id", "amount"])
    refunds.append(["r1", "1.00"])
    workbook.save(path)


def test_excel_read_selects_sheet_and_reports_formula_limits(tmp_path: Path) -> None:
    source = tmp_path / "book.xlsx"
    _workbook(source)
    request = LocalTableReadRequest(
        TableURI(f"{source.as_uri()}#sheet=refunds"),
        options=LocalReadOptions(header_row=1),
    )

    result = LocalFilesConnector().read_polars(request)

    assert result.frame.to_dicts() == [{"refund_id": "r1", "amount": "1.00"}]
    assert result.receipt.coordinate_convention.sheet == "refunds"
    assert result.receipt.to_wire()["vendor_receipt_ref"] is None


def test_excel_inspection_lists_all_worksheets_and_formula_facts(tmp_path: Path) -> None:
    source = tmp_path / "book.xlsx"
    _workbook(source)

    inspection = LocalFilesConnector().inspect(InspectRequest(TableURI(source.as_uri())))

    assert inspection.columns == ("id", "amount")
    assert inspection.facts["worksheets"] == ["orders", "refunds"]
    assert inspection.facts["formula_text_captured"] is False
    assert inspection.facts["formula_calculated"] is False


def test_excel_default_active_sheet_and_missing_sheet_are_explicit(tmp_path: Path) -> None:
    source = tmp_path / "book.xlsx"
    _workbook(source)

    result = LocalFilesConnector().read_polars(LocalTableReadRequest(TableURI(source.as_uri())))
    assert result.receipt.coordinate_convention.sheet == "orders"

    with pytest.raises(ConnectorError) as raised:
        LocalFilesConnector().read_polars(
            LocalTableReadRequest(TableURI(f"{source.as_uri()}#sheet=missing"))
        )
    assert raised.value.code is ConnectorErrorCode.INVALID_URI
