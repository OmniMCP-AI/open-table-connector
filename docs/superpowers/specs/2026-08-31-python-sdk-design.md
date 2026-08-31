# Polars-First OTC Python SDK Architecture

**Status:** proposed architectural design; pending final review before a
separate implementation-planning gate.

**Assumption:** the current CLI refactor is completed before this migration.
Other unexecuted implementation plans are not assumed complete.

## Decision

Open Table Connector becomes an application-independent Python SDK between
applications and pluggable physical-medium Connectors:

```text
CLI / FinClaw / Python applications
                 |
                 v
          OTC Python SDK
                 |
                 v
   pluggable physical-medium Connectors
```

The public value model is intentionally small:

- `polars.DataFrame` is the concrete in-memory table value;
- `Query` is one immutable deferred table-producing plan;
- `Table` is one physical, Connector-backed table; and
- `TableSource` is the accepted source union, not a wrapper callers construct.

There is no public logical `Table`, `TableRef`, `TableHandle`, or
`MaterializedTable`. There is no `Table.frame()` escape hatch. Callers
manipulate a DataFrame with Polars directly and cross into physical I/O only
through `Client`, `Table`, or a descriptor-bound time-series view.

Materialization is create-only. Existing Tables are mutated only through
explicit `insert`, strict keyed `update`, predicate-required `delete`, and
`drop` operations. There is no generic `write(if_exists=...)`, `replace`,
`clear`, implicit upsert, or `copy_to` operation.

All evaluated or physical operations use one normalized
`OperationResult[T]`. Physical evidence remains in plural Receipts and never
becomes hidden mutable client state or DataFrame metadata.

OTS integration is not part of this implementation. Its future Rust adapter
is specified separately in
`2026-08-31-rust-client-ots-bridge-design.md`.

## Goals

1. Make OTC straightforward to use from ordinary Python and Polars code.
2. Normalize table-shaped operations without erasing meaningful base-mode and
   sheet-mode differences.
3. Support every current normalized Table operation and the declared portable
   time-series operations through one SDK.
4. Keep the CLI a thin parser/renderer that demonstrates SDK usage.
5. Provide portable relational and temporal SQL with one semantic contract
   across DataFrames, files, databases, base-mode Tables, and sheet-mode
   Tables.
6. Keep provider discovery, routing, credentials, bounds, retries,
   reconciliation, receipts, and Arrow conversion out of applications.
7. Let independently distributed Connectors extend physical media without
   changing the SDK interface.
8. Preserve a stable internal host port for a future Rust adapter without
   exposing Arrow or process mechanics to Python callers.

## Non-goals

- Rewriting OTS in Python or integrating OTS in this phase.
- Treating a worksheet or arbitrary cell range as a Table.
- Exposing workbook grids, formulas, arbitrary coordinates, or provider UI
  features through the normalized Table interface.
- General SQL:2016 conformance or arbitrary provider SQL portability.
- Executing SQLGlot ASTs, Polars SQLContext statements, or caller-provided
  DuckDB SQL.
- Making an arbitrary `polars.LazyFrame` a Connector input. A LazyFrame may
  hide external scans, Python UDFs, or unbounded work outside OTC policy.
- Attaching lineage, credentials, receipts, themes, or provider identity to a
  Polars DataFrame.
- Claiming atomicity, snapshot stability, pushdown, or presentation fidelity
  that a Connector cannot prove.
- Adding an async facade before there are genuine async Connector interfaces.

## Domain and Value Model

### Public values

| Value | Meaning | Contains | Does not contain |
| --- | --- | --- | --- |
| `pl.DataFrame` | Concrete in-memory table value | schema and rows | URI, credentials, lineage, receipts, theme, provider identity |
| `Query` | Deferred table-producing computation | Portable Plan, explicit sources, schema, limits, policy, plan identity | SQLGlot AST, provider objects, credential values |
| `Table` | Physical table handle | canonical Table URI, Table Mode, observed schema/identity, client dispatch binding | row payload, credentials, Connector instance |
| `TableTheme` | Portable presentation intent | semantic table regions and portable properties | grid coordinates or provider style IDs |
| `TableStyle` | Concrete presentation observation or realization | capability-scoped physical properties | portable data semantics |

`Table` always means the physical type. A DataFrame is the in-memory table
value. A `Query` is deferred work that evaluates to a DataFrame. These names
must not be overloaded by compatibility aliases.

### Table Source

`TableSource` is a closed accepted-source union:

```python
TableSource = (
    pl.DataFrame
    | Query
    | Table
    | SheetRangeSource
)
```

It is a typing and normalization concept, not a metadata-bearing wrapper.

- A DataFrame is snapshotted into a canonical bounded carrier when an
  operation begins.
- A Query binds only explicitly supplied sources and is evaluated under its
  recorded limits and consistency policy.
- A Table source is read completely from one pinned or stability-proven
  snapshot.
- A `SheetRangeSource` names an exact grid, fixed range, exact declared schema,
  header/data policy, and value/formula rendering policy. It is a source, not
  a Table. Collection verifies the observed schema against the declaration.

Callers that do not yet know the range schema use the physical binding
operation:

```python
source = client.bind_sheet_range(
    grid=grid_address,
    cell_range="A1:D500",
    header=True,
    schema=None,
    schema_policy="infer_complete",
).require_value()
```

`bind_sheet_range()` returns `OperationResult[SheetRangeSource]`. It inspects
or reads the complete bounded range under finite limits, records a physical
Receipt, and returns an exact schema/header/rendering contract. Its two closed
schema policies are `validate_declared`, which requires `schema=` and validates
it against an exact provider schema or complete observation, and
`infer_complete`, which requires `schema=None` and infers from the complete
range. Neither policy samples rows or treats the whole worksheet as the range
schema. `SheetRangeSource` has no public free constructor; Client binding is
the only public creation path and attaches its dispatch affinity. The returned
source carries the observed revision/snapshot constraint; later collection
fails if it changed unless the caller explicitly rebinds.

Every Client operation that accepts a Table Source enforces physical-source
affinity before I/O. A `Table` or `SheetRangeSource` may be collected,
materialized, or captured in a Query only by the Client that opened or bound
it. Module-level convenience operations accept physical handles from the
default Client only. Moving work to another Client requires reopening the
canonical Table address or rebinding the range there; OTC never imports a
foreign dispatch binding or credential lease implicitly.

Schema-only materialization uses an ordinary zero-row DataFrame with an exact
Polars schema:

```python
empty = pl.DataFrame(
    schema={
        "order_id": pl.Int64,
        "amount": pl.Decimal(18, 2),
    }
)
```

There is no separate schema-only Table proposal type.

### Base-mode and sheet-mode

`TableMode` has exactly two public values:

```python
TableMode.BASE_MODE   # wire value: "base-mode"
TableMode.SHEET_MODE  # wire value: "sheet-mode"
```

These are the new normalized public/wire values. Current contract v1 schemas
encode `"base"` and `"sheet"`; adapters decode those legacy values during
migration, but existing v1 capability and Receipt schemas are never rewritten
in place. Emitting `"base-mode"`/`"sheet-mode"` requires a versioned successor
schema and updated compatibility fixtures.

- A base-mode Table consists of typed fields and records, with provider-owned
  field and record identity.
- A sheet-mode Table is one bounded, header-aware region within a sheet-mode
  grid.

A worksheet contains a grid and may contain Tables; it is not itself a Table.
An arbitrary A1 range is not a Table. `SheetTable` remains the Maybe base-mode
package/engine name. Excelize remains the Maybe sheet-mode engine name.

### Alignment with the Maybe execution seam

OTC adopts the resource honesty and deep execution-seam rules from the Maybe
designs while placing them behind a Connector rather than in applications:

| Maybe design role | OTC role |
| --- | --- |
| Base table backed by SheetTable | `Table(mode="base-mode")` |
| bounded header-aware table backed by Excelize | `Table(mode="sheet-mode")` |
| worksheet or cell grid | physical container, explicit range source, or sheet-grid extension; never a Table |
| local frame file | CLI-only codec that yields or consumes a Polars DataFrame |
| query create source | deferred Query supplied to `Client.materialize()` |
| range create source | explicit `SheetRangeSource` supplied to `Client.materialize()` |
| unified backend table creation | one Connector `create_table` seam |
| execution/result envelope | `OperationResult` plus ordered Receipts |
| provider OpenLineage run | provider evidence that may be referenced by a Receipt; not DataFrame metadata |

The Maybe provider may place both modes behind one deployment, but its
base-mode adapter delegates to the SheetTable engine and its sheet-mode
adapter delegates to Excelize. It must derive mode from the resolved physical
identity and never fall back across engines.

The older Maybe CLI's source-specific create operations and frame paths are
compatibility inputs, not OTC SDK concepts. Its CLI decodes a frame into a
DataFrame and lowers query/range creation to `Client.materialize()`. It does
not pass a local path, raw create-from-query request chain, `if_exists=adopt`,
or verification orchestration through the SDK.

Provider-specific identity-preserving refresh and table replacement remain
outside the OTC SDK; they do not reappear as normalized extensions. Formula,
grid, and workbook operations may use typed extensions, while OpenLineage
publication remains provider-owned evidence. A Maybe Connector may use private
engine workflows only when they satisfy the exact normalized operation it
advertises. OTC retains create-only materialization, explicit source binding,
snapshot evidence, no cross-engine fallback, and read-only reconciliation.

Alignment references:

