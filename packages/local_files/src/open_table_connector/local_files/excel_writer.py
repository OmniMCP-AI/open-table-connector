"""Neutral Arrow-to-Excel writer for local conversion targets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow as pa

from open_table_connector.contract import ConnectorError, ConnectorErrorCode


def write_excel(table: pa.Table, path: Path, sheet: str | None = None) -> None:
    try:
        from openpyxl import Workbook
    except ImportError:
        raise ConnectorError(
            ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
            "Excel writing requires openpyxl",
            {},
        ) from None

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = sheet or "Sheet1"
    worksheet.append(list(table.column_names))
    for row in table.to_pylist():
        worksheet.append([_cell_value(row.get(name)) for name in table.column_names])
    try:
        workbook.save(path)
    except OSError as exc:
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "Excel output could not be written",
            {"path": str(path), "reason": exc.strerror or str(exc)},
        ) from None


def _cell_value(value: Any) -> Any:
    if isinstance(value, pa.Scalar):
        return _cell_value(value.as_py())
    if isinstance(value, (list, dict)):
        return str(value)
    return value


__all__ = ["write_excel"]
