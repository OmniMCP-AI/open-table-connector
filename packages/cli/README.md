# Open Table Connector CLI

`otc` and `open-table-connector` are the canonical command names for the Open Table Connector CLI.

The CLI supports listing connectors, inspecting and reading tables, converting
to local files or stdout, importing into writable connectors, discovering
versioned operations, and running buffered spreadsheet sessions.

Install a released CLI with `uv tool install open-table-connector`, or install
from this checkout with `uv sync --all-packages --group dev` followed by `source .venv/bin/activate`.
Then verify the command with `otc --help`.

Show the stable package version and the latest source commit label with:

```console
otc --version
```

Examples:

```console
otc list
otc inspect --from orders.csv
otc read --from orders.csv --output-format jsonl
otc read --from file:///absolute/path/orders.csv --output-format table
otc read --from file:///absolute/path/orders.xlsx --sheet Orders
otc read --from md:///absolute/path/orders.md --output-format json
otc convert --from orders.csv --to - --output-format jsonl
otc convert --from /absolute/path/orders.csv --to md:///absolute/path/orders.md
otc import --from orders.csv --to gsheets://SPREADSHEET/Orders --if-exists replace
otc import --from orders.csv --to https://www.maybe.ai/docs/spreadsheets/d/DOCUMENT --target Orders --if-exists append
otc help spreadsheet range.style --output-format json
otc capabilities --uri file:///absolute/path/report.xlsx --output-format json
otc spreadsheet read --uri file:///absolute/path/report.xlsx --sheet Orders --range A1:D20
otc spreadsheet recipe export --uri file:///absolute/path/report.xlsx --selectors selectors.json
otc artifact export --from orders.csv --to report.docx
```

`otc spreadsheet` uses the SDK workbook session and preserves its bounded
preflight, commit, receipt, and verification semantics. Creation profiles are
`literal-artifact/1.0`, `general/1.0`, and the explicit
`rich-artifact/1.0`. The rich profile uses existing Excelize capabilities for
qualified local XLSX objects, currently PNG/JPEG image workflows with
independent serialized readback. MaybeSheet sheet-mode uses the same contract
but remains capability- and live-evidence-gated.

Observed layout recipes use the closed `otc.spreadsheet-recipe/1.0` envelope:

```console
otc spreadsheet recipe export --uri file:///absolute/path/report.xlsx \
  --selectors selectors.json
otc spreadsheet apply --uri file:///absolute/path/report.xlsx \
  --spec recipe.json --dry-run
```

Optional artifact support is installed separately with
`open-table-connector-artifacts` and `open-table-connector-officecli`. The
adapter creates native DOCX/PPTX table snapshots and never authors XLSX.
HTML/PNG/text/outline/stats/issues views and watch sessions are
renderer-dependent SDK contracts; the CLI reports `unsupported_capability`
until a qualified OfficeCLI runtime is configured. Legacy `.doc`, `.ppt`, and
`.xls` destinations are rejected.

The long-form command is also available:

```console
open-table-connector convert --from orders.csv --to orders.json
```

The supported entry-point names are:

- `otc`
- `open-table-connector`
- `open-connectors` (deprecated compatibility alias)

## Provider configuration

Provider adapters are discovered from installed wheels and configured without
embedding credentials in command arguments. Set `OTC_CONFIG` (or place the file
at `$XDG_CONFIG_HOME/open-table-connector/config.toml`) and reference secrets
through environment variables:

```toml
schema_version = "otc.cli-config/v1"

[[providers]]
id = "google_sheets"
key = "work-google"
env = { endpoint = "GOOGLE_SHEETS_ENDPOINT" }
options = { timeout_seconds = 30 }

[credentials.work-google]
access_token = { env = "GOOGLE_SHEETS_ACCESS_TOKEN" }
```

Use `--credential-key PROVIDER=REFERENCE` for a one-run reference override.
Configuration contains only logical environment bindings; literal secrets and
route overrides are rejected. Providers may be installed, disabled, or removed
independently; `otc list` reports only installed and enabled descriptors.

## Local connector routing

The CLI exposes two public local connector identities:

| Connector | Routes |
| --- | --- |
| `md` | `md://` absolute Markdown pipe-table file URIs |
| `local_files` | bare paths and `file://` URIs with CSV, XLSX, JSON, JSONL, or Markdown autodetection |

CSV is a supported format and codec, not a public connector identity or URI
scheme. Use bare paths or `file://` for local CSV files, `--from-format csv`
when the input format must be explicit, and `--output-format csv` or
`--to-format csv` for CSV output. Use `md://` when Markdown is explicitly part
of the endpoint; otherwise local-file probing selects the format from the path
and payload. MaybeSheet uses canonical
`https://www.maybe.ai/docs/spreadsheets/d/DOCUMENT` URLs rather than a
provider-specific public URI route.

See the [CLI reference](../../docs/user-guide/cli.md), [spreadsheet operations
guide](../../docs/user-guide/spreadsheet-operations.md), and [agent
workflows](../../docs/user-guide/agent-workflows.md) for the complete command
and evidence contracts.

The complete behavior manual is the [CLI manual](../../docs/user-guide/cli-manual.md);
the generated [option inventory](../../docs/reference/cli-options.md) is the
parser-level reference.
