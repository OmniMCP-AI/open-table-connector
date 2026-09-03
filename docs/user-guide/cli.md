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
```

Success output uses the selected format. Errors are one safe JSON object on
stderr; automation should use the exit code and stable error `code`, not
human-readable message text.
