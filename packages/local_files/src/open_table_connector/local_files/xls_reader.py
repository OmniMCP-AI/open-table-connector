"""Legacy XLS-to-Arrow materialization through the governed xlrd dependency."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa

from open_table_connector.contract import ConnectorError, ConnectorErrorCode, ResourceLimits

from .csv_reader import _headers


def _cell(value):
    return None if value is None else value if isinstance(value, str) else str(value)


def read_xls_arrow(
    path: Path,
    *,
    sheet: str | None,
    header_row: int,
    limits: ResourceLimits,
) -> tuple[pa.Table, str, tuple[str, ...]]:
    try:
        import xlrd
    except ImportError:
        raise ConnectorError(
            ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
            "XLS reading requires xlrd",
            {},
        ) from None
    try:
        workbook = xlrd.open_workbook(file_contents=path.read_bytes(), on_demand=True)
        worksheet = workbook.sheet_by_name(sheet) if sheet is not None else workbook.sheet_by_index(0)
        if header_row < 1 or worksheet.nrows < header_row:
            return pa.table({}), worksheet.name, tuple(workbook.sheet_names())
        names = _headers([str(value) for value in worksheet.row_values(header_row - 1)])
        rows: list[list[str | None]] = []
        for index in range(header_row, worksheet.nrows):
            values = worksheet.row_values(index)
            normalized = [_cell(value) for value in values[: len(names)]]
            normalized.extend([None] * (len(names) - len(normalized)))
            if not any(value is not None for value in normalized):
                continue
            rows.append(normalized)
            if limits.max_rows is not None and len(rows) >= limits.max_rows:
                break
        columns = [pa.array([row[index] for row in rows], type=pa.large_string()) for index in range(len(names))]
        return pa.Table.from_arrays(columns, names=names), worksheet.name, tuple(workbook.sheet_names())
    except ConnectorError:
        raise
    except Exception as exc:
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "XLS worksheet could not be read",
            {"path": str(path), "reason": str(exc)},
        ) from None


__all__ = ["read_xls_arrow"]
