"""Framework-neutral Google Sheets values connector."""

from .cli_adapter import GoogleSheetsCliAdapter, google_sheets_cli_plugin
from .connector import (
    GOOGLE_SHEETS_MAX_RESPONSE_BYTES,
    GoogleSheetsConnector,
    GoogleSheetsReadOptions,
    GoogleSheetsTableReadRequest,
)

__all__ = [
    "GOOGLE_SHEETS_MAX_RESPONSE_BYTES",
    "GoogleSheetsConnector",
    "GoogleSheetsCliAdapter",
    "google_sheets_cli_plugin",
    "GoogleSheetsReadOptions",
    "GoogleSheetsTableReadRequest",
]