- [SheetTable Unified Execution Seam Design](https://github.com/OmniMCP-AI/SheetTable/blob/main/docs/superpowers/specs/2026-08-20-sheettable-execution-seam-design.md)
- [Critical Review of SheetTable Unified Execution Seam Design](https://github.com/OmniMCP-AI/SheetTable/blob/main/docs/superpowers/specs/Critical%20Review%20of%20SheetTable%20Unified%20Execution%20Seam%20Design%20-%20grok.md)
- [Maybe CLI Table Frame I/O and Unified Create Sources](https://github.com/OmniMCP-AI/maybeai-sheet-cli/blob/main/docs/superpowers/specs/2026-08-24-table-frame-and-create-source-design.md)

### Evidence and lineage

A DataFrame contains data only. A Receipt records one physical interaction.
An `OperationResult` records one normalized operation outcome and its ordered
Receipts. Neither is FinClaw `FrameMeta`, `Run`, `RunResult`, or `RunState`.

FinClaw may construct its own lineage or FrameMeta from OTC Receipts, source
identities, Query identity, and application context. OTC does not own the
application lineage graph.

## Architecture and Package Direction

### Dependency graph

```text
open-table-connector-cli
            |
            v
open-table-connector-sdk
      |        |        |
      v        v        v
  contract     sql   timeseries
      ^        |        |
      |        v        |
      +----- Polars <----+
      ^
      |
provider Connector packages
```

Normative dependency rules:

- `sdk` depends on `contract`, `sql`, `timeseries`, and Polars.
- `sql` depends on `contract`, `timeseries`, Polars, and a pinned SQLGlot
  parser version. It never depends on `sdk` or provider packages.
- `timeseries` depends on `contract`; it never depends on `sdk`, `sql`, or
  provider packages.
- provider packages depend on `contract` and optional plan/time-series
  interfaces; they never depend on `sdk` or `cli`.
- `cli` depends on `sdk` and rendering libraries only.

The `sdk` package alone owns the public `Client`, `Table`, `Query`,
`SheetRangeSource`, and `TableSource` types. The `sql` package returns an
internal prepared relational-plan value; `timeseries` returns descriptors and
Portable Temporal Plans. SDK factories wrap those neutral outputs in Query,
so neither lower package imports SDK or constructs a public Query. This
ownership rule prevents a Query/Table source-binding dependency cycle.

Arrow is the verified internal carrier at Connector and future host-port
seams. A Connector may return a bounded, snapshot-bound Arrow batch stream,
but never a Polars LazyFrame, executable scan object, or caller-visible path.
The stream contract carries its exact schema, extent status, snapshot lease,
and limits; the SDK validates every batch before use. Polars is the application
value. A public Polars result is converted once from the verified carrier; a
future Rust adapter uses the internal carrier-preserving host port rather than
converting Polars back to Arrow.

### Deep modules and seams

`Client` is the deep orchestration module. It hides:

- target normalization and routing;
- Connector discovery and lazy activation;
- credential resolution and leases;
- capability preflight and effective-capability probing;
- source binding, complete reads, snapshots, and resource admission;
- SQL and temporal preparation;
- local Polars evaluation and certified pushdown selection;
- materialization, idempotency, verification, and reconciliation;
- Arrow validation and Polars conversion; and
- receipt and error normalization.

`Table` is the deep physical-operation facade. Provider packages supply
Connector adapters at the contract seam. Local file/database implementations
are locally substitutable in conformance tests. Maybe engines are remote-owned
adapters. Google Sheets and Feishu are true external adapters and retain their
real paging, revision, batching, and uncertainty behavior.

## Public Python Interface

### Imports and client lifecycle

The application surface lives under `open_table_connector.sdk`, re-exported
through a short documented namespace:

```python
from open_table_connector import otc
```

Configured applications own a Client lifetime:

```python
with otc.Client.from_config("/etc/otc/config.toml") as client:
    table = client.open("feishu://APP_TOKEN/TABLE_ID").require_value()
    frame = table.read().require_value()
```

Module-level convenience functions delegate to one lazily created,
thread-safe default Client:

```python
result = otc.read("csv:///data/orders.csv")
created = otc.materialize(frame, to="parquet:///data/orders.parquet")
```

A credential-free URI string in a `to=` position is documented shorthand for
`DirectDestination(uri=...)`; the SDK normalizes it before planning. Container
destinations always require their typed BaseModeDestination or
SheetModeDestination form.

Every module-level physical/evaluated operation returns the same
`OperationResult` as the Client path. Convenience functions do not define a
second semantic path.

The synchronous interface is authoritative in v1. `Client.close()` is
idempotent and closes providers, transports, credential leases, and artifact
workspaces in reverse construction order. Tables bound to a closed Client fail
with `CLIENT_CLOSED`.

### Addressing existing Tables and new destinations

`client.open(...)` accepts a canonical credential-free Table URI or one member
of a closed `ExistingTableAddress` union:

```python
ExistingTableAddress = (
    DirectTableAddress
    | DatabaseTableAddress
    | BaseModeTableAddress
    | SheetModeTableAddress
)

DatabaseTableAddress(
    database=database_target,
    name=QualifiedTableName(catalog=None, schema="public", table="orders"),
)

BaseModeTableAddress(container=workbook, table_id="orders")
SheetModeTableAddress(grid=sheet_grid, table_id="orders_region")
```

`DirectTableAddress` wraps a URI that already identifies exactly one Table.
`DatabaseTableAddress` separates the database execution domain from a typed,
qualified table name. `BaseModeTableAddress` and `SheetModeTableAddress`
select one existing stable table identity within their physical containers.
Names, when supported, must resolve unambiguously; stable IDs are preferred.
An arbitrary sheet/range selector uses SheetRangeSource instead.

Open returns `OperationResult[Table]`:

```python
orders = client.open(existing_table_uri).require_value()
```

It resolves and inspects enough physical state to establish a canonical URI,
Table Mode, schema, and observed identity. It never treats a database URI, a
workbook, a worksheet, or an unbounded grid as a Table.

This requires an exact, typed, Receipt-bearing inspect/describe contract. The
current `TableInspection` contains column names and a schema fingerprint but
not full field types or revision evidence, so it is a migration input rather
than a conforming implementation. Connectors must implement
`table.inspect/2.0` (or a semantically equivalent versioned adapter) before
`client.open()` can expose a fully typed Table; the SDK never guesses types
from names or samples.

New destinations use a closed `TableDestination` union:

```python
DirectDestination(uri=...)

BaseModeDestination(
    container=...,
    table_name="orders",
)

SheetModeDestination(
    grid=...,
    anchor="A1",
    header=True,
)
```

- `DirectDestination` is for a URI that completely and deterministically
  identifies a not-yet-existing Table, such as a new local file.
- `BaseModeDestination` names a new record Table within a physical container.
- `SheetModeDestination` selects a grid and placement for a new bounded,
  header-aware Table; the grid or worksheet does not become the Table.

The public vocabulary never uses `relation` as a generic synonym for Table.
Provider-specific creation details require versioned typed destination
extensions, not an unvalidated options mapping. Credentials never appear in a
Table URI or destination value.

### Table interface

`Table` is immutable as a handle. Mutations change its physical target, not
the Python handle's identity.

```python
class Table:
    uri: TableURI
    mode: TableMode
    schema: pl.Schema
    observed_revision: Revision | None

    def inspect(...) -> OperationResult[TableInspection]: ...
    def capabilities(...) -> OperationResult[CapabilitySet]: ...

    def read(...) -> OperationResult[pl.DataFrame]: ...
    def read_page(...) -> OperationResult[pl.DataFrame]: ...

    def insert(frame, ...) -> OperationResult[int]: ...
    def update(frame, *, keys, ...) -> OperationResult[int]: ...
    def delete(*, where, parameters=None, ...) -> OperationResult[int]: ...
    def drop(...) -> OperationResult[None]: ...

    def transaction(...) -> TableTransaction: ...
    def time_series(descriptor) -> TimeSeriesView: ...
    def extension(extension_type) -> Extension: ...
```

There are no `*_with_receipt` variants. Receipts are always present on the
normal OperationResult. There is no public raw Connector object.

`observed_revision` is open-time evidence, not live mutable state. A mutation
never rewrites an immutable Table handle. Its Receipt supplies
`revision_after` when observable; callers obtain a refreshed handle with
`client.open(table.uri)` or a new observation through `table.inspect()` before
using optimistic concurrency again.

### Complete and page reads

`read()` is a Complete Read:

```python
result = table.read(
    columns=("order_id", "amount"),
    limits=ResourceLimits(...),
)
frame = result.require_value()
```

It follows provider pages internally and returns the complete bounded Table.
If the Table cannot be read completely under finite limits or a stable
snapshot, it fails. It never labels a truncated result complete.

The read Receipt declares the observed row-order contract. Base-mode storage
does not acquire a meaningful order merely because one provider happened to
emit rows in that sequence. Page Read requires a stable order bound into its
continuation token. A materialization whose destination makes row sequence
observable, including sheet-mode, rejects an unordered Table source; callers
use a totally ordered Query or collect an explicitly ordered DataFrame first.

`read_page()` is the only page-shaped read:

```python
page = table.read_page(
    max_rows=500,
    continuation=previous.continuation,
    columns=("order_id", "amount"),
)
```

The DataFrame is `page.require_value()`; opaque continuation state is
`page.continuation`. Although carried as a string, callers must treat it as an
opaque value. The SDK rejects a token that is malformed or not authenticated
and bound to the same Table identity, snapshot, schema, projection, and
Connector. A successful page is not a partial mutation outcome.

### Row insertion

```python
result = table.insert(frame, idempotency_key="load-42")
```

Insertion adds new rows only:

- it does not update, delete, upsert, replace, or recreate existing rows;
- it validates the input against the Table schema before mutation;
- it has no portable positional guarantee in base-mode;
- in sheet-mode, v1 inserts at the logical data-region tail; and
- target uniqueness or provider constraints may reject the whole insertion.

The normalized capability is `table.insert/1.0`. Existing provider-specific
"append" implementations may satisfy it only after conformance proves these
semantics. `table.append()` is not a public alias.

### Strict keyed update

```python
result = table.update(
    changes,
    keys=("order_id",),
    expected_revision=observed_revision,
    idempotency_key="update-42",
)
```

Update is update-only:

- at least one key column is required;
- every key exists in both input and target schema;
- input keys are non-null and unique;
- every input key matches exactly one target row;
- missing or multiply matching keys reject the whole operation;
- key fields are immutable;
- only supplied non-key columns are changed; and
- no unmatched input becomes an insertion.

The normalized capability is `table.update.keyed/1.0`. A Connector that
cannot provide all-or-fail submitted-key semantics must not advertise it.

### Predicate-required row deletion

```python
result = table.delete(
    where="status = :status AND created_at < :cutoff",
    parameters={"status": "cancelled", "cutoff": cutoff},
    expected_revision=observed_revision,
    idempotency_key="cleanup-42",
)
```

`where` is a required keyword-only argument. `table.delete()` is a Python type
error and can never accidentally remove every row. Intentional all-row
deletion uses an explicit portable predicate:

```python
table.delete(where=otc.all_rows())
```

The predicate may be a typed `PortablePredicate` or a SQL-like predicate
string with named parameters. SQLGlot parses string syntax, then OTC discards
the parser AST and lowers immediately to an owned `DeleteRows` plan. The v1
mutation-predicate grammar contains:

- field references and typed named parameters;
- `AND`, `OR`, and `NOT`;
- `=`, `<>`, `<`, `<=`, `>`, and `>=`;
- `IS NULL`, `IS NOT NULL`, `IN`, `BETWEEN`, and case-sensitive `LIKE`; and
- the closed deterministic scalar expressions shared with SQL Lite.

It rejects subqueries, aggregates, windows, arbitrary functions, external
references, provider syntax, and nondeterministic expressions. SQL
three-valued logic applies: only rows for which the predicate evaluates to
`TRUE` are deleted.

Base-mode deletes matching records. Sheet-mode deletes matching logical data
rows and compacts the bounded data region while preserving its header and
Table identity. A Connector must not approximate the operation with an unsafe
read/rewrite race. Unsupported Connectors fail capability preflight.

The normalized capability is `table.delete.where/1.0`. There is no `clear()`
method. `drop()` is the separate physical-resource operation.

### Drop

```python
result = table.drop(idempotency_key="retire-orders")
```

Drop removes the physical Table identified by the canonical Table URI. It does
not mean row deletion. The Receipt states the exact physical scope; dropping a
sheet-mode Table never implicitly drops its parent workbook or spreadsheet.
After a confirmed drop, operations through that handle fail `TABLE_NOT_FOUND`
or `STALE_TABLE_IDENTITY`.

The normalized capability is `table.drop/1.0`.

### Transactions

A new normalized transaction capability is exposed without giving callers a
Connector-wide mutable transaction. Existing low-level `TransactionalStore`
implementations are migration inputs, not proof of this stronger contract:

```python
tx = table.transaction(idempotency_key="refresh-42")
tx.delete(where=otc.all_rows())
tx.insert(frame)
result = tx.commit()
```

`TableTransaction` is a local builder bound to exactly one Table, expected
revision, finite limits, and idempotency identity. Its
`insert`/`update`/`delete` methods validate and accumulate normalized mutations
and bounded input snapshots without calling a Connector. Only `commit()`
performs capability preflight, acquires the credential lease, opens one
provider transaction, and returns `OperationResult[None]`. `abort()` is
idempotent, cleans local snapshots, and returns `OperationResult[None]` with no
physical Receipt when commit never began.

Nesting and use after commit/abort are rejected. An abandoned uncommitted
builder owns no provider transaction; Client close cleans its local snapshots.
A Connector without `table.transaction/1.0` fails at commit before data-bearing
I/O. Once commit dispatch begins, its unknown outcomes follow the normal
read-only reconciliation rule.

This permits an explicit atomic delete-all-plus-insert workflow when a caller
truly needs it; it does not create a `replace` API. Identity-changing
recreation is `drop()` followed by a separate `materialize()` operation and
therefore cannot masquerade as one transaction.

## Query and Evaluation Interface

### One deferred Query type

Portable relational and temporal queries use the same immutable public
`Query` type:

```python
@dataclass(frozen=True)
class Query:
    plan: PortablePlan
    sources: FrozenSourceBindings
    parameters: FrozenTypedParameters
    snapshot_constraints: FrozenSnapshotConstraints
    schema: pl.Schema
    limits: QueryResourceLimits
    consistency: ConsistencyPolicy
    pushdown: PushdownPolicy
    plan_hash: str
    definition_hash: str
```

The actual representation remains private. `Query` does not expose SQLGlot,
Polars LazyFrame, provider plan, credential, or mutable authorization objects.
Relational and temporal plan families remain distinguishable inside the
versioned Portable Plan union.

Source bindings are defensively copied into an immutable, ordered mapping.
Nested Query sources form a finite directed acyclic graph; construction
rejects direct or indirect cycles and duplicate aliases. `plan_hash` covers
only canonical Portable Plan meaning. `definition_hash` additionally covers
ordered aliases, source definitions and schemas, parameter names/types,
requested snapshot constraints, limits, consistency, and pushdown policy.
Runtime parameter values, DataFrame content, and physical snapshots are
deliberately bound at evaluation, revalidated against the declared schema, and
recorded in the ExecutionReceipt rather than pretending to be frozen at Query
construction.

Physical source bindings also preserve Client affinity. Every `Table` and
`SheetRangeSource` in one Query graph must belong to one Client, and that same
Client must evaluate the Query. DataFrames add no affinity; nested Queries
inherit the union of their physical-source affinities. Construction or
evaluation rejects a mixed-client graph with `CLIENT_AFFINITY_MISMATCH` before
physical I/O. The module-level convenience API may therefore evaluate only
queries whose physical handles came from its default Client. To move a query
definition to another Client, the caller reopens each canonical Table address
and rebinds each range with that Client, then constructs a new Query. OTC never
copies dispatch bindings, routes, authorization state, or credential leases
between Clients implicitly.

Parameter mappings are likewise defensively copied and typed. Query reprs and
diagnostics redact values classified as sensitive. At evaluation, Client
computes a private domain-separated binding fingerprint over their canonical
values, evaluated source content/snapshots, and the definition hash. That
fingerprint, not Query construction, protects idempotency against changed
bindings. The portable cross-implementation identity remains `plan_hash`.

### Preparing and collecting relational SQL

The pure preparation path is:

```python
query = otc.sql(
    """
    SELECT customer_id, SUM(amount) AS total
    FROM orders
    GROUP BY customer_id
    ORDER BY customer_id
    """,
    sources={"orders": orders_frame},
    parameters={},
    limits=SqlResourceLimits(...),
)
```

It parses, binds, types, validates, lowers, and returns a Query without
physical execution. Evaluation is explicit:

```python
result = client.collect(query)
frame = result.require_value()
```

Preparation is pure because every accepted source already exposes an exact
schema: a DataFrame and Query carry one, an opened Table carries its observed
schema, and a SheetRangeSource requires one in its declaration. Discovering a
range schema is a separate Client inspection operation, not hidden I/O inside
`otc.sql()`.

The convenience path performs those same two steps:

```python
result = client.sql(statement, sources=..., parameters=..., limits=...)
```

`client.sql()` returns `OperationResult[pl.DataFrame]`; it does not define a
different parser or executor.

`client.collect(source)` accepts any Table Source. Collecting a DataFrame
returns a bounded snapshot value with no physical Receipt. Collecting a Table
performs a Complete Read. Collecting a Query evaluates its Portable Plan.
Collecting an explicit sheet range performs one stable bounded grid
observation.

For exact multi-target fan-out from live sources, collect once and reuse the
resulting DataFrame:

```python
frozen = client.collect(query).require_value()
client.materialize(frozen, to=postgres_destination)
client.materialize(frozen, to=sheet_destination)
```

Re-executing a Query may observe new source snapshots and is not falsely
described as the same row set.

## Create-Only Materialization

### Interface

```python
result = client.materialize(
    source,
    to=destination,
    theme=None,
    theme_policy="require",
    limits=MaterializationLimits(...),
    consistency="recorded",
    verification="required",
    idempotency_key="create-orders-42",
)

table = result.require_value()
```

`source` is one Table Source and `result` is
`OperationResult[Table]`. Materialization always creates exactly one new
Table. After checking for an idempotent replay, an already-existing
destination is `rejected/not_started` with `DESTINATION_EXISTS`. It never
adopts, appends, updates, clears, replaces, or refreshes an existing Table.

There is no public `Table.create(schema)` method because `Table` already means
an existing physical resource. Schema-only creation is the same materialize
operation with a zero-row DataFrame source.

Copy and conversion are not separate SDK operations:

```python
source_table = client.open(source_uri).require_value()
created = client.materialize(source_table, to=destination)
```

The OperationResult contains ordered source and destination Receipts from the
one orchestration. There is no `CopyResult`.

### One Connector creation seam

Every destination Connector implements the same normalized internal operation:

```python
Connector.create_table(CreateTableRequest(...))
```

`CreateTableRequest` contains a resolved typed destination, Table Mode, exact
schema, one SDK-prepared bounded source carrier or certified complete provider
plan, materialization limits, idempotency binding, presentation policy, and
verification policy. It never contains caller SQL, a SQLGlot tree, a Polars
object, a local CLI frame path, or an untyped provider-options mapping.

The same seam handles zero-row schema creation and source-backed row creation.
It returns the created canonical physical identity, schema, mode, extent, and
Receipt evidence from which the SDK constructs `OperationResult[Table]`.
There are no Connector peers named `create_from_query`, `create_from_range`,
`copy`, `convert`, or `adopt`.

- A `BaseModeDestination` lowers to `create_table` on the SheetTable-backed
  base-mode adapter.
- A `SheetModeDestination` lowers to `create_table` on the Excelize-backed
  sheet-mode adapter and must create or register one bounded, header-aware
  Table rather than treating the worksheet as the Table.

Mode-specific placement and physical facts remain typed destination fields or
capability details. They do not create separate public creation APIs. A
Connector that cannot atomically establish the promised Table identity or
verify its bounds rejects preflight.

### Internal lifecycle

The public interface exposes one invocation. Internal phases are owned by the
SDK and destination Connector:

```text
validate source/schema/policy
  -> resolve/authorize destination
  -> preflight effective capabilities and limits
  -> reserve preliminary operation/key/destination identity
  -> bind schema and select exactly one physical strategy
  -> pin or capture every source snapshot
  -> atomically finalize payload identity and resolve replay/conflict
  -> check destination absence
  -> create/stage and commit through one destination Connector
  -> verify through a fresh observation
  -> assemble OperationResult[Table]
```

Source Connectors may provide snapshots, but exactly one destination
Connector owns target creation. Strategy selection occurs before data-bearing
execution. OTC never silently falls back to a different executor or mutation
strategy after data-bearing I/O begins.

A DataFrame source contributes a canonical schema/content identity but no
physical Receipt. A Table or sheet-range source contributes physical snapshot
evidence. A Query contributes its Portable Plan identity, complete per-input
snapshot evidence, and execution Receipt.

### Idempotency and destination existence

Every materialization has an idempotency key. The SDK generates one when
omitted for a single process attempt. Applications requiring restart-safe
replay or reconciliation supply a stable key.

The key binds at least:

```text
principal/tenant
operation and contract version
resolved deterministic destination key
source definition and evaluated snapshot/content identity
schema and materialization policy
```

Binding is a two-phase durable protocol because evaluated source identity is
not known at the initial reservation. Phase one reserves the caller key with
principal, operation/version, and deterministic destination and yields one
operation identity; concurrent users of that preliminary identity join or
wait. After source snapshots are captured, phase two atomically finalizes the
record with the complete payload fingerprint. An already-finalized identical
fingerprint joins or replays its recorded effect; a different fingerprint is
`IDEMPOTENCY_CONFLICT`. A phase-one record abandoned before target dispatch is
closed as `not_started` and may be reconciled or safely resumed under the same
key. It is never evidence that a target mutation occurred.

Same key and same payload joins or replays the same logical effect. Same key
with any changed bound field is `IDEMPOTENCY_CONFLICT`. One source materialized
to two destinations uses two physical idempotency identities.

The finalized durable idempotency lookup precedes the ordinary
destination-existence check and all target mutation. A same-key, same-payload
replay returns the original operation result even though its successfully
created destination now exists. A different key at that destination yields
`DESTINATION_EXISTS`; the same key with changed payload yields
`IDEMPOTENCY_CONFLICT`. Source observation may therefore occur before a
conflict is known, but target mutation never does.

Create-if-absent strength is capability-specific. A Connector must report
whether destination absence is atomically enforced, reserved through a durable
ledger, or protected by a compensating workflow. It must not advertise an
atomic guarantee for a check-then-create race.

### Source snapshots

All physical Query and materialization sources are resolved before target
mutation. Each source supplies a canonical URI when physical, exact schema,
revision or snapshot reference, content/schema identity, and one of:

- an immutable held snapshot;
- an immutable copied snapshot; or
- a stability proof validated again at commit.

A source that cannot remain stable for the operation is rejected before target
mutation. An explicit unavailable snapshot fails rather than silently reading
latest. Cross-provider `require_atomic` is unsupported unless all inputs share
a compatible snapshot domain; `recorded` records each stable snapshot without
upgrading it to cross-provider atomicity.

### Theme and style extension

`TableTheme` is future portable presentation intent passed to materialization;
it is not DataFrame metadata. `TableStyle` is future concrete presentation on
a physical Table.

The extension capability family is reserved as:

```text
table.theme.apply/1.0
table.style.inspect/1.0
table.style.apply/1.0
```

Capability details are property-specific: supported semantic regions,
properties, coercions, preservation guarantees, and verification behavior.
They are not booleans.

If a theme is supplied, the default `theme_policy="require"` rejects before
mutation unless the destination can realize and verify it. An explicit
`theme_policy="omit"` permits data materialization, emits a warning, and does
not claim presentation evidence. No current Connector may advertise these
capabilities until it passes the extension conformance suite.

Coordinate-level worksheet, row, column, range, formula, and workbook styling
remain a separate sheet-grid extension, not Table core.

## Operation Results, Errors, and Recovery

### One result envelope

```python
@dataclass(frozen=True)
class OperationResult(Generic[T]):
    value: T | None
    outcome: Outcome
    commit: CommitState
    verification: VerificationState
    receipts: tuple[Receipt, ...]
    continuation: str | None
    warnings: tuple[OperationWarning, ...]
    error: ErrorInfo | None

    def require_value(self) -> T: ...
```

`value` remains available for generic result inspection and may legitimately
be `None`, for example after `drop()`. Value-bearing examples use
`require_value()`, which returns `T` for static typing and raises a normalized
result-contract error if an outcome that should carry a value does not. It
does not create a result subclass or hide Receipts.

Outcome dimensions are independent:

```text
outcome:
  succeeded | planned | rejected | failed | partial | unknown

commit:
  not_applicable | not_started | not_committed | committed | partial | unknown

verification:
  not_applicable | passed | failed | skipped | unavailable
```

The state space is constrained, not an arbitrary cross-product:

| Outcome | Required commit state | Required evidence invariants |
| --- | --- | --- |
| `succeeded` | read/evaluation: `not_applicable`; mutation: `committed` | `error=None`; verification matches the operation policy |
| `planned` | nonmutation: `not_applicable`; mutation: `not_started` | no mutation Receipt; verification `not_applicable` or `skipped` |
| `rejected` | nonmutation: `not_applicable`; mutation: `not_started` | typed error; verification `skipped`; no effect Receipt |
| `failed` | nonmutation: `not_applicable`; mutation: `not_committed` or `committed` | typed error; committed failure retains effect and verification evidence |
| `partial` | `partial` | typed error and exact known partial-effect Receipts |
| `unknown` | `unknown` | typed error, verification `unavailable`, and reconciliation reference |

`continuation` is non-null only on a succeeded Page Read. An error is required
for every rejected/failed/partial/unknown result and absent for succeeded or
planned results. Each operation contract defines whether a successful value is
required; the SDK validates that invariant before exposing the result.

The generic envelope can represent provider operations that honestly permit
partial effects. An operation advertising all-or-nothing atomicity must never
emit `partial`.

Successful and explicitly planned operations return their OperationResult.
`rejected`, `failed`, `partial`, and `unknown` outcomes raise `OTCError`; its
`.result` preserves the complete envelope. A known physical Table may appear
as `error.result.value` when commit succeeded but verification failed. No
error path discards Receipts.

Typical materialization states are:

| Condition | Outcome | Commit | Verification |
| --- | --- | --- | --- |
| Invalid schema, unsupported capability, destination exists | `rejected` | `not_started` | `skipped` |
| Confirmed rollback | `failed` | `not_committed` | `skipped` |
| Committed target fails fresh verification | `failed` | `committed` | `failed` |
| Lost commit acknowledgement | `unknown` | `unknown` | `unavailable` |
| Fully verified | `succeeded` | `committed` | `passed` |

`commit=committed` does not imply success. A committed verification failure is
not retryable and must not repeat the mutation.

### Receipts

Receipts are immutable, credential-safe evidence variants. Common facts
include:

- operation, contract, Connector, and capability identities;
- safe physical Table URI and Table Mode;
- revision/snapshot before and after where available;
- source schema/content identity and emitted schema/content identity;
- affected rows and physical extent when observable;
- requested and observed resource bounds;
- execution location and certified pushdown facts;
- idempotency outcome and replay status; and
- verification observations.

Managed temporal stage, commit, readback, and abort Receipts remain distinct
receipt variants inside OperationResult; they do not create parallel public
result families.

### Reconciliation

An unsafe post-dispatch outcome supplies a typed reconciliation reference in
`ErrorInfo`. The ergonomic path is:

```python
try:
    client.materialize(source, to=destination, idempotency_key="run-42")
except otc.OTCError as exc:
    resolved = client.reconcile(exc.result)
```

Reconciliation is read-only. It uses the original destination, operation
version, idempotency key, operation identity, and Connector evidence. It may
resolve to committed, not committed, in progress, unknown, or expired.
Expired evidence is not proof of no commit.

Its public return is
`OperationResult[ReconciliationDisposition]`; it never returns an unstructured
provider status or performs a compensating mutation.

After an adapter invocation, OTC never retransmits a mutation until
reconciliation proves it did not commit. A timeout or missing response never
means rollback.

### Stable error families

The SDK normalizes at least:

- invalid target/URI, schema, predicate, SQL, descriptor, or configuration;
- unsupported capability or mode;
- authentication and authorization;
- destination exists, target not found, stale revision, and key conflict;
- duplicate/missing update key and idempotency conflict;
- resource limit, timeout, cancellation, and snapshot unavailable;
- execution failure, partial effect, uncertain mutation, and reconciliation
  unavailable; and
- readback/verification mismatch, protocol failure, and artifact integrity.

Messages and safe details never expose credential values, unrestricted SQL
literals, provider response bodies, secret-bearing URIs, or unrestricted
filesystem paths.

## OTC SQL Lite

### Three explicit SQL lanes

OTC exposes three non-interchangeable lanes:

1. relational OTC SQL Lite over explicitly named Table Sources;
2. temporal OTC SQL Lite over one descriptor-bound Time-Series View; and
3. explicit provider-native SQL against a database execution domain.

There is no automatic fallback between them. Portable SQL never discovers a
physical resource from text. Provider-native SQL never claims portable
semantics.

### SQLGlot ownership

SQLGlot is the parser, syntax-normalization, and policy-front-end only:

```text
SQL text
  -> exactly pinned SQLGlot parser
  -> OTC validation, binding, and type checking
  -> OTC-owned Portable Plan
  -> PolarsPlanMapper or certified full provider lowering
  -> OperationResult[DataFrame]
```

The SQLGlot AST is discarded immediately after lowering. It is never:

- public Python state;
- a wire or Connector request;
- the authorized or hashed Portable Plan;
- a production executor input; or
- a compatibility contract.

The exact SQLGlot version is pinned only after the normative SQL corpus passes.
Parser upgrades require the same corpus plus a reviewed canonical-plan diff.

### Relational profile v1

`otc.sql-lite.relational/v1` accepts exactly one deterministic `SELECT`,
optionally introduced by nonrecursive `WITH`, and this closed set:

- explicitly bound named sources and compile-time `*` expansion;
- projection, aliases, and `DISTINCT`;
- `WHERE` and `HAVING` with SQL three-valued logic, comparisons, `IS NULL`,
  `IN`, `BETWEEN`, and case-sensitive `LIKE`;
- `INNER` and `LEFT` equijoins whose condition is a conjunction of typed
  equality predicates;
- `GROUP BY` with `COUNT(*)`, `COUNT(expr)`, `COUNT(DISTINCT expr)`, `SUM`,
  `AVG`, `MIN`, and `MAX`;
- `CASE`, `COALESCE`, `NULLIF`, checked casts, numeric arithmetic, date/time
  literals, interval arithmetic, `ABS`, `ROUND`, `LOWER`, `UPPER`, `LENGTH`,
  `TRIM`, and `EXTRACT`;
- derived tables and uncorrelated scalar, `IN`, and `EXISTS` subqueries;
- `UNION ALL` between schema-compatible branches;
- `ROW_NUMBER`, `RANK`, `DENSE_RANK`, `LAG`, `LEAD`, and declared aggregates
  as window functions with `PARTITION BY` and `ORDER BY`; and
- a top-level `ORDER BY` whose keys prove a total output order, plus optional
  `LIMIT` or SQL `FETCH` under that order.

Aggregate windows accept only a whole-partition frame or
`ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`.

Every accepted v1 query must have that top-level total `ORDER BY`, except a
query statically proven to return at most one row. SQL without `ORDER BY` does
not inherit file, database, DataFrame, or encounter order. `LIMIT`, `FETCH`,
window ordering, and final output ordering all require snapshot-valid enforced
or validated uniqueness sufficient to break ties.

The profile rejects everything else, including:

- DDL, DML, multiple statements, and comments carrying directives;
- recursive CTEs and correlated subqueries;
- cross, right, full, lateral, and non-equality joins;
- `UNION DISTINCT`, `INTERSECT`, and `EXCEPT`;
- `OFFSET`;
- arbitrary functions, executable UDFs, procedures, and table functions;
- external readers, provider settings, provider casts, and extensions; and
- nondeterministic functions or output ordering.

Only named relational parameters are accepted:

```sql
WHERE booked_at >= :start AND booked_at < :end
```

Runtime values are typed separately and never interpolated into SQL text.

### Portable type and value semantics

The normative machine-readable semantic matrix is part of the profile. Core
v1 rules are:

| Family | Portable rule |
| --- | --- |
| null/boolean | SQL three-valued logic; empty text is not null |
| integer | checked range and widening before overflow |
| decimal | precision at most 38; overflow fails; half-even rounding |
| floating | finite `Float64`; NaN and infinity rejected at binding |
| text | UTF-8 Unicode code-point comparison; case-sensitive unless function says otherwise |
| binary | no implicit text coercion |
| temporal | dates are calendar values; timestamps require timezone and normalize to UTC |
| nested/object | list, struct, object, and opaque provider values unsupported in v1 |

There is no implicit text-to-number, text-to-date, or timezone guess.
`COUNT` returns `Int64`. Integer `SUM` returns `Decimal(38, 0)`.
`AVG(integer)` returns `Decimal(38, 6)`. Decimal SUM/AVG follow the declared
scale rules. Float reductions use the normative exact binary-superaccumulator
rule and round once to nearest-even so input order cannot change the result.

Ascending ordering defaults to `NULLS LAST`; descending defaults to
`NULLS FIRST`. Receipt or result canonicalization cannot repair ambiguous
query meaning.

### Source binding and consistency

SQL source names bind explicitly to Table Sources:

```python
query = otc.sql(
    statement,
    sources={
        "orders": orders_table,
        "rates": rates_frame,
    },
)
```

Text cannot name an unbound database object, file, worksheet, URL, or
provider object. Bindings capture exact schemas and safe source definitions;
execution captures physical snapshots and receipts.

`consistency="recorded"` requires one stable recorded snapshot per physical
source. `consistency="require_atomic"` requires immutable sources or one
compatible shared snapshot domain. It never claims atomicity across unrelated
providers.

### Bounds

Every query is fully bounded independently of SQL `LIMIT`:

```python
SqlResourceLimits(
    max_source_rows=...,
    max_source_bytes=...,
    max_total_input_rows=...,
    max_total_input_bytes=...,
    max_intermediate_rows=...,
    max_intermediate_bytes=...,
    max_output_rows=...,
    max_output_bytes=...,
    max_duration_ms=...,
    max_local_memory_bytes=...,
    max_spill_bytes=...,
)
```

`limits=None` selects a configured finite profile, never unbounded execution.
The v1 default is one million rows/256 MiB per source, two million rows/512
MiB total input and per intermediate, 100,000 rows/128 MiB output, 30 seconds,
512 MiB local memory, and 2 GiB confined spill.

A truncated source fails; OTC never computes an aggregate or join over an
unlabeled partial input. Unknown or excessive expansion fails closed before
the operator. V1 derives a conservative upper bound for every relational or
temporal intermediate from source bounds, uniqueness evidence, and operator
semantics. A join or other expanding operator whose worst-case rows or bytes
exceed the declared intermediate limits is rejected even when typical data
would be smaller. Runtime counters supplement this admission check at every
observable batch boundary; they are not used to excuse an unbounded opaque
operator.

### PolarsPlanMapper

`PolarsPlanMapper` is the normative local evaluator:

```text
OTC Portable Plan
  -> validated bounded operator graph
  -> confined Polars worker and LazyFrame implementation
  -> bounded worker collect
  -> verified Arrow carrier
  -> public Polars DataFrame
```

Local evaluation runs in a disposable, killable SDK worker rather than the
application process. Before collection, the SDK serializes already-authorized
and bounded inputs to SDK-owned Arrow IPC artifacts. The worker receives only
those artifacts and the validated plan: it has no Connector, credential,
network authority, or ambient file access. Its platform confinement profile
enforces the memory ceiling, private temporary-storage quota, CPU/thread
budget, and deadline outside Polars; the supervisor cancels and then kills a
worker that exceeds them, validates its bounded Arrow output, and cleans its
workspace. A platform that cannot demonstrate those controls in conformance
must reject SDK-local evaluation rather than advertise weakened limits.

Every Query evaluation emits one `ExecutionReceipt` containing the Portable
Plan/profile identity, enforced limits, observed work, output schema/order, and
`execution_location="sdk-local"` for a local mapper. Physical source Receipts,
when any, precede it. A DataFrame-only query therefore has no physical Receipt
but still has local execution evidence; collecting an unchanged DataFrame has
neither physical I/O nor a Query execution Receipt.

DataFrame sources are snapshotted into the same bounded Arrow input form.
Every physical Table or sheet range enters after one Complete Read, certified
full provider pushdown, or a Connector-supplied bounded snapshot-bound Arrow
batch stream. A local-file Connector may read CSV or Parquet internally and
supply that verified Arrow stream plus its physical Receipt; only the SDK
worker may lower SDK-owned Arrow IPC artifacts to Polars scans. Neither the
mapper nor worker opens a Connector path or receives a Connector-supplied
LazyFrame. Polars SQLContext is not the parser or semantic authority.

The planner selects exactly one execution strategy:

- `pushdown="allow"`: certified full provider lowering or local execution;
- `pushdown="forbid"`: local execution only; or
- `pushdown="require"`: one certified provider must execute the complete plan
  under every requested semantic and resource guarantee before source I/O.

Partial relational pushdown is deferred from v1 because cross-boundary
intermediate semantics, bounds, and evidence are not yet closed.

### DuckDB future seam

DuckDB is not a v1 dependency, capability, public engine option, SQL lane, or
fallback. The future reference is
`docs/reviews/2026-08-31-duckdb-local-executor-reference.md`.

Admission requires separate relational and temporal parity corpora, resource
enforcement, security/artifact review, packaging review, and benchmarks. A
future DuckDB mapper would accept only OTC Portable Plans and return the normal
OperationResult; it would not accept caller SQL or claim provider pushdown.

### Provider-native SQL

Native SQL is explicitly database-scoped:

```python
native = client.native_sql(database_target)
rows = native.query(
    statement,
    parameters=...,
    limits=NativeSqlResourceLimits(...),
).require_value()
affected = native.execute(
    statement,
    parameters=...,
    limits=NativeSqlResourceLimits(...),
    idempotency_key="native-load-42",
    verification="required",
).require_value()
```

It may address any object authorized within that database execution domain.
It is not a Table method, portable Query, or fallback. Parameters, dialect,
effects, and evidence remain provider-specific and use the normal
OperationResult envelope.

`native.query()` is a read-only capability, not merely a row-returning call.
It accepts exactly one statement and runs under provider-enforced read-only
authorization or transaction state. The dialect policy rejects DDL, DML,
procedures, multi-statements, locking clauses, external-I/O functions, and any
volatile or user-defined function the Connector cannot prove side-effect-free.
Its successful result therefore uses `commit=not_applicable`. If the Connector
cannot prove the statement and execution context read-only, it rejects before
dispatch; callers must use `native.execute()` and its mutation lifecycle.

Every native query or execution has finite effective limits, supplied either
explicitly or by a configured Client policy; an unbounded request is rejected
before dispatch. Before a statement that may mutate is dispatched, the
Connector must classify its effect, bind a stable operation identity and
idempotency key to the statement, typed parameter values, database target,
and limits, and declare its verification policy. The result uses the same
commit and verification states as every other physical mutation. A lost or
ambiguous acknowledgement produces `commit=unknown` with a durable
reconciliation reference and is never retried blindly. If a provider cannot
meet those effect, idempotency, evidence, and reconciliation requirements, it
must not advertise native mutation execution; read-only native query support
may still be advertised separately.

The capabilities are independently versioned as `native.sql.query/1.0`,
`native.sql.execute/1.0`, and, when supported,
`native.sql.transaction/1.0`. Advertising query never implies execute or
transaction support.

An optional `native.transaction()` extension owns database-scoped raw-SQL
transactions. Today's `TransactionalStore` implementations and concrete
SQLite/PostgreSQL transaction handles are migration inputs because they are
bound to a database target and can execute provider SQL. They must first gain
normalized lifecycle state, OperationResult/Receipt evidence, idempotency, and
unknown-outcome reconciliation; they do not already prove this extension or
the new one-Table `Table.transaction/1.0` contract.

## Time-Series Interface

### Orthogonal view

A Time-Series View binds one Table Source to an exact Temporal Descriptor:

```python
series = otc.time_series(source, descriptor)
```

It is not a third Table Mode. The descriptor declares disjoint event-time,
series-key, tag, value, and optional ingestion-time roles; timezone; precision;
ordering; and duplicate policy. The descriptor hash includes its canonical
schema contract.

Physical mutation methods require a physical Table source. Query helpers may
use a DataFrame, Query, Table, or explicit range when the descriptor can be
validated.

`series.describe()` returns `OperationResult[TimeSeriesDescription]`. The
description binds the exact descriptor and schema identities, canonical
physical target and observed revision when present, declared uniqueness
requirements, and effective temporal capabilities. It does not mint an
execution snapshot or prove an order-sensitive query against one; execution
binds those facts in its Receipts. A DataFrame-backed description has no
physical Receipt; a physical observation does.

### Typed temporal helpers

The following helpers build the existing Portable Temporal Plan operations
and return a deferred Query:

```python
series.scan_range(
    start, end, *, columns=None, tag_predicates=(),
    snapshot_reference=None, limits=None,
)
series.latest(
    *, at_or_before=None, columns=None, tag_predicates=(),
    snapshot_reference=None, limits=None,
)
series.as_of(
    at, *, columns=None, tag_predicates=(),
    snapshot_reference=None, limits=None,
)
series.aggregate(
    start, end, *, bucket, group_by=(), measures, tag_predicates=(),
    snapshot_reference=None, limits=None,
)
series.gap_fill(
    start, end, *, bucket, group_by=(), measures, tag_predicates=(), fills,
    snapshot_reference=None, limits=None,
)
series.sql(
    statement, *, parameters, snapshot_reference=None, limits=None,
)
```

`columns` lowers to the existing nonempty `projection`; `None` expands to the
descriptor's documented default projection during pure Query construction.
`group_by`, `measures`, `tag_predicates`, and `fills` lower without semantic
renaming to their current Portable Temporal Plan fields. A supplied
`snapshot_reference` becomes the Query's one-source snapshot constraint and
fails if unavailable; omission applies the Query consistency policy rather
than silently pinning an old observation.

Callers evaluate or materialize the returned Query through Client:

```python
latest = series.latest(at_or_before=cutoff)
frame = client.collect(latest).require_value()
created = client.materialize(latest, to=destination).require_value()
```

The plan family remains:

- `ScanRange`;
- `Latest`;
- `AsOf`;
- `BucketAggregate`; and
- `GapFill`.

Ranges are increasing half-open `[start, end)` intervals at exact descriptor
precision. Gap fill is aggregate-then-gap-fill with only null, constant,
LOCF, and linear interpolation rules over aggregate outputs. It is not generic
DataFrame null filling.

Series-key and tag filters remain the closed typed `eq`/`in` forms, and
aggregates may target only descriptor value fields. Fixed and calendar bucket
origin, offset, timezone, precision, and daylight-saving behavior remain
defined by the existing Portable Temporal Plan corpus; SQL syntax cannot
override them with provider-specific defaults.

Plan and execution preserve the current temporal invariants: descriptor and
plan hashes, required capability IDs, positive finite row/byte/duration bounds,
requested and observed ranges, snapshot reference, and truthful provider,
Connector, or SDK-local execution location. Output order is exact:

- ScanRange and AsOf use the complete observation key;
- Latest uses every series-key field;
- BucketAggregate uses every group key followed by bucket; and
- GapFill uses the corresponding aggregate group keys followed by bucket.

Duplicate policy `preserve` requires snapshot-valid unique observation
evidence whenever stored duplicates would otherwise tie. `replace-latest`
requires ingestion time plus a validated unique full replacement key of series
keys, event time, and ingestion time. Encounter order is never a tie-breaker.
An executor unable to prove the required order rejects rather than returning a
nondeterministic DataFrame.

### Temporal SQL profile

`otc.sql-lite.temporal/v1` is intentionally narrower than relational SQL. It
accepts one deterministic SELECT over exactly one descriptor-bound source and
maps exactly:

| SQL shape | Portable operation |
| --- | --- |
| bounded descriptor-field projection | `ScanRange` |
| documented `last(value, event_time)` latest shape | `Latest` |
| `time_bucket(...)` aggregates | `BucketAggregate` |
| `time_bucket_gapfill(...)` plus supported fill wrapper | `GapFill` |

`AsOf` remains a typed helper rather than a SQL shape.

Temporal SQL requires:

- PostgreSQL-style numbered typed parameters;
- exact `event_time >= $n AND event_time < $m` for scans and buckets;
- the documented one-sided `event_time <= $n` latest shape only;
- equality or `IN` filters on series keys and tags;
- explicitly and uniquely aliased `count`, `min`, `max`, `sum`, `avg`,
  `first`, and `last` aggregates;
- `time_bucket` or `time_bucket_gapfill`, with `locf`/`interpolate` only as
  supported wrappers over one gap-fill aggregate;
- mandatory deterministic output ordering; and
- a positive literal `LIMIT` within the independent resource profile.

It rejects `BETWEEN` for event-time bounds, comments, physical names, multiple
sources, joins, CTEs, subqueries, set operations, windows, HAVING, DISTINCT,
OFFSET, arbitrary functions or expressions, DDL, DML, provider settings,
unbounded range scans/aggregates/fills, and nondeterministic output. The only
bounded-result exception is Latest: the typed helper may omit
`at_or_before` under finite source/work limits, while temporal SQL requires its
documented one-sided cutoff predicate.

Latest groups by the complete series key. `first`/`last` are rejected under
duplicate policy `preserve`. `replace-latest` requires ingestion time and a
validated full replacement key. Ambient source encounter order is never
uniqueness evidence.

### Temporal writes

The existing time-series write vocabulary remains descriptor-specific:

```python
series = table.time_series(descriptor)
series.append(frame, idempotency_key="batch-42")
series.upsert(frame, idempotency_key="batch-43")
```

`series.append()` is intentionally not renamed to `insert()` because it
expresses temporal duplicate and observation semantics, not generic row
insertion.

- `preserve` retains observations;
- `reject` fails a duplicate logical observation key; and
- `replace-latest` requires ingestion time and makes the greatest-ingestion
  observation visible for a logical key.

Append never deletes or updates a stored observation. Upsert is unsupported
under `preserve`; under `reject` or `replace-latest` it must implement the
descriptor's full submitted-key behavior atomically. Input schema, descriptor,
content identity, bounds, and idempotency are validated before I/O.

Both operations return the normal OperationResult, with affected rows as the
value when known and temporal write evidence in Receipts. There is no public
`TemporalWriteResult` peer type.

### Managed temporal storage

Framework-facing managed storage remains available as a capability extension:

```python
stage: ManagedStage = series.storage.stage(
    frame,
    idempotency_key="batch-42",
).require_value()
snapshot: ManagedSnapshot = series.storage.commit(stage).require_value()
readback: OperationResult[pl.DataFrame] = series.storage.readback(snapshot)
aborted: OperationResult[AbortDisposition] = series.storage.abort(stage)
```

The value contracts are distinct from evidence:

```python
stage(...) -> OperationResult[ManagedStage]
commit(stage) -> OperationResult[ManagedSnapshot]
readback(snapshot) -> OperationResult[pl.DataFrame]
abort(stage) -> OperationResult[AbortDisposition]
```

`ManagedStage` is an immutable, credential-free, Client-affine handle bound to
one opaque stage reference, target, descriptor/schema/content identities,
operation/idempotency identity, and lease expiry. `ManagedSnapshot` is an
immutable handle bound to the committed target, descriptor/schema/content
identities, exact snapshot reference, and its independent retention contract
or deadline when finite. `AbortDisposition` is a closed enum: `aborted`,
`already_aborted`, `already_committed`, or `expired`. The extension
authenticates each opaque reference and rejects a foreign Client, target,
descriptor, schema, or content binding before dispatch. Commit rejects an
expired stage lease. Readback ignores the former stage lease and validates the
snapshot's own reference and retention contract; an unavailable retained
snapshot is a typed `SNAPSHOT_EXPIRED` or `SNAPSHOT_NOT_FOUND` failure. Abort
is the exception for stage expiry: when the durable stage ledger proves that
an authenticated stage lease expired without commit, it returns succeeded
with `AbortDisposition.expired` and performs no provider mutation. These
handles coordinate later calls; they are not Receipts and contain no claim
that an operation occurred.

Normative semantics remain:

- stage is invisible and content-bound;
- commit is idempotent on target, stage, and key;
- readback independently observes and verifies the committed snapshot; and
- abort is idempotent and reports a closed disposition.

Each call returns OperationResult. Existing managed stage/commit/readback/abort
receipt schemas remain the evidence variants that prove what occurred.
Commit's value identifies the snapshot that readback must observe; readback's
value is a DataFrame and its independent verification evidence is mandatory.
An abort after commit returns `already_committed` and never undoes the visible
snapshot.

`limits=None` selects the finite default temporal profile: 100,000 rows,
128 MiB, and 30 seconds. A configuration may replace it only with another
fully bounded profile.

## Capabilities and Extensions

### Static and effective capabilities

`client.connectors()` returns zero-I/O installed Connector metadata and static
capabilities. `table.capabilities()` returns effective capabilities for one
physical Table and may perform an authorized live probe. Results distinguish
static, probe-required, and observed claims.

Capability compatibility matches ID and supported version. Full wire strings,
process maps, provider registration, and receipts derive from one authoritative
`CapabilityIdentity`; providers do not maintain competing capability lists.

### Core capability family

The normalized application capabilities are semantic, not carrier-specific:

```text
table.inspect/2.0
table.read.complete/1.0
table.read.page/1.0
table.snapshot.read/1.0
table.materialize.schema/1.0
table.materialize.rows/1.0
table.insert/1.0
table.update.keyed/1.0
table.delete.where/1.0
table.drop/1.0
table.transaction/1.0
```

`table.read.polars`, `table.read.arrow`, `table.read.arrow.bounded/2.0`,
`base.read/1.0`, `sheet.read/1.0`, `base.inspect/1.0`, `sheet.inspect/1.0`, and
the old `table.inspect/1.0` are current compatibility identities, not final
application semantics. Adapters map them only after the normalized contract's
complete/page, exact-schema, Receipt, mode, and continuation conformance
passes. The current bounded read proves truthful `complete` versus `truncated`
extent but has no continuation request, so it is not yet Page Read.

Current `uri.resolve/1.0` becomes internal Client routing.
`table.write/1.0` is not carried forward as one semantic identity: after
conformance its create-if-absent behavior maps to materialization and its
append behavior maps to insertion, while replace is removed.
`table.execute/1.0` maps only to the explicit provider-native SQL extension.
Versioned adapters preserve old manifests and Receipts during migration rather
than changing these identities in place.

Capability details are typed and operation-specific. They include applicable
Table Modes, finite limits, snapshot support, key kinds, atomicity, visibility,
idempotency, continuation behavior, verification, and property subsets. A
boolean method-presence check is insufficient.

Pushdown and visibility are guarantees recorded on execution; they do not
create duplicate public methods.

The existing temporal capability identities remain versioned extension
contracts:

```text
timeseries.describe/1.0
timeseries.scan.range/1.0
timeseries.scan.range.pushdown/1.0
timeseries.lookup.latest/1.0
timeseries.lookup.asof/1.0
timeseries.aggregate.window/1.0
timeseries.aggregate.window.pushdown/1.0
timeseries.fill/1.0
timeseries.write.append/1.0
timeseries.write.upsert/1.0
storage.stage/1.0
storage.commit.idempotent/1.0
storage.visibility.atomic/1.0
storage.snapshot.read/1.0
storage.readback.verify/1.0
storage.abort/1.0
```

The read/query and managed-storage protocols exist today. The two temporal
write identities are declared but have no current normalized writer protocol
or conforming provider implementation; the SDK migration must add that
contract before any Connector advertises them. Ordinary `table.write` or
`Table.insert()` does not prove descriptor-aware append/upsert semantics.

The two current `.pushdown/1.0` identities migrate to typed execution-guarantee
details and Receipt facts under their parent temporal operations. Compatibility
adapters may decode them, but they are retired rather than retained as separate
public methods or permanent boolean capabilities.

### Optional extensions

Orthogonal surfaces use versioned typed extensions rather than widening every
Table:

- TableTheme/TableStyle presentation;
- sheet-grid coordinates, formulas, and workbook operations;
- provider-native SQL;
- managed temporal storage; and
- external processing such as dbt compile/run/cancel/artifact-read/readback.

External processing preserves current prepared-operation and artifact outputs
without creating another result envelope. Typed prepared handles, processing
summaries, and bounded artifact references or values occupy
`OperationResult.value`; Receipts carry their digests, producer identity,
bounds, and execution evidence. Compatibility adapters convert today's
`ExecutionResult.artifacts`, dbt compiled artifacts, manifests, run-results,
and artifact references into those typed values rather than dropping them or
mistaking payloads for Receipts.

An extension factory receives only the authorized Table/client context and
typed configuration needed for that capability. An unavailable extension
fails predictably; it never appears as a half-implemented object.

## Connector Discovery, Configuration, and Credentials

`open_table_connector.providers` is the authoritative entry-point group. Each
entry returns a zero-I/O immutable descriptor containing routes, modes,
capability identities, and one lazy factory ABI. Importing the SDK does not
import every provider or establish network connections.

Route collisions are deterministic configuration errors before provider
construction or credential resolution. Removing a provider distribution
removes its routes without preventing SDK import.

Configuration is application-independent under `otc.config/v1` and contains:

- enabled Connectors and safe typed provider configuration;
- credential references, never credential values;
- finite SQL, temporal, read, and materialization limit profiles;
- artifact workspace policy; and
- explicit capability/pushdown/verification policy defaults.

Configuration cannot invent provider import paths or executable commands.
Secrets are resolved through injected credential resolvers and excluded from
representation, equality, serialization, diagnostics, hashes, environment
inheritance, arguments, and Receipts. Credentials are leased for the shortest
operation scope; a live transaction pins its lease until commit or abort.

Applications may inject discovery, credentials, transports, clocks,
environment, and artifact workspaces through immutable Client configuration.
These are internal/test seams, not provider-shaped public options.

## Thin CLI Cutover

The new CLI parses arguments, calls the SDK, renders values/results, and maps
stable errors to exit status. It does not own provider discovery, credentials,
Arrow conversion, SQL parsing, copy orchestration, retries, or capability
policy.

Representative mappings are:

```python
# otc read SOURCE
table = client.open(source).require_value()
result = table.read()
render(result.require_value())

# otc read-range GRID --range A1:D100 --schema SCHEMA
source = client.bind_sheet_range(
    grid=grid,
    cell_range="A1:D100",
    header=True,
    schema=schema,
    schema_policy="validate_declared",
).require_value()
render(client.collect(source).require_value())

# otc import --from SOURCE --to DESTINATION
source_table = client.open(source).require_value()
result = client.materialize(source_table, to=destination)
render(result)

# otc insert TARGET --frame INPUT
table = client.open(target).require_value()
result = table.insert(read_polars_input(input_path))

# otc update TARGET --frame INPUT --key id
result = table.update(frame, keys=("id",))

# otc delete TARGET --where EXPRESSION --param name=value
result = table.delete(where=expression, parameters=parameters)
```

CLI deletion requires `--where`; an explicit `--all-rows` flag maps to
`otc.all_rows()` and is mutually exclusive with `--where`. There is no empty
predicate default.

Standard input and local frame paths are CLI codecs: the CLI decodes them to a
DataFrame before calling the SDK. `inspect --from -` remains a CLI-local Polars
schema/shape summary with no Table identity or physical Receipt; it does not
pretend stdin is a Table. An unbounded worksheet selector is rejected; the
caller must select an existing bounded sheet-mode Table or bind an explicit
bounded range through `client.bind_sheet_range()`. Legacy `--limit` never
slices after a full read. It maps to `read_page(max_rows=...)` only for a
continuation-conformant Connector and otherwise fails with migration guidance.

Compatibility mapping from the completed CLI refactor is:

| Old intent | New SDK operation |
| --- | --- |
| list installed Connectors | `client.connectors()` |
| read/inspect an existing Table | `client.open(...).require_value().read()/inspect()` |
| read an explicit bounded sheet range | `client.bind_sheet_range(...).require_value()`, then `client.collect(...)` |
| stdin/local frame source | CLI decode to DataFrame, then render, query, or materialize |
| inspect stdin | CLI-local Polars schema/shape summary; no `Table.inspect()` or physical Receipt |
| unbounded worksheet source | removed; select a Table or exact range |
| legacy post-read `--limit` | `read_page` only with resumable continuation support; otherwise rejected |
| `if_exists=error` create/import | `client.materialize(...)` |
| `if_exists=append` | `table.insert(...)` |
| `if_exists=replace` | removed; no normalized equivalent |
| convert to stdout/rendered frame | `client.collect(source)` plus CLI renderer/codec |
| convert/import to a physical Table | create-only `client.materialize(source, to=...)` |
| provider query read | explicit native SQL query |
| URI resolution | SDK internal routing |

Deprecated CLI aliases may survive one compatibility window, but they call the
same SDK path and may not preserve removed unsafe semantics.

## Complete Current Operation Mapping

| Current contract or declared operation | Final SDK surface |
| --- | --- |
| `URIResolver.resolve` | internal Client routing |
| current receiptless `TableInspector.inspect` | migration input for exact, Receipt-bearing `Table.inspect()` v2 conformance |
| current `ArrowTableReader` / `PolarsTableReader` | migration inputs for `Table.read()`; Arrow adapts after completeness/Receipt conformance, while Polars is converted at the compatibility boundary and is not the final Connector carrier SPI |
| current `BoundedArrowTableReader` | truthful bounded-prefix compatibility SPI; not `read_page()` until continuation input/replay is added |
| CLI-refactor `ConnectorAdapter.read/inspect/write` | transitional façade only; read/inspect route after Complete Read/exact-schema/Receipt conformance, while write additionally requires explicit materialize or insert intent |
| `TableWriter(if_exists=error)` | migration input for create-only `Client.materialize()` after idempotency/identity/verification conformance |
| `TableWriter(if_exists=append)` | `Table.insert()` after conformance |
| `TableWriter(if_exists=replace)` | no normalized operation |
| database-scoped `TransactionalStore` | migration input for optional `client.native_sql(...).transaction()` after lifecycle/result/evidence conformance; not normalized Table transaction proof |
| CLI convert to stdout | `Client.collect(TableSource)` plus CLI renderer/codec |
| CLI convert/import to a physical destination | `Client.materialize(TableSource, to=...)` |
| provider `ReadOptions(query=...)` row reads | migration input for `client.native_sql(...).query()` after Complete Read and evidence conformance |
| receiptless `SqlExecutor.execute` status/effect result | migration input for `client.native_sql(...).execute()` after commit/effect/Receipt conformance |
| `WritePreflightAdapter.preflight_write` | internal materialization/mutation capability preflight |
| `StepExecutor.prepare/run` | external-processing extension; not Table or Query core |
| planned portable relational SQL | `Query`, `otc.sql`, `client.collect/sql` |
| current minimal temporal describe | migration input for richer `TimeSeriesView.describe()` schema/descriptor/evidence conformance |
| temporal scan/latest/as-of/aggregate/fill | `TimeSeriesView` Queries |
| temporal append/upsert | physical `TimeSeriesView.append/upsert()` |
| managed stage/commit/readback/abort | `TimeSeriesView.storage` extension |
| temporal snapshot read/request binding | Query snapshot constraint and managed readback extension |
| process `cancel` | internal Client/Connector cancellation, not a Table method |
| dbt compile/run/cancel/artifact-read/readback | external-processing extension; artifact read and execution readback remain distinct operations |

The mapping is semantic, not a claim that every current Connector already
implements each capability. Unsupported capabilities remain unsupported until
their implementation and conformance evidence exist.

## Migration Strategy

This design follows the assumed completed CLI refactor and supersedes the old
SDK draft. Implementation planning must decompose it into independently
reviewable phases:

1. **Contract foundation:** add OperationResult, physical Table identities,
   destinations, normalized capabilities, predicates, and error/reconciliation
   types without changing CLI behavior.
2. **SDK core:** add Client, physical Table, DataFrame source binding,
   create-only materialization, complete/page reads, configuration, credentials,
   and compatibility adapters over current Connectors.
3. **Portable Query:** add the pinned SQLGlot front end, OTC Portable Plan,
   confined-worker PolarsPlanMapper, bounded execution, source snapshots,
   receipts, and SQL corpus.
4. **Normalized mutations:** implement `insert`, strict keyed `update`,
   predicate-required `delete`, `drop`, transactions, idempotency, and
   reconciliation capability by capability. Connectors that cannot prove a
   contract continue to reject it.
5. **Time-series consolidation:** make typed helpers and temporal SQL return
   Query, add normalized temporal write results, and adapt managed storage
   Receipts without changing Portable Temporal Plan semantics.
6. **Thin CLI:** replace CLI orchestration with SDK calls, add explicit
   insert/update/delete vocabulary, retain bounded compatibility aliases, and
   delete duplicate provider/configuration logic.
7. **Extensions and cleanup:** add future presentation extension contracts,
   remove deprecated TableRef/TableHandle/specialized-result surfaces, and
   publish independent packages and conformance evidence.

The detailed implementation plan is written only after this specification is
reviewed and approved.

## Testing and Conformance

### SDK interface tests

Tests use the same public interface as applications and cover:

- DataFrame, Query, Table, and sheet-range source normalization;
- direct and nested physical-source Client affinity and explicit rebinding;
- zero-row schema-only materialization;
- create-only destination conflicts, two-phase idempotency finalization,
  concurrent join, crash recovery, conflict, and replay;
- source snapshot stability and exact multi-target DataFrame fan-out;
- Complete Read versus Page Read and opaque continuation binding;
- insert-only, strict update-only, predicate-required deletion, all-row
  explicit predicate, drop, transaction, and stale-handle behavior;
- every OperationResult state, committed verification failure, uncertain
  commit, and reconciliation;
- confined local-worker row/byte/intermediate/memory/temp/deadline enforcement
  and cleanup after forced termination;
- provider-enforced read-only native query and mutating native execution
  separation;
- managed stage/snapshot handle binding and every abort disposition;
- client close, credential lease, artifact cleanup, and secret redaction; and
- thin CLI equivalence to direct SDK calls.

### SQL corpus

The vendored relational corpus contains accepted/rejected SQL, typed sources
and parameters, exact canonical Portable Plan JSON/hash, exact result schema,
normalized ordered output, resource expectations, and errors. It covers every
grammar family, type rule, null rule, numeric edge, timezone, determinism
proof, snapshot policy, and pushdown policy.

The mutation-predicate corpus separately covers parsing, parameter binding,
three-valued logic, rejected constructs, constant all-row intent, connector
lowering, affected rows, atomicity, and revision conflicts.

### Temporal corpus

The existing Portable Temporal Plan corpus remains authoritative and gains
Python Query/public-result cases for typed helpers, temporal SQL lowering,
descriptor/duplicate policy, bucket/DST behavior, gap fill, writes, managed
storage, bounds, and normalized Receipts.

### Connector conformance

A Connector advertises only capabilities whose shared suite passes. Tests
assert observable semantics and Receipts through Client/Table, not provider
internals. Recording-stub results do not become configured-live claims.

Initial implementation reality is recorded honestly:

- existing read/inspect support can adapt first;
- current generic write policies do not automatically prove insert/update/
  delete/materialize capabilities;
- Base schema-only creation, source-backed refresh, and distributed workflow
  guarantees are distinct;
- current sheet-mode worksheet creation does not yet prove bounded Table
  creation;
- current Feishu, Google Sheets, local file, and Maybe adapters do not all
  provide atomic predicate deletion; and
- no current Connector has a conforming TableTheme/TableStyle capability.

### Dependency and packaging gates

CI checks the package DAG, independent installation, public symbol inventory,
schema/wire compatibility, generated artifacts, all conformance corpora,
configured-live tiers where credentials exist, and CLI thinness. Provider
packages must not import SDK or CLI modules.

## Acceptance Criteria

The design is implemented only when:

1. applications use Polars DataFrames directly without a logical Table
   wrapper;
2. `Query` is the sole deferred public table-producing type;
3. `Table` is the sole physical table type and uses only base-mode or
   sheet-mode;
4. materialization is create-only and source evidence is preserved;
5. `insert`, strict keyed `update`, predicate-required `delete`, `drop`, and
   transaction semantics are capability-tested;
6. there is no public `Table.append`, `clear`, generic replace, copy result,
   TableRef/TableHandle/MaterializedTable, or specialized result hierarchy;
7. every evaluated or physical operation uses OperationResult with plural
   Receipts and safe reconciliation;
8. SQLGlot is parser/policy only and PolarsPlanMapper is the normative local
   evaluator;
9. relational SQL Lite, temporal SQL Lite, and provider-native SQL remain
   explicit non-fallbacking lanes;
10. all existing declared time-series helpers, writes, and managed lifecycle
    operations are represented without a second public result model;
11. the CLI contains no independent provider, credential, SQL, Arrow, copy,
    retry, or capability orchestration; and
12. OTS remains outside this implementation and can later consume the stable
    internal host port through the separate Rust adapter specification.
