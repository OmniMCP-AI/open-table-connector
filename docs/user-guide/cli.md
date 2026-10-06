# `otc` command reference

The canonical commands are `otc` and `open-table-connector`. The deprecated
`open-connectors` alias remains available for compatibility.

## Commands

| Command | Purpose |
| --- | --- |
| `list` | List installed connector descriptors and capabilities |
| `inspect` | Read schema, row count, fingerprints, and source facts |
| `read` | Read one endpoint and emit rows |
| `convert` | Read once and write a local file or stdout |
| `import` | Read once and write a writable connector |
| `help` | Describe a versioned operation without opening a target |
| `capabilities` | Resolve endpoint operation support and evidence |
| `spreadsheet` | Buffer, inspect, verify and publish workbook operations |
| `artifact` | Export native document artifacts and request bounded views |

## Common options

| Option | Values | Notes |
| --- | --- | --- |
| `--from` | endpoint | Required except for `list` |
| `--to` | endpoint | Required for `convert` and `import` |
| `--from-format` | `auto`, `csv`, `excel`, `json`, `jsonl`, `table` | Local source override |
| `--output-format` | `csv`, `json`, `jsonl`, `table` | Output representation; `convert` also accepts `auto` and `excel` |
| `--to-format` | `auto`, `csv`, `excel`, `json` | Destination codec for `convert` |
| `--if-exists` | `error`, `append`, `replace` | Destination conflict policy |
| `--limit` | positive integer | Maximum rows for a read |
| `--timeout` | positive number | Connector request timeout |
| `--sheet` | sheet name | Excel or Sheets selection |
| `--range` | provider range | Bounded Sheets range |
| `--field-name` | repeatable name | Feishu field projection |
| `--credential-key` | `PROVIDER=REFERENCE` | One-run credential selection |
| `--token` | secret value | Local experiment only; prefer environment bindings |
| `--target` | provider target | MaybeSheet target selection |

Examples:

```console
otc list
otc inspect --from orders.csv --output-format json
otc read --from orders.csv --output-format jsonl
otc convert --from orders.csv --to orders.xlsx --to-format excel --sheet Orders
otc import --from orders.csv --to gsheets://ID/Orders --if-exists replace
otc help spreadsheet range.style --output-format json
otc capabilities --uri file:///absolute/path/report.xlsx --output-format json
```

Success output uses the selected format. Errors are one safe JSON object on
stderr; automation should use the exit code and stable error `code`, not
human-readable message text.

## Optional artifact and MCP packages

Install `open-table-connector-artifacts` with the adapter you need. The
OfficeCLI adapter can create native DOCX/PPTX table snapshots. The neutral SDK
also defines HTML, PNG, text, outline, stats, issues, and disposable watch view
contracts, but the current CLI intentionally returns
`unsupported_capability` for `artifact view` and `artifact watch` until a
qualified OfficeCLI binary and renderer are configured. These views operate on
owned disposable snapshots and never become the authoritative workbook.

```console
otc artifact export --from orders.csv --to report.docx
```

The export adapter accepts qualified CSV sources and DOCX/PPTX destinations.
Legacy `.doc`, `.ppt`, and `.xls` destinations are rejected. OfficeCLI is not
an XLSX authoring backend and is never used as a fallback for rich spreadsheets.

Rich XLSX operations use existing Excelize capabilities through local files;
MaybeSheet sheet-mode retains the same contract but remains live-evidence
gated. The qualified local subset currently covers PNG/JPEG image insertion,
observation, and index deletion with independent serialized readback. Other
object families are capability-gated until their preservation and readback
evidence exists. Use `--profile rich-artifact/1.0` explicitly when creating a
local workbook for this surface.

```console
otc spreadsheet operation --uri file:///absolute/path/report.xlsx \
  --profile rich-artifact/1.0 --operation image.insert --sheet Report \
  --arguments '{"content_base64":"...","mime_type":"image/png","anchor":"B2"}'
```

Layout recipes use the closed `otc.spreadsheet-recipe/1.0` envelope. Exported
recipes contain observed layout operations only; they do not contain values,
formulas, or image bytes and they reject unsupported properties before
dispatch.

```console
otc spreadsheet recipe export --uri file:///absolute/path/report.xlsx \
  --selectors selectors.json
otc spreadsheet apply --uri file:///absolute/path/report.xlsx \
  --spec recipe.json --dry-run
```

The optional `open-table-connector-mcp` package exposes exactly three typed
tools: `otc_discover`, `otc_inspect`, and `otc_execute`. It uses the official
MCP stdio transport, requires an explicit fail-closed policy for deployment,
and does not accept shell commands, arbitrary module names, or credential
values in request arguments.
