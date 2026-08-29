# Open Table Connector CLI

`otc` and `open-table-connector` are the canonical command names for the Open Table Connector CLI.

The CLI supports listing connectors, inspecting and reading tables, converting
to local files or stdout, and importing into writable connectors.

Install a released CLI with `uv tool install open-table-connector`, or install
from this checkout with `uv sync --dev` followed by `source .venv/bin/activate`.
Then verify the command with `otc --help`.

Examples:

```console
otc list
otc inspect --from orders.csv
otc read --from orders.csv --output-format jsonl
otc read --from csv:///absolute/path/orders.csv --output-format table
otc read --from excel:///absolute/path/orders.xlsx --sheet Orders
otc read --from md:///absolute/path/orders.md --output-format json
otc convert --from orders.csv --to - --output-format jsonl
otc convert --from csv:///absolute/path/orders.csv --to md:///absolute/path/orders.md
otc import --from orders.csv --to gsheets://SPREADSHEET/Orders --if-exists replace
```

The long-form command is also available:

```console
open-table-connector convert --from orders.csv --to orders.json
```

The supported entry-point names are:

- `otc`
- `open-table-connector`
- `open-connectors` (deprecated compatibility alias)

## Local connector routing

The CLI exposes four local connector identities:

| Connector | Routes |
| --- | --- |
| `csv` | `csv://` absolute file URIs |
| `excel` | `excel://` absolute `.xlsx` file URIs, with optional `--sheet` |
| `md` | `md://` absolute Markdown pipe-table file URIs |
| `local_files` | bare paths and `file://` URIs with CSV, XLSX, or Markdown autodetection |

Use `csv://`, `excel://`, or `md://` when the format is part of the endpoint.
Use bare paths or `file://` when compatibility probing should select the local
format from the file payload.
