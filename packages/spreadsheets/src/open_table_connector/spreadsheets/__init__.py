"""Provider-neutral unified spreadsheet contracts."""

from ._limits import ArtifactLimits
from ._operations import Change
from ._protocols import SpreadsheetProvider
from .capabilities import (
    ALL_CAPABILITIES,
    SPREADSHEET_IMAGE_INSERT,
    SPREADSHEET_RANGE_FORMAT,
    SPREADSHEET_RANGE_READ,
    SPREADSHEET_RANGE_SORT,
    SPREADSHEET_RANGE_STYLE,
    SPREADSHEET_RANGE_WRITE,
    SPREADSHEET_WORKBOOK_INSPECT,
    SPREADSHEET_WORKBOOK_VERIFY,
    SPREADSHEET_WORKBOOK_WRITE,
    SPREADSHEET_WORKSHEET_LIST,
)
from .model import CellFormat, CellStyle, ImageSpec, RangeRef, SpreadsheetTarget, WorksheetRef

__all__ = [
    "ArtifactLimits",
    "CellFormat",
    "CellStyle",
    "Change",
    "ImageSpec",
    "RangeRef",
    "SpreadsheetTarget",
    "SpreadsheetProvider",
    "WorksheetRef",
    "ALL_CAPABILITIES",
    "SPREADSHEET_IMAGE_INSERT",
    "SPREADSHEET_RANGE_READ",
    "SPREADSHEET_RANGE_FORMAT",
    "SPREADSHEET_RANGE_STYLE",
    "SPREADSHEET_RANGE_SORT",
    "SPREADSHEET_RANGE_WRITE",
    "SPREADSHEET_WORKBOOK_INSPECT",
    "SPREADSHEET_WORKBOOK_VERIFY",
    "SPREADSHEET_WORKBOOK_WRITE",
    "SPREADSHEET_WORKSHEET_LIST",
]
