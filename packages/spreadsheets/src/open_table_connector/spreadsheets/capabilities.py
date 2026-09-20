"""Capability identities for the unified spreadsheet extension."""

from open_table_connector.contract import CapabilityIdentity

SPREADSHEET_WORKBOOK_INSPECT = CapabilityIdentity("spreadsheet.workbook.inspect", "1.0")
SPREADSHEET_WORKSHEET_LIST = CapabilityIdentity("spreadsheet.worksheet.list", "1.0")
SPREADSHEET_RANGE_READ = CapabilityIdentity("spreadsheet.range.read", "1.0")
SPREADSHEET_RANGE_WRITE = CapabilityIdentity("spreadsheet.range.write", "1.0")
SPREADSHEET_RANGE_STYLE = CapabilityIdentity("spreadsheet.range.style", "1.0")
SPREADSHEET_RANGE_FORMAT = CapabilityIdentity("spreadsheet.range.format", "1.0")
SPREADSHEET_IMAGE_INSERT = CapabilityIdentity("spreadsheet.image.insert", "1.0")
SPREADSHEET_WORKBOOK_WRITE = CapabilityIdentity("spreadsheet.workbook.write", "1.0")
SPREADSHEET_WORKBOOK_VERIFY = CapabilityIdentity("spreadsheet.workbook.verify", "1.0")
SPREADSHEET_RANGE_SORT = CapabilityIdentity("spreadsheet.range.sort", "1.0")
SPREADSHEET_FORMULA_SET_RANGE = CapabilityIdentity("spreadsheet.formula.set_range", "1.0")
SPREADSHEET_RANGE_STYLE_READ = CapabilityIdentity("spreadsheet.range.style.read", "1.0")
SPREADSHEET_WORKSHEET_CONFIG_READ = CapabilityIdentity("spreadsheet.worksheet.config.read", "1.0")
SPREADSHEET_RANGE_ALIGNMENT_READ = CapabilityIdentity("spreadsheet.range.alignment.read", "1.0")
SPREADSHEET_RANGE_ALIGNMENT_WRITE = CapabilityIdentity("spreadsheet.range.alignment.write", "1.0")
SPREADSHEET_RANGE_BORDER_READ = CapabilityIdentity("spreadsheet.range.border.read", "1.0")
SPREADSHEET_RANGE_BORDER_WRITE = CapabilityIdentity("spreadsheet.range.border.write", "1.0")
SPREADSHEET_RANGE_TEXT_LAYOUT_READ = CapabilityIdentity("spreadsheet.range.text_layout.read", "1.0")
SPREADSHEET_RANGE_TEXT_LAYOUT_WRITE = CapabilityIdentity("spreadsheet.range.text_layout.write", "1.0")

ALL_CAPABILITIES = (
    SPREADSHEET_WORKBOOK_INSPECT,
    SPREADSHEET_WORKSHEET_LIST,
    SPREADSHEET_WORKBOOK_WRITE,
    SPREADSHEET_WORKBOOK_VERIFY,
    SPREADSHEET_RANGE_READ,
    SPREADSHEET_RANGE_WRITE,
    SPREADSHEET_RANGE_STYLE,
    SPREADSHEET_RANGE_FORMAT,
    SPREADSHEET_IMAGE_INSERT,
    SPREADSHEET_RANGE_SORT,
    SPREADSHEET_FORMULA_SET_RANGE,
    SPREADSHEET_RANGE_STYLE_READ,
    SPREADSHEET_WORKSHEET_CONFIG_READ,
    SPREADSHEET_RANGE_ALIGNMENT_READ,
    SPREADSHEET_RANGE_ALIGNMENT_WRITE,
    SPREADSHEET_RANGE_BORDER_READ,
    SPREADSHEET_RANGE_BORDER_WRITE,
    SPREADSHEET_RANGE_TEXT_LAYOUT_READ,
    SPREADSHEET_RANGE_TEXT_LAYOUT_WRITE,
)

__all__ = [
    "ALL_CAPABILITIES",
    "SPREADSHEET_IMAGE_INSERT",
    "SPREADSHEET_RANGE_READ",
    "SPREADSHEET_RANGE_FORMAT",
    "SPREADSHEET_RANGE_STYLE",
    "SPREADSHEET_RANGE_WRITE",
    "SPREADSHEET_RANGE_SORT",
    "SPREADSHEET_FORMULA_SET_RANGE",
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
