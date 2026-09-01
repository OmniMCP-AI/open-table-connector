# OTC SDK

`open-table-connector-sdk` is the pure-Python application-facing layer for
Open Table Connector. It gives apps one small, Polars-first surface for table
operations while leaving physical I/O, credentials, receipts, and provider
quirks to pluggable connectors.

## Architecture

```text
CLI / FinClaw / Python apps
            |
            v
      OTC Python SDK
            |
            v
   pluggable physical connectors
```

The SDK is intentionally small:

- `pl.DataFrame` is the in-memory table value.
- `Table` is the only public physical connector-backed handle.
- `Query` is the only deferred table-producing value.
- `Client` owns connector routing, collection, materialization, and execution.

There is no public logical table type, `TableRef`, `TableHandle`,
`MaterializedTable`, or `Table.frame()`.

## Core vocabulary

```python
import polars as pl
from open_table_connector import otc
from open_table_connector.sdk import Client, DirectDestination

# Build a registry from ClientConfig and installed provider descriptors.
client = Client(registry=registry)

orders = client.open("postgres://warehouse/public.orders").require_value()
frame: pl.DataFrame = orders.read().require_value()
result = client.materialize(
    frame,
    to=DirectDestination("sqlite:///tmp/analytics.db"),
)

# The short facade uses the same operations through a lazy default Client.
result = otc.read("csv:///data/orders.csv")
```

`Client.materialize()` is create-only. Existing physical tables are mutated
through explicit operations on `Table`:

- `insert(frame)`
- `update(frame, keys=[...])`
- `delete(where=...)`
- `drop()`

`delete()` always requires `where=`. There is no `clear()`, `replace()`, or
generic write mode switch.

## Modes

The public mode values are:

- `base-mode`
- `sheet-mode`

`base-mode` means a provider-managed typed table with field and record
identity. `sheet-mode` means a bounded, header-aware table region inside a
sheet grid. A worksheet or arbitrary cell range is not itself a `Table`.

During migration, the SDK accepts legacy contract values `base` and `sheet`
only at compatibility boundaries.

## Formula Extension

Formula support is an optional, typed facade over the two existing modes. Use
`Client.formulas(...)` with one of two closed target kinds:

- `GridFormulaTarget(grid=..., worksheet=...)` binds a sheet-mode grid and
  returns a `GridFormulaView`, whose operations accept bounded A1 rectangles.
- `FieldFormulaTarget(table=..., field=...)` binds an opened base-mode
  `Table` and returns a `FieldFormulaView` for an existing formula field.

For example:

```python
grid = client.formulas(
    otc.GridFormulaTarget(
        grid="gsheets://spreadsheet-id",
        worksheet=otc.WorksheetRef(name="Model"),
    )
).require_value()
grid.set(
    "A1:B2",
    otc.FormulaExpression("=A1+1", "google-sheets-a1"),
).require_value()

orders = client.open("feishu://app/table").require_value()
margin = client.formulas(
    otc.FieldFormulaTarget(orders, otc.FieldRef(name="gross_margin"))
).require_value()
margin.set(
    otc.FormulaExpression("=revenue-cost", "feishu-bitable"),
).require_value()
```

Formula expressions are provider-native and opaque. The dialect is required
and must match the bound provider; the SDK does not translate or evaluate
formula text. Formula activation is explicit: only a `FormulaExpression`
passed to a Formula view's `set()` method can activate a formula. Ordinary
`Table` writes remain value-only and do not gain formula behavior.

The Formula Extension is capability-selected for real providers. Google
Sheets, Maybe Sheet, and direct Excel currently expose their proven grid
identities; field identities remain disabled until the field-provider plan's
focused conformance gate passes. Effective capabilities may still be a subset
of a provider's static declaration. Unsupported Formula operations fail before
provider I/O.

## SQL lanes

The SDK exposes three explicit SQL lanes:

- Relational SQL Lite: a portable cross-engine subset for DataFrames, files,
  databases, base-mode tables, and sheet-mode tables.
- Temporal SQL Lite: portable time-series forms such as range scans, as-of,
  latest-per-key, bucket aggregation, and gap fill.
- Provider-native SQL: explicit opt-in, provider-enforced, and never used as a
  silent fallback.

SQLGlot is the parser, normalization, and policy layer. OTC does not execute
raw SQLGlot ASTs directly. Local execution is planned through a Polars plan
mapper over bounded inputs.

DuckDB is intentionally out of scope for the first SDK execution path. It
remains a future local-executor option and is tracked in the architecture docs
for later evaluation.

## Time-series

The SDK surface must cover both current normalized table operations and OTC's
portable time-series additions. Temporal queries still return `Query` values
and evaluate to Polars `DataFrame` results. Managed temporal lifecycle calls
return the same normalized `OperationResult[T]` envelope used elsewhere.

Managed snapshot recovery is public and provider-neutral:

```python
series = table.time_series(descriptor)
state = series.storage.current().require_value()
if state is not None:
    snapshot = state.snapshot
    frame = series.storage.readback(snapshot).require_value()
```

`current()` returns `None` only when the logical time-series target has no
committed current snapshot. A returned `ManagedSnapshotState` includes the
public `ManagedSnapshot` handle and the recovered Arrow schema; callers never
need to inspect provider metadata or physical artifact paths.

Temporal SQL Lite is a closed portable profile. It accepts bounded `ScanRange`
queries, typed `Latest` queries, `BucketAggregate` queries, and `GapFill`
queries with `locf` or `interpolate`. `AsOf` remains available as the typed
helper `series.as_of(...)` and is intentionally rejected as SQL. Accepted SQL
uses numbered typed parameters, exact half-open event-time bounds, a positive
literal `LIMIT`, and complete deterministic ordering.

Duplicate policy is part of the descriptor contract. `first` and `last`
aggregates require a policy that resolves duplicate events; they are rejected
for `preserve`. `replace-latest` additionally requires an ingestion-time field
and a complete replacement key. These checks are applied before a portable
plan is constructed and again by the evaluator.

## CLI relationship

The `otc` CLI is a thin parser and renderer over this SDK. It exists to
demonstrate the SDK surface and provide a convenient shell entry point; it is
not the architectural center of OTC.

## Deferred Rust bridge

Rust and OTS integration is specified separately. The current SDK work keeps a
clean seam for:

```text
OTC Python SDK <-> Rust adapter SDK <-> OTS Rust
```

That bridge is deferred until after the Python SDK surface is stabilized.
