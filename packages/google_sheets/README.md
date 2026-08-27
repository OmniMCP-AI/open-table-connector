# Google Sheets connector

Reads and writes Google Sheets values through the Google Sheets API v4. Supply
an OAuth access token and optionally an injected transport for testing.

Supported URIs are `gsheets://SPREADSHEET_ID/SHEET_NAME` and Google Sheets
URLs. Reads use the first row as column headers by default; writes use
`append` for append semantics and `replace`/`error` for range updates.
