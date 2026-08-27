# Open Connectors CLI

`otc` and `open-table-connector` are the canonical command names for the Open Table Connector CLI.

The CLI supports listing connectors, inspecting and reading tables, converting
to local files or stdout, and importing into writable connectors.

Examples:

```console
otc list
otc inspect --from orders.csv
otc read --from orders.csv --output-format jsonl
otc convert --from orders.csv --to - --to-format jsonl
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
