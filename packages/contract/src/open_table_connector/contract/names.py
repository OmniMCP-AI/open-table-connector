"""Canonical package, connector, and discovery identifiers."""

PACKAGE_NAMESPACE = "open_table_connector"

PROVIDER_CSV = "csv"
PROVIDER_JSON = "json"
PROVIDER_JSONL = "jsonl"
PROVIDER_EXCEL = "excel"
PROVIDER_LOCAL_FILES = "local_files"
PROVIDER_SQLITE = "sqlite"
PROVIDER_POSTGRES = "postgres"
PROVIDER_GOOGLE_SHEETS = "google_sheets"
PROVIDER_FEISHU_BITABLE = "feishu_bitable"
PROVIDER_MAYBE_SHEET = "maybe_sheet"
PROVIDER_DBT = "dbt"

SCHEME_FILE = "file"
SCHEME_XLSX = "xlsx"
SCHEME_MD = "md"
SCHEME_MANAGED_CSV = "managed+csv"
SCHEME_MANAGED_XLSX = "managed+xlsx"
SCHEME_POSTGRESQL = "postgresql"
SCHEME_GSHEETS = "gsheets"
SCHEME_HTTPS = "https"
SCHEME_FEISHU = "feishu"
SCHEME_MAYBE = "maybe"

HOST_GOOGLE_DOCS = "docs.google.com"
HOST_MAYBE = "www.maybe.ai"

CLI_PLUGIN_GROUP = f"{PACKAGE_NAMESPACE}.cli_adapters"
PROCESS_PLUGIN_GROUP = f"{PACKAGE_NAMESPACE}.process_handlers"
PROVIDER_PLUGIN_GROUP = f"{PACKAGE_NAMESPACE}.providers"

__all__ = [name for name in globals() if name.isupper()]
