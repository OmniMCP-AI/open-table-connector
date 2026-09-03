# Projects and configuration

OTC does not impose an application project file. The CLI and SDK use a
reference-only TOML configuration to select installed provider descriptors and
map logical credential fields to environment variables.

## Configuration lookup

The CLI checks, in order:

1. an explicit path supplied by the caller;
2. `OTC_CONFIG`;
3. `$XDG_CONFIG_HOME/open-table-connector/config.toml` when it exists; and
4. `$HOME/.config/open-table-connector/config.toml` when it exists.

The schema version is `otc.cli-config/v1`. Configuration is limited to 1 MiB,
must be a regular non-symlink file, and rejects unknown fields.

## Minimal configuration

```toml
schema_version = "otc.cli-config/v1"

[[providers]]
id = "google_sheets"
key = "work-google"
options = { timeout_seconds = 30 }

[credentials.work-google]
access_token = { env = "GOOGLE_SHEETS_ACCESS_TOKEN" }
```

The file stores references, not literal secrets. `id`, `enabled`, `key`,
`env`, and non-secret `options` are the provider fields. Secret-like option
names such as `password`, `token`, `secret`, and `api_key` are rejected.

## One-run credential overrides

Use `--credential-key PROVIDER=REFERENCE` to select another configured
credential reference for one CLI invocation:

```console
otc read \
  --from gsheets://SPREADSHEET_ID/Orders \
  --credential-key google_sheets=work-google \
  --output-format jsonl
```

The referenced environment variables are resolved at operation time. A URI
must remain credential-free; do not put tokens in a URI or config path.

## SDK configuration

```python
from open_table_connector.sdk import Client, ClientConfig

with Client.from_config("/absolute/path/config.toml") as client:
    table = client.open("csv:///absolute/path/orders.csv").require_value()
    frame = table.read().require_value()
```

Provider packages are discovered from installed descriptors. The configuration
selects and constrains them; it does not import arbitrary modules or commands.
