from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook

from open_table_connector.contract import ResolveContext, TableURI
from open_table_connector.contract.errors import ConnectorError, ConnectorErrorCode
from open_table_connector.local_files.reader import (
    LocalFilesConnector,
    LocalReadOptions,
    LocalTableReadRequest,
)
from open_table_connector.local_files.resolver import LocalFormat


@pytest.mark.parametrize(
    ("filename", "payload", "expected_format"),
    (
        ("orders.csv", "id\n1\n", LocalFormat.CSV),
        ("orders.md", "| id |\n| --- |\n| 1 |\n", LocalFormat.MARKDOWN),
    ),
)
def test_local_files_facade_autodetects_supported_text_formats(
    tmp_path: Path, filename: str, payload: str, expected_format: LocalFormat
) -> None:
    source = tmp_path / filename
    source.write_text(payload, encoding="utf-8")
    connector = LocalFilesConnector()

    resolved = connector.resolve(TableURI(source.as_uri()), ResolveContext())
    result = connector.read_arrow(LocalTableReadRequest(TableURI(source.as_uri())))

    assert resolved.resource.format is expected_format
    assert result.table.num_rows == 1
    assert result.receipt.connector.connector_id == "local_files"


def test_local_files_facade_reads_excel_and_preserves_compatibility_receipts(
    tmp_path: Path,
) -> None:
    source = tmp_path / "orders.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "orders"
    worksheet.append(["id"])
    worksheet.append(["1"])
    workbook.save(source)

    result = LocalFilesConnector().read_arrow(LocalTableReadRequest(TableURI(source.as_uri())))

    assert result.table.column_names == ["id"]
    assert result.receipt.connector.connector_id == "local_files"


@pytest.mark.parametrize(("filename", "payload"), (("orders.csv", "id\n1\n"), ("orders.md", "| id |\n| --- |\n| 1 |\n")))
def test_local_files_facade_rejects_sheet_option_for_non_excel_formats(
    tmp_path: Path, filename: str, payload: str
) -> None:
    source = tmp_path / filename
    source.write_text(payload, encoding="utf-8")

    with pytest.raises(ConnectorError) as raised:
        LocalFilesConnector().read_arrow(
            LocalTableReadRequest(
                TableURI(source.as_uri()),
                options=LocalReadOptions(sheet="orders"),
            )
        )

    assert raised.value.code is ConnectorErrorCode.INVALID_URI


def test_local_files_facade_inspection_honors_csv_read_options(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    source.write_bytes("name;amount\ncafé;1\n".encode("latin-1"))
    request = LocalTableReadRequest(
        TableURI(source.as_uri()),
        options=LocalReadOptions(separator=";", encoding="latin-1"),
    )

    inspection = LocalFilesConnector().inspect(request)

    assert inspection.columns == ("name", "amount")
    assert inspection.row_count == 1


def test_local_files_facade_inspection_honors_excel_read_options(tmp_path: Path) -> None:
    source = tmp_path / "orders.xlsx"
    workbook = Workbook()
    orders = workbook.active
    orders.title = "orders"
    orders.append(["ignored metadata"])
    orders.append(["id", "amount"])
    orders.append(["1", "2.50"])
    refunds = workbook.create_sheet("refunds")
    refunds.append(["ignored metadata"])
    refunds.append(["refund_id", "amount"])
    refunds.append(["r1", "1.00"])
    workbook.save(source)
    request = LocalTableReadRequest(
        TableURI(source.as_uri()),
        options=LocalReadOptions(sheet="refunds", header_row=2),
    )

    inspection = LocalFilesConnector().inspect(request)

    assert inspection.columns == ("refund_id", "amount")
    assert inspection.coordinate_convention.sheet == "refunds"
    assert inspection.coordinate_convention.header_rows == 2
