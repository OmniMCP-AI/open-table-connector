"""Capability identities for the unified spreadsheet extension."""

from open_table_connector.contract import CapabilityIdentity

SPREADSHEET_WORKBOOK_INSPECT = CapabilityIdentity("spreadsheet.workbook.inspect", "1.0")
SPREADSHEET_WORKSHEET_LIST = CapabilityIdentity("spreadsheet.worksheet.list", "1.0")
SPREADSHEET_RANGE_READ = CapabilityIdentity("spreadsheet.range.read", "1.0")
SPREADSHEET_RANGE_WRITE = CapabilityIdentity("spreadsheet.range.write", "1.0")
SPREADSHEET_RANGE_STYLE = CapabilityIdentity("spreadsheet.range.style", "1.0")
SPREADSHEET_IMAGE_INSERT = CapabilityIdentity("spreadsheet.image.insert", "1.0")

ALL_CAPABILITIES = (
    SPREADSHEET_WORKBOOK_INSPECT,
    SPREADSHEET_WORKSHEET_LIST,
    SPREADSHEET_RANGE_READ,
    SPREADSHEET_RANGE_WRITE,
    SPREADSHEET_RANGE_STYLE,
    SPREADSHEET_IMAGE_INSERT,
)

__all__ = [
    "ALL_CAPABILITIES",
    "SPREADSHEET_IMAGE_INSERT",
    "SPREADSHEET_RANGE_READ",
    "SPREADSHEET_RANGE_STYLE",
    "SPREADSHEET_RANGE_WRITE",
    "SPREADSHEET_WORKBOOK_INSPECT",
    "SPREADSHEET_WORKSHEET_LIST",
]
