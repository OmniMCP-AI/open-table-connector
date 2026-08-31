# Open Table Connector

Open Table Connector packages are independently released, framework-neutral
integrations for physical data systems. The center of the workspace is now a
pure-Python OTC SDK: applications talk to the SDK, and the SDK talks to
pluggable physical connectors.

```text
CLI / FinClaw / Python apps
            |
            v
      OTC Python SDK
            |
            v
   pluggable physical connectors
```

Connectors own vendor URI parsing, credentials injected by callers, physical
I/O, schema conversion, retries, limits, and neutral receipts. The SDK owns
the normalized table surface, SQL policy, temporal query surface, operation
results, and application-facing ergonomics. A connector never owns framework
publication, temporal commit policy, OpenLineage assembly, business mapping,
or canonical acceptance.

The main workspace packages are:

- `open-table-connector-contract`: closed v1 identity, URI, Base/Sheet coordinate,
  receipt, error, and Arrow/Polars read contracts;
- `open-table-connector-sdk`: pure-Python client SDK with `Client`, `Table`,
  `Query`, Polars DataFrame integration, normalized results, and SQL/time-series
  facades;
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

The CLI is the quickest path for ordinary table movement, but it is now meant
to be a thin wrapper over the SDK. The Python SDK is the primary application
surface for normalized table operations, relational SQL lite, temporal SQL
lite, and bounded time-series operations.

## Python SDK

The public Python vocabulary is intentionally small:

- `pl.DataFrame`: in-memory table value
- `Table`: physical connector-backed table
- `Query`: deferred table-producing computation
- `Client`: routing, collection, materialization, SQL, and execution entry point

Materialization is create-only. Existing tables are mutated through explicit
`insert`, keyed `update`, required-predicate `delete(where=...)`, and `drop`
operations. There is no `TableRef`, `TableHandle`, `MaterializedTable`,
`Table.frame()`, `clear()`, `append()`, or generic `replace` mode.

Mode names are normalized as `base-mode` and `sheet-mode`. A worksheet or
arbitrary A1 range is not itself a `Table`; sheet-mode means a bounded,
header-aware table region inside a sheet grid.

### SQL support

OTC exposes three explicit SQL lanes:

- Relational SQL Lite for portable cross-engine table queries
- Temporal SQL Lite for range, as-of, latest, bucket, and gap-fill forms
- Provider-native SQL for explicit provider-specific execution

SQLGlot is used for parsing, normalization, and policy enforcement. Local
portable execution is designed around a Polars plan mapper. DuckDB is not a
current dependency; it is only tracked as a future local execution option.

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
[Open Time Series](https://github.com/OmniMCP-AI/open-time-series). In the
approved architecture, the Python SDK remains separate from the future Rust/OTS
bridge:

```text
OTC Python SDK <-> Rust adapter SDK <-> OTS Rust
```

That bridge is intentionally deferred while the Python SDK surface is being
stabilized. The portable lane accepts a closed typed plan and supports bounded
range scans, latest/as-of lookup, bucket aggregation, and gap fill.

The provider inventory is explicit: CSV, JSON, JSONL, SQLite, PostgreSQL, and
Excel expose only their certified portable capabilities; MaybeSheet remains
import/export-only unless a live command probe and receipts prove more. JSON
and JSONL always use `json://` and `jsonl://`; managed snapshot selection is
request metadata, never a `managed+` URI.

See the [OTC architecture specification](docs/superpowers/specs/2026-08-29-portable-time-series-storage-design.md),
the [implementation plan](docs/superpowers/plans/2026-08-29-portable-time-series-storage.md),
and the [conformance suite](specification/conformance/timeseries/README.md).

## Documentation

Provider adapters are independently pluggable. Configure installed providers
with a reference-only TOML file selected by `OTC_CONFIG` (or the XDG config
location); credentials are resolved from environment variables at operation
time. For a complete example, see [CLI provider configuration](packages/cli/README.md#provider-configuration).

- [Getting started](docs/getting-started.md) — install, first reads, and a
  minimal portable temporal query.
- [User manual](docs/user-manual.md) — CLI reference, URI rules, connector
  support matrix, temporal API, managed lifecycle, process adapter, and
  troubleshooting.
- [OTC Python SDK design](docs/superpowers/specs/2026-08-31-python-sdk-design.md)
  — normalized SDK surface, SQL lanes, table vocabulary, and mode boundaries.
- [Rust adapter / OTS bridge design](docs/superpowers/specs/2026-08-31-rust-client-ots-bridge-design.md)
  — deferred bridge seam after the Python SDK stabilizes.
- [Demos and use cases](docs/demos.md) — CSV/JSONL/Excel workflows, portable
  temporal queries, SQLite/PostgreSQL, and `otc-process`.
- [Portable time-series design](docs/superpowers/specs/2026-08-29-portable-time-series-storage-design.md)
  — normative OTC contract and cross-link to OTS.
