# Open Table Connector

Open Table Connector packages are independently released, framework-neutral integrations
for physical data systems. This workspace is intentionally independent of
FinClaw and Open Time Series.

```text
physical system
      |
      v
neutral Connector
  URI + capability + Arrow/Polars + receipt
      |                         |
      v                         v
FinClaw Binding          Open Time Series Binding
```

Connectors own vendor URI parsing, credentials injected by callers, physical
I/O, schema conversion, retries, limits, and neutral receipts. Bindings own
translation into a framework's interfaces. A Connector never owns framework
publication, temporal commit, OpenLineage assembly, business mapping, or
canonical acceptance.

The first workspace packages are:

- `open-table-connector-contract`: closed v1 identity, URI, Base/Sheet coordinate,
  receipt, error, and Arrow/Polars read contracts;
- `open-table-connector-conformance`: reusable parity and dependency-direction
  checks; and
- `open-table-connector-local-files`: concrete `csv`, `excel`, and `md`
  read/inspect connectors plus the `local_files` compatibility facade.

The `open_table_connector` Python namespace is PEP 420 based; framework packages
are never dependencies of the neutral packages.

## Command-line interface

Install the CLI package to use `otc` (or the equivalent
`open-table-connector` command):

```console
otc convert --from orders.csv --to - --to-format jsonl
otc read --from csv:///absolute/path/orders.csv --output-format table
otc read --from excel:///absolute/path/orders.xlsx --sheet Orders
otc read --from md:///absolute/path/orders.md --output-format json
otc read --from gsheets://SPREADSHEET/Orders --output-format json
```

Use explicit local schemes when the format should be selected directly:
`csv://`, `excel://`, and `md://`. Existing bare paths and `file://` URIs
continue to route through `local_files`, which probes CSV, XLSX, and Markdown
payloads for compatibility.
