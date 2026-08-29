"""Legacy OLE XLS to Arrow conversion."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow as pa

from open_table_connector.contract import ConnectorError, ConnectorErrorCode, ResourceLimits


def _header(value: Any, index: int) -> str:
    text = str(value).strip()
    return text or f"column_{index + 1}"


def _unique_headers(values: list[Any]) -> list[str]:
    seen: dict[str, int] = {}
    result: list[str] = []
    for index, value in enumerate(values):
        base = _header(value, index)
        count = seen.get(base, 0)
        result.append(base if count == 0 else f"{base}_duplicated_{count - 1}")
        seen[base] = count + 1
    return result


def _arrow_table(headers: list[str], records: list[dict[str, Any]]) -> pa.Table:
    arrays = []
    for header in headers:
        values = [record.get(header) for record in records]
        try:
            arrays.append(pa.array(values))
        except (pa.ArrowInvalid, pa.ArrowTypeError):
            arrays.append(
                pa.array(
                    [
                        None
                        if value is None
                        else value.isoformat()
                        if hasattr(value, "isoformat")
                        else str(value)
                        for value in values
                    ],
                    type=pa.large_string(),
                )
            )
    return pa.Table.from_arrays(arrays, names=headers)


def read_legacy_excel_arrow(
    path: Path,
    *,
    sheet: str | None,
    header_row: int,
    limits: ResourceLimits,
) -> tuple[pa.Table, str, tuple[str, ...]]:
    try:
        import xlrd

        workbook = xlrd.open_workbook(filename=str(path), on_demand=True)
        names = tuple(str(name) for name in workbook.sheet_names())
        worksheet = workbook.sheet_by_name(sheet) if sheet else workbook.sheet_by_index(0)
    except Exception as exc:
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "legacy Excel file could not be opened",
            {"path": str(path), "reason": str(exc)},
        ) from None
    if header_row > worksheet.nrows:
        return pa.table({}), worksheet.name, names
    headers = _unique_headers(worksheet.row_values(header_row - 1))
    records: list[dict[str, Any]] = []
    final_row = worksheet.nrows
    if limits.max_rows is not None:
        final_row = min(final_row, header_row + limits.max_rows)
    for row_index in range(header_row, final_row):
        values: list[Any] = []
        for cell in worksheet.row(row_index):
            value = cell.value
            if cell.ctype == xlrd.XL_CELL_EMPTY:
                value = None
            elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                value = bool(value)
            elif cell.ctype == xlrd.XL_CELL_DATE:
                value = xlrd.xldate_as_datetime(value, workbook.datemode)
                if isinstance(value, datetime) and value.time().isoformat() == "00:00:00":
                    value = value.date()
            values.append(value)
        values.extend([None] * (len(headers) - len(values)))
        records.append(dict(zip(headers, values, strict=True)))
    try:
        return _arrow_table(headers, records), worksheet.name, names
    except (pa.ArrowInvalid, pa.ArrowTypeError) as exc:
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "legacy Excel rows do not form a consistent table",
            {"path": str(path), "reason": str(exc)},
        ) from None


__all__ = ["read_legacy_excel_arrow"]
