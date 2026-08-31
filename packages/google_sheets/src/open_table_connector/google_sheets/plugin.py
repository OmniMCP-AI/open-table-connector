"""Provider-neutral registration metadata for Google Sheets."""

from __future__ import annotations

from .cli_adapter import google_sheets_cli_plugin

provider_plugin = google_sheets_cli_plugin


__all__ = ["provider_plugin"]
