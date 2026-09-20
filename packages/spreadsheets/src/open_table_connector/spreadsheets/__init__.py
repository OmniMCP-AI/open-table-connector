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
    SPREADSHEET_RANGE_STYLE_READ,
    SPREADSHEET_WORKSHEET_CONFIG_READ,
    SPREADSHEET_RANGE_ALIGNMENT_READ,
    SPREADSHEET_RANGE_ALIGNMENT_WRITE,
    SPREADSHEET_RANGE_BORDER_READ,
    SPREADSHEET_RANGE_BORDER_WRITE,
    SPREADSHEET_RANGE_TEXT_LAYOUT_READ,
    SPREADSHEET_RANGE_TEXT_LAYOUT_WRITE,
    SPREADSHEET_WORKBOOK_INSPECT,
    SPREADSHEET_WORKBOOK_VERIFY,
    SPREADSHEET_WORKBOOK_WRITE,
    SPREADSHEET_WORKSHEET_LIST,
)
from .model import CellFormat, CellStyle, ImageSpec, RangeRef, SpreadsheetTarget, WorksheetRef
from .formats import normalize_format
from ._layout import LayoutCapabilityError, normalize_config, normalize_style, prepare_layout, validate_descriptor

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
    "normalize_format",
    "LayoutCapabilityError",
    "normalize_config",
    "normalize_style",
    "prepare_layout",
    "validate_descriptor",
    "ALL_CAPABILITIES",
    "SPREADSHEET_IMAGE_INSERT",
    "SPREADSHEET_RANGE_READ",
    "SPREADSHEET_RANGE_FORMAT",
    "SPREADSHEET_RANGE_STYLE",
    "SPREADSHEET_RANGE_SORT",
    "SPREADSHEET_RANGE_WRITE",
    "SPREADSHEET_RANGE_STYLE_READ",
    "SPREADSHEET_WORKSHEET_CONFIG_READ",
    "SPREADSHEET_RANGE_ALIGNMENT_READ",
    "SPREADSHEET_RANGE_ALIGNMENT_WRITE",
    "SPREADSHEET_RANGE_BORDER_READ",
    "SPREADSHEET_RANGE_BORDER_WRITE",
    "SPREADSHEET_RANGE_TEXT_LAYOUT_READ",
    "SPREADSHEET_RANGE_TEXT_LAYOUT_WRITE",
    "SPREADSHEET_WORKBOOK_INSPECT",
    "SPREADSHEET_WORKBOOK_VERIFY",
    "SPREADSHEET_WORKBOOK_WRITE",
    "SPREADSHEET_WORKSHEET_LIST",
]
