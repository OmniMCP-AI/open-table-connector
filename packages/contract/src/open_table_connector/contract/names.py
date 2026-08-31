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

FORMAT_AUTO = "auto"
FORMAT_TABLE = "table"
CLI_CONFIG_SCHEMA_VERSION = "otc.cli-config/v1"
CLI_CONFIG_ENV = "OTC_CONFIG"
XDG_CONFIG_HOME_ENV = "XDG_CONFIG_HOME"
CLI_CONFIG_DIRECTORY = "open-table-connector"
CLI_CONFIG_FILENAME = "config.toml"

CAPABILITY_TABLE_READ_ARROW = "table.read.arrow"
CAPABILITY_TABLE_WRITE = "table.write"
IF_EXISTS_APPEND = "append"
IF_EXISTS_REPLACE = "replace"
IF_EXISTS_ERROR = "error"

CREDENTIAL_ACCESS_TOKEN = "access_token"
CREDENTIAL_TENANT_ACCESS_TOKEN = "tenant_access_token"
SETTING_ENDPOINT = "endpoint"
SETTING_BINARY = "binary"
OPTION_TIMEOUT_SECONDS = "timeout_seconds"

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

PROVIDER_IDS = (
    PROVIDER_CSV,
    PROVIDER_JSON,
    PROVIDER_JSONL,
    PROVIDER_EXCEL,
    PROVIDER_LOCAL_FILES,
    PROVIDER_SQLITE,
    PROVIDER_POSTGRES,
    PROVIDER_GOOGLE_SHEETS,
    PROVIDER_FEISHU_BITABLE,
    PROVIDER_MAYBE_SHEET,
    PROVIDER_DBT,
    SCHEME_MD,
)

__all__ = [name for name in globals() if name.isupper()]
