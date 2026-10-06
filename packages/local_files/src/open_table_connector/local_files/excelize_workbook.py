"""Explicit rich-profile alias for the existing Excelize-backed provider."""

from .spreadsheet_workbook import LocalSpreadsheetProvider


class ExcelizeSpreadsheetProvider(LocalSpreadsheetProvider):
    """Use the existing provider implementation for rich XLSX sessions."""


__all__ = ["ExcelizeSpreadsheetProvider"]
