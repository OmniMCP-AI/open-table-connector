from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook

from open_table_connector.contract import InspectRequest, ResourceLimits, TableMode, TableURI
from open_table_connector.contract.errors import ConnectorError, ConnectorErrorCode
from open_table_connector.conformance import run_read_suite
from open_table_connector.local_files.excel_connector import (
    ExcelConnector,
    ExcelReadOptions,
    ExcelTableReadRequest,
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


def test_excel_connector_identity_and_manifest_pin_the_public_scheme() -> None:
    connector = ExcelConnector()

    assert connector.identity.connector_id == "excel"
    assert connector.manifest.connector == connector.identity
    assert connector.manifest.uri_schemes == ("excel",)
    assert connector.manifest.modes == (TableMode.SHEET,)
    assert [capability.capability_id for capability in connector.manifest.capabilities] == [
        "uri.resolve",
        "table.inspect",
        "table.read.arrow",
        "table.read.polars",
    ]


def test_excel_connector_reads_selected_sheet_and_uses_concrete_receipts(tmp_path: Path) -> None:
    source = tmp_path / "book.xlsx"
    _workbook(source)
    request = ExcelTableReadRequest(
        TableURI(f"excel://{source}#sheet=refunds"),
        options=ExcelReadOptions(header_row=1),
    )

    result = ExcelConnector().read_polars(request)

    assert result.frame.to_dicts() == [{"refund_id": "r1", "amount": "1.00"}]
    assert result.receipt.connector.connector_id == "excel"
    assert result.receipt.coordinate_convention.sheet == "refunds"
    assert result.receipt.coordinate_convention.header_rows == 1
    assert result.receipt.coordinate_convention.first_data_row == 2


def test_excel_connector_honors_row_limit_from_resource_limits(tmp_path: Path) -> None:
    source = tmp_path / "book.xlsx"
    _workbook(source)
    request = ExcelTableReadRequest(
        TableURI(f"excel://{source}"),
        resource_limits=ResourceLimits(max_rows=1),
    )

    result = ExcelConnector().read_arrow(request)

    assert result.table.to_pylist() == [{"id": "1", "amount": "2.50"}]


def test_excel_connector_inspection_reports_available_worksheets(tmp_path: Path) -> None:
    source = tmp_path / "book.xlsx"
    _workbook(source)

    inspection = ExcelConnector().inspect(InspectRequest(TableURI(f"excel://{source}")))

    assert inspection.mode is TableMode.SHEET
    assert inspection.columns == ("id", "amount")
    assert inspection.row_count == 1
    assert inspection.coordinate_convention.sheet == "orders"
    assert inspection.facts["worksheets"] == ["orders", "refunds"]
    assert inspection.facts["formula_text_captured"] is False
    assert inspection.facts["formula_calculated"] is False


def test_excel_connector_rejects_unsupported_hosts(tmp_path: Path) -> None:
    source = tmp_path / "book.xlsx"
    _workbook(source)

    with pytest.raises(ConnectorError) as raised:
        ExcelConnector().resolve(
            TableURI(f"excel://example.test{source}"),
            ExcelTableReadRequest(TableURI(f"excel://{source}")).resolve_context,
        )

    assert raised.value.code is ConnectorErrorCode.INVALID_URI


def test_excel_connector_rejects_mismatched_csv_payload(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    source.write_text("id\n1\n", encoding="utf-8")

    with pytest.raises(ConnectorError) as raised:
        ExcelConnector().read_arrow(ExcelTableReadRequest(TableURI(f"excel://{source}")))

    assert raised.value.code is ConnectorErrorCode.INVALID_URI


def test_excel_connector_passes_shared_read_conformance(tmp_path: Path) -> None:
    source = tmp_path / "book.xlsx"
    _workbook(source)

    run_read_suite(ExcelConnector(), [ExcelTableReadRequest(TableURI(f"excel://{source}"))])
