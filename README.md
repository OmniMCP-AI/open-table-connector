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
- `open-table-connector-timeseries`: the closed portable temporal plan,
  Polars/Arrow evaluator, managed-storage protocols, and neutral receipts;
- `open-table-connector-process`: the pinned local framed transport used by
  sister-product bindings; and
- `open-table-connector-local-files`: concrete `csv`, `excel`, and `md`
  read/inspect connectors plus the `local_files` compatibility facade.

The `open_table_connector` Python namespace is PEP 420 based; framework packages
are never dependencies of the neutral packages.

## Get started

Install a released CLI with `uv`:

```console
uv tool install open-table-connector
otc --help
```

When working from a checkout, install the workspace and activate its virtual
environment:

```console
uv sync --all-packages --group dev
source .venv/bin/activate
otc --help
```

Read, inspect, and convert a local table:

```console
otc inspect --from orders.csv --output-format json
otc read --from csv:///absolute/path/orders.csv --output-format table
otc convert --from orders.csv --to orders.jsonl --output-format jsonl
```

The CLI is the quickest path for ordinary table movement. The typed Python
time-series API is the path for bounded `ScanRange`, `Latest`, `AsOf`, bucket,
and gap-fill operations.

## Command-line interface

Install the CLI package to use `otc` (or the equivalent
`open-table-connector` command):

```console
otc convert --from orders.csv --to - --output-format jsonl
otc read --from csv:///absolute/path/orders.csv --output-format table
otc read --from excel:///absolute/path/orders.xlsx --sheet Orders
otc read --from md:///absolute/path/orders.md --output-format json
otc read --from gsheets://SPREADSHEET/Orders --output-format json
```

Use explicit local schemes when the format should be selected directly:
`csv://`, `excel://`, and `md://`. Existing bare paths and `file://` URIs
continue to route through `local_files`, which probes CSV, XLSX, and Markdown
payloads for compatibility.

## Portable time-series storage

OTC can act as an explicit reduced-capability storage backend for
[Open Time Series](https://github.com/OmniMCP-AI/open-time-series). The portable
lane accepts a closed typed plan—not SQL—and supports bounded range scans,
latest/as-of lookup, bucket aggregation, and gap fill. Native TimescaleDB talks
directly to OTS through its thin native adapter and does not pass through OTC.

The provider inventory is explicit: CSV, JSON, JSONL, SQLite, PostgreSQL, and
Excel expose only their certified portable capabilities; MaybeSheet remains
import/export-only unless a live command probe and receipts prove more. JSON
and JSONL always use `json://` and `jsonl://`; managed snapshot selection is
request metadata, never a `managed+` URI.

See the [OTC architecture specification](docs/superpowers/specs/2026-08-29-portable-time-series-storage-design.md),
the [implementation plan](docs/superpowers/plans/2026-08-29-portable-time-series-storage.md),
and the [conformance suite](specification/conformance/timeseries/README.md).

## Documentation

- [Getting started](docs/getting-started.md) — install, first reads, and a
  minimal portable temporal query.
- [User manual](docs/user-manual.md) — CLI reference, URI rules, connector
  support matrix, temporal API, managed lifecycle, process adapter, and
  troubleshooting.
- [Demos and use cases](docs/demos.md) — CSV/JSONL/Excel workflows, portable
  temporal queries, SQLite/PostgreSQL, and `otc-process`.
- [Portable time-series design](docs/superpowers/specs/2026-08-29-portable-time-series-storage-design.md)
  — normative OTC contract and cross-link to OTS.
