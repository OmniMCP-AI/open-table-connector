from __future__ import annotations

import io
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import openpyxl

from open_table_connector.local_files.spreadsheet_observe import observe_xlsx
from open_table_connector.local_files.spreadsheet_workbook import LocalSpreadsheetProvider
from open_table_connector.spreadsheets import SpreadsheetTarget


def _bytes(*, explicit_false: bool = False) -> bytes:
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Report"
    sheet["A1"] = 60
    sheet["A1"].number_format = '[$€-407] #,##0.00'
    sheet["B1"].font = openpyxl.styles.Font(bold=True)
    if explicit_false:
        sheet["B1"].alignment = openpyxl.styles.Alignment(wrap_text=False, shrink_to_fit=False)
    sheet.row_dimensions[1].height = 24
    sheet.column_dimensions["A"].width = 18
    sheet.sheet_view.showGridLines = False
    output = io.BytesIO()
    book.save(output)
    data = output.getvalue()
    if explicit_false:
        rewritten = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(rewritten, "w") as target:
            for info in source.infolist():
                payload = source.read(info)
                if info.filename == "xl/styles.xml":
                    root = ET.fromstring(payload)
                    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
                    xfs = root.find(ns + "cellXfs")
                    assert xfs is not None
                    ET.SubElement(xfs[2], ns + "alignment", {"wrapText": "0"})
                    payload = ET.tostring(root, encoding="utf-8", xml_declaration=True)
                target.writestr(info, payload)
        data = rewritten.getvalue()
    return data


def test_observe_xlsx_returns_complete_style_evidence():
    result = observe_xlsx(
        data=_bytes(),
        target={"provider": "excel", "resource": "book.xlsx", "worksheet_id": "1"},
        selector={"operation": "range.style.read", "address": "A1:B1", "fields": ["bold", "number_format", "wrap_text"]},
    )
    assert result["physical_hash"].startswith("sha256:")
    assert len(result["physical"]["cells"]) == 2
    assert result["physical"]["cells"][0]["fields"]["number_format"]["effective"]["code"] == '[$€-407] #,##0.00'


def test_stored_false_differs_from_inherited_false():
    target = {"provider": "excel", "resource": "book.xlsx", "worksheet_id": "1"}
    selector = {"operation": "range.style.read", "address": "B1", "fields": ["wrap_text"]}
    first = observe_xlsx(data=_bytes(explicit_false=True), target=target, selector=selector)
    second = observe_xlsx(data=_bytes(explicit_false=False), target=target, selector=selector)
    assert first["physical_hash"] != second["physical_hash"]


def test_observe_xlsx_reads_dimensions_and_view():
    result = observe_xlsx(
        data=_bytes(),
        target={"provider": "excel", "resource": "book.xlsx", "worksheet_id": "1"},
        selector={"operation": "worksheet.config.read", "rows": [1], "columns": ["A"]},
    )
    assert result["physical"]["rows"]["1"]["height"] == 24
    assert result["physical"]["columns"]["A"]["width"] == 18
    assert result["physical"]["view"]["show_gridlines"] is False


def test_provider_routes_layout_reads_to_independent_observer(tmp_path: Path):
    path = tmp_path / "book.xlsx"
    path.write_bytes(_bytes())
    provider = LocalSpreadsheetProvider()
    binding = provider.bind(SpreadsheetTarget(path.as_uri()))
    result = provider.observe(binding, {"operation": "range.style.read", "target_key": "Report", "address": "A1"})
    assert result["value"]["kind"] == "spreadsheet.range.style.observation/1.0"
