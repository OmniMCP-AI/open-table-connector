"""Provider-neutral unified spreadsheet contracts."""

from .capabilities import (
    ALL_CAPABILITIES,
    SPREADSHEET_IMAGE_INSERT,
    SPREADSHEET_RANGE_READ,
    SPREADSHEET_RANGE_STYLE,
    SPREADSHEET_RANGE_WRITE,
    SPREADSHEET_WORKBOOK_INSPECT,
    SPREADSHEET_WORKSHEET_LIST,
)
from .model import CellFormat, CellStyle, ImageSpec, RangeRef, SpreadsheetTarget, WorksheetRef

__all__ = [
    "CellFormat",
    "CellStyle",
    "ImageSpec",
    "RangeRef",
    "SpreadsheetTarget",
    "WorksheetRef",
    "ALL_CAPABILITIES",
    "SPREADSHEET_IMAGE_INSERT",
    "SPREADSHEET_RANGE_READ",
    "SPREADSHEET_RANGE_STYLE",
    "SPREADSHEET_RANGE_WRITE",
    "SPREADSHEET_WORKBOOK_INSPECT",
    "SPREADSHEET_WORKSHEET_LIST",
]
