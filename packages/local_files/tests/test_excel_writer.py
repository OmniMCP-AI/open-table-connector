from openpyxl import load_workbook
import pyarrow as pa
import pytest

from open_table_connector.contract import ConnectorError, ConnectorErrorCode
from open_table_connector.local_files.excel_writer import write_excel


def test_excel_writer_writes_headers_and_rows_to_named_sheet(tmp_path) -> None:
    destination = tmp_path / "orders.xlsx"
    table = pa.table({"id": ["1", "2"], "amount": ["10", None]})

    write_excel(table, destination, sheet="Orders")

    workbook = load_workbook(destination, read_only=True, data_only=True)
    try:
        assert workbook.sheetnames == ["Orders"]
        assert list(workbook["Orders"].values) == [
            ("id", "amount"),
            ("1", "10"),
            ("2", None),
        ]
    finally:
        workbook.close()


def test_excel_writer_maps_file_errors_to_connector_error(tmp_path) -> None:
    destination = tmp_path / "missing" / "orders.xlsx"

    with pytest.raises(ConnectorError) as error:
        write_excel(pa.table({"id": ["1"]}), destination)

    assert error.value.code is ConnectorErrorCode.EXECUTION_FAILED
    assert error.value.safe_details["path"] == str(destination)
