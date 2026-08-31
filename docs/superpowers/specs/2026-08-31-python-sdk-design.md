# Polars-First OTC Python SDK

**Status:** proposed for review; active scope

**Date:** 2026-08-31

**Assumption:** the config-driven provider-owned CLI adapter plan is completed
before this refactor begins. This design preserves that plan's behavior while
moving application orchestration out of the CLI.

## Problem

Open Table Connector already has framework-neutral Connector protocols,
provider packages, plugin descriptors, receipts, portable time-series
contracts, and a command-line host. It does not yet have a single Python
application interface that composes those parts.

Consequently, Python applications such as FinClaw must repeat discovery,
routing, provider construction, credential handling, request construction, and
result conversion. The CLI also owns orchestration that belongs in a reusable
runtime. Completing the current CLI refactor improves provider ownership, but
still leaves the CLI as the only integrated application host.

OTC needs a Python-native SDK whose ordinary table value is a
`polars.DataFrame`. The SDK must support every current neutral table operation
and every portable time-series addition. The CLI must become a thin reference
application over that SDK.

The approved but unexecuted FinClaw design also defines a portable SQL Lite
language, while the OTS design defines a separate Timescale Core SQL slice.
Leaving the relational compiler in FinClaw would create two table runtimes and
deny other OTC applications the same facility. This design moves the generic
relational and portable temporal SQL frontends into OTC while leaving FinClaw
governance and OTS-specific semantics in their owning applications.

## Goals

- Provide a small, easy Python interface for reading, inspecting, writing, and
  copying tables.
- Use `polars.DataFrame` as the application-facing table type.
- Support every current table capability: discovery, inspection, ordinary and
  bounded reads, writes, copy, native SQL execution, and transactions.
- Add OTC SQL Lite, a read-only SQL:2016-derived relational profile that
  compiles to a typed portable plan and runs across Connector tables and
  in-memory Polars frames.
- Add an OTC SQL Lite temporal profile with TimescaleDB-familiar syntax that
  compiles to the existing `PortableTemporalPlan`.
- Support every current portable temporal capability: describe, range scan,
  latest, as-of, window aggregation, gap fill, append, upsert, and the managed
  stage/commit/readback/abort lifecycle.
- Preserve neutral and temporal receipts through explicit evidence-bearing
  variants.
- Centralize provider discovery, routing, configuration, credentials,
  capability preflight, lifecycle, and error normalization in the SDK.
- Keep physical-medium implementations independently installable and
  discoverable.
- Make the CLI a thin demonstration of the same public SDK used by other
  applications.
- Preserve an eventual language-neutral bridge without making the deferred OTS
  integration part of this implementation.

## Non-goals

- This design does not rewrite OTS or integrate it during the Python SDK
  refactor.
- It does not become a general dataframe transformation or SQL database
  framework. SQL Lite is a bounded, read-only query surface with a closed
  grammar and typed plan.
- The temporal SQL profile does not add joins, arbitrary expressions,
  unbounded temporal queries, or operations excluded by the portable temporal
  contract.
- SQL Lite does not claim full SQL:2016 compliance, accept executable UDFs,
  perform network/file discovery from SQL text, or emulate native provider
  extensions.
- It does not require every Connector to support every operation. Availability
  remains capability-based.
- It does not expose provider secrets through config documents, objects,
  receipts, logs, or errors.
- It does not make PyArrow part of the normal application interface. Arrow may
  remain an internal Connector and artifact carrier.
- It does not preserve CLI-shaped adapter options as the SDK's public request
  model.

## Domain Model

The design uses these terms consistently:

- **Application**: a caller such as the OTC CLI, FinClaw, a notebook, or a
  service.
- **SDK**: the Python application interface and runtime composition layer.
- **Client**: one configured, reusable SDK runtime with explicit lifecycle.
- **Table handle**: an application view of one routed physical table target.
- **Time-series handle**: a descriptor-bound temporal view of one table target.
- **SQL Lite**: OTC's closed, versioned, read-only SQL application language.
- **Portable relational plan**: the typed, provider-neutral plan compiled from
  the SQL Lite relational profile.
- **Native SQL**: explicitly provider-dialect SQL passed only to a Connector
  that advertises the physical SQL capability.
- **Connector**: a framework-neutral physical-medium implementation.
- **Provider plugin**: zero-I/O route metadata plus lazy factories for one
  Connector and its optional extensions.
- **Extension**: a capability family that requires types outside the base
  contract, initially SQL/query and time-series families.
- **Receipt**: immutable evidence about an observed or performed physical
  operation.
- **Binding**: framework-specific translation. No Binding belongs in the
  Python SDK; the future OTS Binding remains in OTS.

`Adapter` is not used for physical implementations or for the Rust transport
client. The existing CLI adapter layer is transitional and is removed from the
application architecture by this refactor.

## Architecture

```text
CLI / FinClaw / notebooks / Python services
                    |
                    v
        open_table_connector.sdk
          Client and resource handles
                    |
          SQL Lite compile/execute
          relational | temporal
                    |
        discovery, routing, credentials,
        preflight, lifecycle, receipts
                    |
                    v
       provider-owned Connector plugins
                    |
                    v
 CSV / Excel / SQLite / PostgreSQL / Sheets / Maybe / ...
```

The dependency direction is strict:

```text
cli --------> sdk --------> sql --------> timeseries
                 \          \-----------> contract
                  \----------------------> contract
                  \----------------------> timeseries

provider -----------------> contract
provider SQL lowering ----> sql ----------> contract
provider temporal code ---> timeseries ---> contract
```

The SDK may depend on the contract, SQL, and time-series distributions.
Providers must not depend on the SDK or CLI; a provider with portable-plan
pushdown may depend on SQL. The SQL package may depend on contract, time-series,
and Polars but not on SDK or providers. The contract must not import SDK, SQL,
providers, CLI, process host, or time-series. The time-series package may
depend on contract but not on SDK or SQL.

## Package Boundaries

### `open-table-connector-sdk`

A new `packages/sdk` distribution exposes `open_table_connector.sdk` and owns:

- `Client` and the module-level convenience functions;
- immutable SDK configuration models and loading;
- credential resolver interfaces and scoped credential leases;
- provider and extension discovery;
- deterministic URI and path routing;
- lazy provider activation and provider lifecycle;
- capability preflight and protocol selection;
- application-facing request options and result types;
- SQL source binding, execution-policy selection, and composite receipts;
- table copy orchestration;
- Arrow-to-Polars conversion at the application boundary;
- stable error normalization; and
- default-client lifecycle for one-shot convenience calls.

It does not own physical codecs, provider-specific transports, CLI rendering,
or OTS semantics.

### `open-table-connector-contract`

The contract distribution remains the provider-facing SPI. Its small neutral
protocols continue to describe URI resolution, inspection, Arrow and Polars
reads, bounded reads, writes, provider-native SQL execution, and transactions.

Operation requests are upgraded to carry a complete `TableRef`, rather than
only a URI, wherever a physical relation or sheet selection affects the
operation. The contract adds a Polars counterpart to the bounded Arrow result
and corrects transaction begin to return a real transaction handle.

`TableInspection` is upgraded to carry an exact canonical Arrow schema and
declared unique-key metadata, not only column names and a schema fingerprint.
The SDK exposes the application view as a Polars schema. A provider may report
a schema obtained from authoritative metadata or a complete bounded
observation, never from an unlabelled sample. SQL preparation depends on this
exact typed description.

Provider-native row queries gain a `NativeSqlQueryExecutor` protocol beside
the existing status-oriented `SqlExecutor`. Its request remains
database-target and dialect-specific; its result carries canonical Arrow table
data and native query evidence. This physical capability has no dependency on
the portable SQL package.

The current CLI-shaped `AdapterEndpoint`, `AdapterOptions`,
`ConnectorAdapter`, and `WritePreflightAdapter` are not promoted to SDK types.
They become migration-only compatibility types and are removed after the CLI
cutover. SDK calls route to the existing capability-specific Connector
protocols.

The contract gains only generic plugin-extension registration primitives. It
does not import SQL or temporal types.

### `open-table-connector-sql`

A new `packages/sql` distribution exposes `open_table_connector.sql` and owns
both OTC SQL Lite profiles:

- `otc.sql-lite.relational/v1`, derived from a closed SQL:2016 subset;
- `otc.sql-lite.temporal/v1`, source-compatible with the portable slice of
  Timescale Core SQL;
- a pinned lexer/parser dependency used only to obtain a syntax tree;
- immediate validation and lowering into OTC-owned typed plan nodes;
- `PortableRelationalPlan`, typed parameters, schema binding, canonical plan
  serialization, and plan hashing;
- compilation of the temporal profile into the existing
  `PortableTemporalPlan` rather than a second temporal plan;
- bounded Polars expression/operator lowering for local relational execution;
- provider-lowering protocols and language conformance fixtures.

The broad third-party parser AST is never an API, wire format, authorization
result, or execution plan. Successful parsing does not imply acceptance. The
package converts only whitelisted nodes into its closed typed algebra and then
discards the parser AST.

The relational algebra is deliberately closed and deep: scan, join, filter,
aggregate, project, sort, window, slice, and `UNION ALL` nodes plus nested
subplans and a closed typed expression union. Nonrecursive CTEs are named DAG
subplans rather than a provider feature. Providers consume the typed algebra
when they implement optional pushdown; they never receive portable SQL text.

The SQL package does not discover providers, resolve credentials, or know
FinClaw stages and OTS Add-ons. The SDK supplies already-authorized logical
relation bindings.

It also owns `SqlCompileError` and a stable closed `SqlErrorCode` set covering
invalid syntax, unsupported features, name resolution, type mismatch,
parameter binding, unavailable exact schema, nondeterministic query shape,
unknown resource estimate, and required-pushdown failure. Physical access and
runtime-limit failures retain the existing `ConnectorError` codes.

### `open-table-connector-timeseries`

The existing distribution continues to own descriptors, portable plan models,
temporal protocols, resource bounds, capability identities, receipts, and
conformance semantics. The SQL package may compile its temporal language
profile into these types. The SDK adapts the neutral seam into Polars-first
resource handles; it does not duplicate the temporal plan language.

The extension adds a typed temporal provider factory context and binding so
provider-owned temporal executors and managed stores can be opened without the
process host's configuration document.

### Provider packages

Each provider owns its Connector, temporal executor/store when applicable,
optional native transport dependencies, validation, and plugin declaration.
There is one application-independent provider registration. Provider-specific
CLI and process adapter registrations are no longer authoritative runtime
seams.

### `open-table-connector-cli`

The CLI owns only:

- argument parsing and usage errors;
- translation of CLI syntax into SDK calls;
- stdout/stderr rendering;
- destination presentation formats for stdout; and
- process exit-code policy.

It does not discover providers, resolve credentials, route endpoints,
construct Connectors, enforce capability semantics, convert Connector result
types, or orchestrate copies.

## Public Python Interface

### One-shot convenience API

The common path is deliberately direct:

```python
from open_table_connector import sdk as otc

frame = otc.read("csv:///data/orders.csv")
write_result = otc.write(
    "postgres://warehouse",
    frame,
    relation="orders",
)
inspection = otc.inspect("postgres://warehouse", relation="orders")

with otc.Client() as client:
    copy_result = client.table("csv:///data/orders.csv").copy_to(
        client.table("postgres://warehouse", relation="orders")
    )
```

`read()` always returns a `polars.DataFrame`. `write()` returns a
`TableWriteResult`; `copy()` returns a `CopyResult` containing both receipts
and row counts. There is no mutable `last_receipt` state.

The module functions use one lazily constructed, process-local default
`Client`. Construction is thread-safe, provider activation remains lazy, and
an explicit `close_default_client()` is available to test runners and hosts
that reload configuration. Applications that need deterministic injection,
multiple configurations, or explicit lifetime use `Client`.

### Configured client

```python
from open_table_connector.sdk import Client

with Client.from_config("/etc/open-table-connector/config.toml") as client:
    table = client.table("feishu://APP_TOKEN/TABLE_ID")
    result = table.read_with_receipt(columns=("symbol", "price"))

    frame = result.frame
    receipt = result.receipt
```

`Client` accepts string targets, `os.PathLike` values, and validated
`TableURI` values. Bare paths are normalized by the SDK before routing.
Provider credentials are never encoded into a `TableURI`.

### Table references and handles

`client.table(...)` normalizes its arguments into an immutable `TableRef` and
returns an immutable `TableHandle`:

```python
orders = client.table("postgres://warehouse", relation="orders")
worksheet = client.table(
    "gsheets://SPREADSHEET_ID",
    sheet="Orders",
    cell_range="A1:D500",
)
local = client.table("orders.data", format_hint="csv")
```

`TableRef` is the canonical answer to the current ambiguity between a database
URI and a table, or a spreadsheet URI and a worksheet/range. Its closed model
is:

```python
TableRef(
    uri=TableURI("postgres://warehouse"),
    selection=BaseSelection(relation="public.orders"),
)

TableRef(
    uri=TableURI("gsheets://SPREADSHEET_ID"),
    selection=SheetSelection(sheet="Orders", range="A1:D500", header_row=1),
)
```

The values mean:

- `TableURI`: the credential-free provider address used for routing;
- `BaseSelection`: an optional database or logical relation within it;
- `SheetSelection`: worksheet, optional range, and header-row convention; and
- `TableRef`: the complete physical table reference passed to every operation.

Convenience keyword arguments construct these values; ordinary callers do not
need to instantiate them. A cell range requires a sheet selection. An explicit
local format hint selects a provider-owned codec before reference construction
and is not retained as a universal stdout format field. If a URI and typed
selection both identify the same property, they must agree or fail with
`INVALID_URI`.

Read projection, key/record identity hints, limits, timeout, conflict policy,
and idempotency remain in typed operation-specific options. Feishu field
projection, for example, is read projection rather than part of its physical
address. Provider-owned codec options such as delimiter or encoding use a
provider-owned typed option object. Provider-specific needs that cannot be
expressed by the closed reference require a versioned typed extension, not an
unvalidated mapping. CLI presentation choices never enter a table reference or
Connector request. Existing URI spellings that already contain a table or
sheet normalize to the same reference.

The table surface is:

```python
table.inspect(*, limits: ResourceLimits | None = None) -> TableInspection
table.read(*, columns=None, limits: ResourceLimits | None = None) -> pl.DataFrame
table.read_with_receipt(
    *, columns=None, limits: ResourceLimits | None = None
) -> PolarsReadResult
table.read_bounded(
    *,
    max_rows,
    continuation=None,
    columns=None,
    limits: ResourceLimits | None = None,
) -> BoundedPolarsReadResult
table.write(frame, *, if_exists="error") -> TableWriteResult
table.copy_to(destination, *, if_exists="error", ...) -> CopyResult
table.capabilities() -> CapabilityManifest
table.transaction() -> Transaction
table.sql(
    statement,
    *,
    relations=None,
    parameters=None,
    limits: SqlResourceLimits | None = None,
    pushdown="allow",
    consistency="recorded",
) -> pl.DataFrame
table.sql_with_receipt(
    statement,
    *,
    relations=None,
    parameters=None,
    limits: SqlResourceLimits | None = None,
    pushdown="allow",
    consistency="recorded",
) -> SqlQueryResult
```

Evidence-bearing complete reads reuse the existing `PolarsReadResult`, which
contains `frame: polars.DataFrame` and `receipt: NeutralReceipt`; the SDK does
not create a parallel result model. The contract adds
`BoundedPolarsReadResult(frame, receipt)` alongside the existing bounded Arrow
result.

`read()` represents an ordinary complete read. `read_bounded()` is the
complete current bounded-read operation. Its result contains a Polars frame
and the existing
`BoundedReadReceipt`, including `complete`/`truncated` extent and any opaque
next token. The contract gains an optional continuation token so a provider
that emits one can resume it; callers must not inspect or synthesize tokens.

`limits=ResourceLimits` sets broader provider work bounds. An ordinary read may
be used only when the requested safety contract can still be guaranteed. The
SDK must never truncate after unbounded materialization and label that a
bounded read, or attach a normal receipt implying completeness to a truncated
result. If the selected Connector cannot meet the bound, it fails with
`UNSUPPORTED_CAPABILITY` before I/O. CLI `--limit` maps to
`read_bounded(max_rows=...)` and renders only its frame when row output is
requested.

`copy_to()` is the SDK operation behind both CLI `convert` and `import`. It
reads once and writes once, preserves source and destination receipts, applies
only destination-owned field policy, and preflights the destination before
source I/O. Whether a destination is local is a Connector fact, not an SDK
restriction.

### Native SQL and transactions

Provider-dialect SQL is opened from an explicit provider execution target so it
cannot be confused with portable `table.sql()` or imply relation-level
sandboxing:

```python
native = client.native_sql("postgres://warehouse")
native.query(
    statement,
    parameters=(),
    *,
    limits: ResourceLimits | None = None,
) -> pl.DataFrame
native.query_with_receipt(
    statement,
    parameters=(),
    *,
    limits: ResourceLimits | None = None,
) -> NativeSqlQueryResult
native.execute(
    statement,
    parameters=(),
    *,
    limits: ResourceLimits | None = None,
) -> ExecutionResult
```

`client.native_sql()` accepts only a database/engine target with no relation,
sheet, or range selection. The resulting `NativeSqlHandle` is scoped to the
provider execution domain, not one table, and documentation must state that
its SQL may address any object authorized by those credentials. Ordinary
tabular-file providers, sheets, and in-memory targets reject native SQL;
database targets such as SQLite remain eligible. Native `query()` is
row-producing; native `execute()` returns status, affected rows, and artifacts.
This distinction replaces provider-specific `read(query=...)` options.

Native statements and parameters remain caller-prepared and dialect-specific
and are available only when the Connector advertises its provider-native SQL
capability. They are not portable, are not a fallback for SQL Lite, and never
enter a portable relational or temporal plan. `NativeSqlQueryResult` contains
a `NativeSqlReceipt` with safe statement/parameter hashes, provider dialect and
capability identity, provider evidence, and output schema/content identity; it
never claims a portable plan identity.

Transactions are context-managed:

```python
with client.table("postgres://warehouse", relation="orders").transaction() as transaction:
    transaction.write(first_frame, if_exists="append")
```

The v1 table transaction surface contains table operations only. Native SQL
transactions require a future database-scoped transaction handle rather than
smuggling database-wide authority through a relation-scoped transaction.

Successful context exit commits. An exception aborts. Explicit
`commit()`/`abort()` remain available, are idempotency-checked, and close the
transaction. Operations on a closed transaction fail with a stable conflict
error. Connectors without transactional capability fail before data I/O.

This requires correcting the provider contract to match the transactional
implementations: `begin(reference)` returns a transaction handle; write and
table operations are invoked on that handle; and the handle owns commit, abort,
and close. A hidden mutable Connector-wide transaction is not the SDK
seam. A transaction pins its provider instance and credential lease until it
ends. Nested transactions are unsupported in version 1.

URI resolution is SDK infrastructure, not a separate common application
operation. Advanced tooling may inspect safe route and capability metadata but
does not receive provider credentials or raw resolved resources.

## Complete Current Table-Operation Mapping

| Current surface | SDK surface | Notes |
| --- | --- | --- |
| provider/CLI `list` | `client.connectors()` | `ConnectorInfo` only; zero-I/O |
| `CapabilityManifest` | `table.capabilities()` | Static versus live is explicit |
| `URIResolver.resolve` | internal routing/activation | Provider resource never leaks by default |
| `TableInspector.inspect` | `table.inspect()` | Request upgraded from URI to `TableRef` |
| `PolarsTableReader.read_polars` | `table.read*()` | Preferred path; existing result reused |
| `ArrowTableReader.read_arrow` | `table.read*()` | Provider SPI; converted once by SDK |
| `BoundedArrowTableReader` | `table.read_bounded()` | Adds Polars result; preserves extent/token |
| `TableWriter.write` | `table.write()` | Input is Polars |
| CLI `convert`/`import` | `table.copy_to()` / `client.copy()` | One SDK orchestration path |
| planned FinClaw SQL Lite | `client.sql*()` / `table.sql*()` | Shared portable relational path |
| provider SQL query reads | `client.native_sql(target).query*()` | Database-scoped provider SQL |
| `SqlExecutor.execute` | `client.native_sql(target).execute()` | Native statement/status path |
| `TransactionalStore` | `table.transaction()` | Context-managed begin/commit/abort |

Prepared external processing remains available through capability extensions,
not `TableHandle`. The generic `StepExecutor` seam has no current table
provider implementation, and dbt compile/run/cancel/readback is a processing
extension rather than a table operation. The SDK plugin model can host it
without pretending it is SQL or dataframe I/O.

No currently implemented or declared table operation is dropped. The SDK may
deprecate duplicate CLI vocabulary after compatibility tests prove equivalent
behavior.

## OTC SQL Lite

### One portable language over named table values

`otc.sql-lite.relational/v1` is the application-facing relational language.
It is a deliberately closed, read-only subset derived from SQL:2016; the name
does not claim general SQL:2016 conformance. Its semantics do not vary by
physical medium.

The query is client-level because one statement may join several named inputs:

```python
import polars as pl

result = client.sql(
    """
    SELECT o.customer_id,
           SUM((o.amount + COALESCE(a.amount, 0)) * r.multiplier)
               AS reporting_amount
    FROM orders AS o
    LEFT JOIN rates AS r ON o.currency = r.currency
    LEFT JOIN adjustments AS a ON o.order_id = a.order_id
    WHERE o.booked_at >= :start
    GROUP BY o.customer_id
    ORDER BY reporting_amount DESC, customer_id
    """,
    relations={
        "orders": client.table("/data/orders.csv"),
        "rates": client.table("/data/rates.xlsx", sheet="FX"),
        "adjustments": pl.DataFrame(...),
    },
    parameters={"start": start},
)
```

The public `SqlSource` union is `str | os.PathLike | TableRef | TableHandle |
polars.DataFrame | SqlRelationBinding`. Strings, paths, and references
normalize through the calling client. A handle must belong to that same client.
A dataframe is already materialized and receives a canonical in-memory
identity. `SqlRelationBinding` wraps one of those values with an optional exact
schema, declared unique key, immutable snapshot identity, and provider-owned
typed read options. Arbitrary `polars.LazyFrame` values are rejected in v1
because they can hide external scans or executable UDFs outside OTC bounds;
the evaluator may still use lazy operations internally.

SQL identifiers resolve only through the explicit `relations` mapping. SQL
text cannot contain a URI, open a file, discover a database table, resolve
credentials, or access the network. This also makes module-level
`otc.sql(..., relations={"orders": "/data/orders.csv"})` a real one-shot call.
FinClaw can resolve and authorize governed Artifacts first and expose only
their logical names to OTC.

The complete client surface is:

```python
client.sql(
    statement,
    *,
    relations,
    parameters=None,
    limits: SqlResourceLimits | None = None,
    pushdown="allow",
    consistency="recorded",
) -> pl.DataFrame
client.sql_with_receipt(
    statement,
    *,
    relations,
    parameters=None,
    limits: SqlResourceLimits | None = None,
    pushdown="allow",
    consistency="recorded",
) -> SqlQueryResult
client.prepare_sql(
    statement,
    *,
    relations,
    parameters=None,
    preparation_limits: ResourceLimits | None = None,
    pushdown="allow",
    consistency="recorded",
) -> PreparedRelationalQuery

prepared.estimate -> SqlResourceEstimate
prepared.admission -> SqlAdmissionStatus
prepared.plan -> PortableRelationalPlan
prepared.authorize(
    *,
    limits: SqlResourceLimits | None = None,
) -> AuthorizedRelationalQuery
AuthorizedRelationalQuery.execute() -> pl.DataFrame
AuthorizedRelationalQuery.execute_with_receipt() -> SqlQueryResult
```

Module-level `otc.sql()` and `otc.sql_with_receipt()` delegate to the default
client. `table.sql()` is sugar for the same client call with that handle bound
as the reserved relation `this`; SQL uses `FROM this`. An optional `relations`
mapping can add other explicitly named inputs but may not redefine `this`.
There is one compiler and evaluator behind all three entry points.

Relational parameters use named placeholders such as `:start` and a mapping of
typed scalar values. Text interpolation is never an API. SQL Lite is
read-only: its result is an ephemeral Polars dataframe. Persisting a result is
an explicit `write()` or `copy_to()` operation with its own receipt.

`prepare_sql()` binds source schemas, parameter values and types, source
identities, pushdown intent, and consistency intent into an immutable
`PreparedRelationalQuery`. `preparation_limits` bound only schema discovery and
materialization needed to prepare sources; they are not an execution
authorization. An explicit preparation envelope must contain positive finite
row, byte, and duration bounds. A direct `prepare_sql(...,
preparation_limits=None)` derives those bounds from the client's configured
`DEFAULT_SQL_LIMITS_V1` replacement. A one-shot `sql()` or
`sql_with_receipt()` first resolves its exact selected `SqlResourceLimits` and
derives preparation bounds from that same profile. If no complete bounded
preparation envelope can be formed, preparation fails before source I/O. The
object contains the typed plan, required logical inputs, expected schema
fingerprints, parameter schema, conservative resource estimate, admission
status, exact statement hash, and canonical plan hash.

Pushdown and consistency are preparation-time safety inputs because
preparation may need to read and retain a complete source. With
`pushdown="require"`, OTC must compile from authoritative schema metadata and
preflight one certified provider execution domain before opening any source
data stream; a source that requires row materialization merely to discover its
schema is therefore ineligible. With `consistency="require_atomic"`, OTC must
prove all inputs immutable or acquire one compatible provider's shared
snapshot before any such materialization. Independently materialized mutable
sources can never be upgraded to atomic later. `consistency="recorded"`
materialization retains the exact pinned or stability-proven source described
below. The prepared object owns any retained frame, snapshot lease, and
confined spill until it is closed; it is a context manager. Choosing a
different pushdown or consistency policy requires a new preparation.

`authorize()` binds only the approved execution envelope, without recompiling
or changing the semantic plan hash or preparation-time policies. It returns an
`AuthorizedRelationalQuery` only when the estimate and required evidence fit
that envelope. The authorized handle retains its normalized bindings and
calling client, so execution rejects a closed client, missing or changed
source, schema drift, or required pinned-identity mismatch before physical
work. This gives governed hosts a real plan-estimate-authorize-execute seam.
One-shot methods perform the same preparation and authorization internally,
using their resolved policies and limits, and execute once.

`SqlResourceEstimate` records each source and operator's conservative row/byte
upper bound, duration/memory/spill assumptions, eligible execution domains, and
the evidence behind each bound. `SqlAdmissionStatus` carries bounded fields,
unknown reasons, and the minimum additional constraint or provider evidence
needed. Syntax, typing, and unauthorized schema-preparation failures still
raise immediately; an unknown or over-default execution estimate remains
inspectable so a governed host can request a different envelope. Authorization
fails with `SqlErrorCode.RESOURCE_ESTIMATE_UNKNOWN` while any expanding node
lacks a finite enforceable bound.

### Exact source binding and portable types

Every logical input becomes an immutable `RelationBinding` containing its
normalized source, exact canonical `SqlSchema`, schema fingerprint, declared
unique constraints, read options, and any pinned snapshot identity. A
DataFrame supplies its schema directly. A table supplies it through the typed
inspection contract or an explicit caller schema that the provider validates
against every row it reads.

Sampled CSV or worksheet inference is never authoritative. When no declared
schema exists, preparation may perform one complete bounded, receipted read to
infer and materialize the input, then retain that exact frame in the prepared
query. If complete preparation is not authorized, schema binding fails before
query execution. A later execution never silently re-infers a different type.

`otc.sql-lite.relational/v1` includes a normative, machine-readable semantic
matrix at `specification/sql-lite/relational-v1-semantics.yaml`. The matrix is
part of the language version and defines source coercion, implicit promotion,
explicit casts, expression and aggregate result types, overflow, rounding,
nulls, identifiers, timestamps, intervals, comparison, and ordering. The core
v1 rules are:

| Family | Portable rule |
| --- | --- |
| null/boolean | SQL three-valued logic; empty text is not null |
| integer | signed/unsigned inputs are range-checked; arithmetic widens before overflow |
| decimal | precision is at most 38; overflow fails; rounding is half-even |
| floating | operations use finite IEEE-754 `Float64`; NaN and infinity are rejected at binding |
| text/binary | UTF-8 text uses Unicode code-point comparison; binary has no implicit text cast |
| temporal | dates are calendar values; timestamps require a timezone and normalize to UTC |
| nested/object | list, struct, object, and opaque provider values are unsupported in v1 |

There is no implicit text-to-number, text-to-date, or timezone guess. Provider
blanks become null only when the bound source schema says they are missing;
the empty string remains a value. `COUNT(*)`, `COUNT(expr)`, and
`COUNT(DISTINCT expr)` return `Int64`; count expressions ignore nulls.
`SUM(integer)` returns `Decimal(38, 0)` and `SUM(Decimal(p, s))` returns
`Decimal(38, s)`. `AVG(integer)` returns `Decimal(38, 6)` and
`AVG(Decimal(p, s))` returns `Decimal(38, max(s, 6))`; overflow fails rather
than changing type. Floating sums and averages return `Float64`. Float
reduction uses an exact binary superaccumulator;
`AVG` divides that exact sum by the count, and each operation rounds only its
final result to nearest with ties to even. Input order therefore cannot change
the answer. Built-in provider float aggregation is ineligible for pushdown
unless its conformance evidence proves that same result. `MIN` and `MAX` retain
the input logical type.

Portability means equal canonical input tables produce the same schema and
relational result. It does not claim that an untyped CSV cell, Excel serial,
SQLite dynamic value, and PostgreSQL column are equal before their providers
decode and validate them into the same `SqlSchema`. Pushdown certification is
against this semantic matrix, not against similar syntax or plan-node names.

### Relational profile v1

Version 1 accepts exactly one deterministic `SELECT`, optionally introduced by
`WITH`, and this closed feature set:

- explicitly bound named relations and compile-time `*` expansion;
- projection, aliases, `DISTINCT`, and closed scalar expressions;
- `WHERE` and `HAVING` with three-valued boolean logic, comparisons, `IS NULL`,
  `IN`, `BETWEEN`, and case-sensitive SQL `LIKE`;
- `INNER` and `LEFT` equijoins whose condition is a conjunction of typed
  equality predicates;
- `GROUP BY` with `COUNT(*)`, `COUNT(expr)`, `COUNT(DISTINCT expr)`, `SUM`,
  `AVG`, `MIN`, and `MAX`;
- `CASE`, `COALESCE`, `NULLIF`, checked casts, numeric arithmetic, date/time
  literals, interval arithmetic, `ABS`, `ROUND`, `LOWER`, `UPPER`, `LENGTH`,
  `TRIM`, and `EXTRACT`;
- nonrecursive CTEs, derived tables, and uncorrelated scalar, `IN`, and
  `EXISTS` subqueries;
- `UNION ALL` between schema-compatible subplans;
- `ROW_NUMBER`, `RANK`, `DENSE_RANK`, `LAG`, `LEAD`, and the declared
  aggregates as window functions with `PARTITION BY` and `ORDER BY`; and
- `ORDER BY`, `LIMIT`, `OFFSET`, and SQL `FETCH` under independent SDK
  resource limits.

Aggregate windows accept only the whole-partition frame or
`ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` in v1. Ranking and offset
windows use their SQL-defined frames. `RANGE`, `GROUPS`, frame exclusion, and
provider-named windows are not in v1.

The profile rejects every other form, including DDL, DML, multiple statements,
recursive CTEs, cross/right/full/lateral joins, correlated subqueries,
`UNION DISTINCT`, `INTERSECT`, `EXCEPT`, arbitrary functions, executable UDFs,
stored procedures, table functions, external readers, provider settings,
provider-specific casts, and nondeterministic functions.

Null behavior, numeric promotion, decimal overflow, casts, timestamp units,
timezones, collations, and ordering follow the OTC semantic matrix rather than
host-engine defaults. Ascending order defaults to `NULLS LAST` and descending
order to `NULLS FIRST`; either may be written explicitly.

Any operation whose result depends on row position requires a proven total
order. `LIMIT`, `OFFSET`, `FETCH`, `ROW_NUMBER`, `LAG`, `LEAD`, and an ordered
`ROWS` frame compile only when the ordering expressions contain a declared
unique key within the result or window partition. Grouping keys and declared
source unique constraints participate in that proof; a caller may supply the
latter through `SqlRelationBinding`. `RANK` and `DENSE_RANK` may retain ties
because their values are tie-stable. Failure is
`SqlErrorCode.NONDETERMINISTIC_QUERY`; receipt canonicalization is evidence,
not a repair for an ambiguous query.

A uniqueness declaration participates in order or cardinality proofs only when
the provider enforces it for the bound snapshot or OTC validates it against the
same complete pinned/materialized input. A caller declaration is only a hint
until that validation succeeds. The prepared query and receipt retain the
constraint identity, validation method, snapshot, and evidence.

The feature registry is versioned. Adding syntax or a scalar, aggregate, or
window function requires a new conformance entry and cannot silently change
`v1` semantics.

### Compilation and execution

The execution path is:

```text
SQL text + typed parameters + explicit relations
  -> pinned parser syntax tree
  -> OTC whitelist and name resolution
  -> typed PortableRelationalPlan
  -> resource and capability planning
  -> bounded Polars operator evaluation and/or certified provider lowering
  -> Polars DataFrame + optional SqlReceipt
```

The parser is a replaceable implementation detail, initially using the
FinClaw migration's pinned SQLGlot baseline. SQLGlot is used only for lexing and
parsing. OTC immediately translates accepted syntax into its own closed plan;
the third-party AST is never serialized, authorized, hashed as the portable
plan, exposed to providers, or executed.

The authoritative local evaluator lowers the typed plan to bounded Polars
expressions and operator stages. A `LazyFrame` is scheduled only after its node
has an enforceable upper bound. Polars `SQLContext` may be used only as a
private optimization after the same conformance corpus proves equivalence; its
accepted grammar does not define OTC SQL Lite. DuckDB is not a required
runtime.

`pushdown` has the same three values on relational and temporal SQL:

- `"allow"` chooses certified full pushdown when available and otherwise uses
  bounded source reads plus the local evaluator;
- `"forbid"` forbids portable-plan execution by a provider while retaining
  ordinary bounded table reads; and
- `"require"` fails before any data-bearing source read unless the complete
  typed plan can execute as one certified provider operation. Bounded,
  metadata-only schema discovery during preparation is permitted.

`consistency="recorded"` is the v1 default. Each input is read from one
recorded provider snapshot or retained in-memory value, but different providers
may represent different observation times; the receipt says so explicitly.
Each provider must pin a revision or prove stability across the complete read,
for example with revision-token pagination or pre/post mutation detection. An
observation timestamp or final content hash alone does not prove that paginated
input was untorn. A provider unable to prove stability fails with
`UNSUPPORTED_CAPABILITY` and never labels the read a recorded snapshot.
`consistency="require_atomic"` succeeds only when all inputs are immutable or
one compatible provider execution domain guarantees a shared statement
snapshot. Cross-provider atomic snapshots are unsupported. FinClaw normally
binds immutable Artifact identities, so it does not rely on coincident live
reads.

A provider may expose the optional `portable-sql/1` extension-family ABI and
advertise the executable capability `portable-sql.execute/1.0`. Its
`PortableSqlExecutor` receives a closed request containing the typed plan,
typed parameters, `PortableSqlRelationBinding` values, consistency policy, and
SQL resource limits—never portable SQL text. Each provider binding contains
the logical name, `TableRef`, exact expected schema/fingerprint, validated
constraints, typed read options, and pinned snapshot identity; credentials
remain in provider context. Its result contains canonical Arrow data or an
artifact plus a `PortableSqlExecutionReceipt` identifying the exact plan hash,
output schema/order, bound source snapshots, enforced limits, and provider
evidence. The executor rejects any binding it cannot reproduce exactly.

Full pushdown is eligible only when every physical input belongs to one
compatible provider execution domain and the provider's conformance profile
covers every plan node, logical type, semantic rule, and requested bound. The
provider executes the exact supplied plan and may not rewrite it into a
self-declared residual. Mixed CSV, Excel, database, sheet, and in-memory
queries execute through the same local semantics. Version 1 permits ordinary
source column projection on the local path but defers partial relational-plan
pushdown until a proof-bearing cut/residual protocol is specified.

The SQL package defines `SqlResourceLimits`, distinct from the smaller
single-operation `ResourceLimits`. It bounds each source's rows and bytes,
total input rows and bytes, every intermediate's rows and bytes, output rows
and bytes, duration, local memory, and spill bytes. The SDK derives a
`ResourceLimits` value for each physical read. A SQL `LIMIT` changes query
meaning and bounds only final output; it does not authorize an unbounded join
or aggregate.

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

Local execution must obtain each source completely within its authorized
bounds. A truncated bounded read makes the query fail with
`RESOURCE_LIMIT_EXCEEDED`; OTC never computes a plausible but incorrect partial
aggregate or join. Before scheduling an operator, the planner must prove a
conservative upper bound inside the authorized envelope using exact source
extents or the enclosing read bounds. Unknown or excessive joins, windows, and
unions fail closed. The local executor uses bounded operator stages and runtime
counters in an isolated, cancellable worker with a confined spill directory;
it must not call an unrestricted `LazyFrame.collect()` and inspect the result
only after memory has already exceeded the contract.

For a one-shot call or `prepared.authorize()`, `limits=None` selects the
client's configured SQL limit profile; it never means unbounded execution. A
plain `Client()` and the module default install `DEFAULT_SQL_LIMITS_V1`: one
million rows/256 MiB per source, two million rows/512 MiB total input and per
intermediate, 100,000 rows/128 MiB output, 30 seconds, 512 MiB local memory,
and 2 GiB confined spill. Configuration may replace the whole profile but may
not create an unbounded one. Authorization rejects work whose bound is already
known to exceed the profile, and execution aborts if an observed intermediate
or output crosses it.
A provider is eligible for full pushdown only when it can enforce every
requested bound or prove a tighter one; a statement timeout alone does not
prove row, byte, memory, or scan bounds.

### SQL evidence and application ownership

`SqlQueryResult` contains `frame: polars.DataFrame` and
`receipt: SqlReceipt`. The receipt records:

- the exact UTF-8 statement hash and canonical typed-parameter hash;
- the canonical portable-plan identity and SQL Lite profile version;
- every logical input, its bound schema fingerprint, and its read receipt,
  full-pushdown source observation, or canonical in-memory dataframe identity;
- the requested consistency and actual per-source or shared snapshot facts;
- the requested limits and observed resource usage;
- provider-pushed and locally evaluated plan-node identities; and
- output schema and canonical content identities.

The exact statement hash preserves authored provenance; the canonical plan
hash identifies equivalent portable execution. A provider-native query receipt
does not claim either identity.

OTC owns SQL parsing, validation, type checking, portable plan semantics,
Polars execution, optional pushdown, and generic query evidence. FinClaw retains
stage and company scope, governed Artifact resolution, Accepted Silver
selection, budget authorization and Action Requests, and Analysis Result/Gold
identity. It maps `SqlAdmissionStatus` and authorization failures to its Action
Request workflow. Its current run-local SQLite SQL path migrates to this SDK
surface rather than becoming a second portable compiler.

## Time-Series Interface

### Binding a temporal table

```python
ticks = client.table("postgres://market", relation="market_data.ticks")
series = client.timeseries(
    ticks,
    descriptor=descriptor,
    logical_name="ticks",
)
```

A `TimeSeriesHandle` is bound to one physical `TableRef`, one distinct logical
name used by portable plans and SQL, and an optional expected
`TemporalTableDescriptor`. Convenience construction may accept the target and
physical selection separately, but `logical_name` is never inferred from or
sent as a physical identifier. Its first operation invokes a real
provider-facing `TemporalDescriber` protocol. That protocol returns a
`TemporalDescription` containing:

- the bound physical table reference and logical name;
- the effective temporal descriptor;
- the exact canonical Arrow schema;
- the descriptor hash over that schema;
- validated unique constraints with their enforcement or snapshot-validation
  evidence;
- the authoritative typed capability identities; and
- safe physical execution facts.

The SDK exposes the schema as a Polars schema in its public
`TimeSeriesDescription`; the canonical Arrow schema remains internal for hash
and artifact verification. If the caller supplies a descriptor, describe
validates it. If no descriptor is supplied, the provider must have a configured
descriptor and return it; schema alone cannot infer semantic roles such as
series keys, tags, or ingestion time. Otherwise binding fails with a
configuration error.

A temporal uniqueness claim is usable only when the provider enforces it for
the target or OTC validates it against the same complete pinned/materialized
snapshot used by the query. The evidence names the ordered field tuple,
validation method, and snapshot or provider constraint identity. Caller hints
are not evidence. A snapshot-scoped claim cannot be reused against another
revision.

This deliberately strengthens the current process `DESCRIBE`, which reports
only that portable temporal behavior exists and cannot verify descriptor
identity. A temporal query is not dispatched until description binds target,
relation, descriptor, schema, and capabilities.

The canonical low-level operation remains the typed portable plan:

```python
frame = series.execute(plan, pushdown="allow")
result = series.execute_with_receipt(plan, pushdown="allow")
```

`execute()` returns `polars.DataFrame`. `execute_with_receipt()` returns
`TemporalReadResult(frame, receipt)`. If an executor returns an Arrow artifact,
the SDK verifies and materializes it before producing the Polars result.

The handle rejects a plan whose logical `relation` or `descriptor_hash` differs
from its description. It also binds execution to the handle's physical table
reference; a plan cannot redirect the provider or reveal its physical relation
name. Querying a committed snapshot is explicit:

```python
snapshot = series.at_snapshot(commit_result)
frame = snapshot.execute(plan)
```

`at_snapshot()` returns another immutable handle carrying the verified
snapshot reference. The detailed execution methods also accept an explicit
`snapshot_reference` for framework bindings. Snapshot selection remains
transport metadata outside the portable plan.

The time-series contract adds an `ExecutionLocationPolicy` to
`TemporalExecutionRequest`, outside `PortableTemporalPlan`: SDK `"allow"` maps
to `ALLOW`, `"forbid"` to `REQUIRE_CONNECTOR`, and `"require"` to
`REQUIRE_PROVIDER`. The binding selects the connector evaluator or provider
lowerer before I/O and fails if the requested location is unavailable. The
receipt's execution location must satisfy the request. Keeping this policy out
of the plan preserves one portable plan hash across execution locations.

### Temporal SQL profile

`otc.sql-lite.temporal/v1` gives Python callers a familiar TimescaleDB-shaped
surface without making SQL text a provider or process protocol:

```python
frame = series.sql(
    """
    SELECT symbol,
           time_bucket($1, observed_at) AS bucket,
           avg(price) AS avg_price
    FROM ticks
    WHERE observed_at >= $2 AND observed_at < $3
    GROUP BY symbol, bucket
    ORDER BY symbol, bucket
    LIMIT $4
    """,
    parameters=("5 minutes", start, end, 500),
)

result = series.sql_with_receipt(...)
prepared = series.prepare_sql(...)
program = prepared.program
plan = program.portable_plan
```

The complete temporal SQL surface is:

```python
series.sql(
    statement,
    parameters=(),
    *,
    limits: ResourceBounds | None = None,
    pushdown="allow",
) -> pl.DataFrame
series.sql_with_receipt(
    statement,
    parameters=(),
    *,
    limits: ResourceBounds | None = None,
    pushdown="allow",
) -> TemporalSqlResult
series.prepare_sql(
    statement,
    parameters=(),
    *,
    limits: ResourceBounds | None = None,
    pushdown="allow",
) -> PreparedTemporalQuery

prepared.program -> TemporalSqlProgram
program.portable_plan -> PortableTemporalPlan
program.result_shape -> TemporalResultShape
prepared.execute() -> pl.DataFrame
prepared.execute_with_receipt() -> TemporalSqlResult
```

`TemporalSqlResult` has exactly `frame: polars.DataFrame` and
`receipt: TemporalSqlReceipt`. The SQL receipt contains the profile version,
exact statement hash, canonical typed-parameter hash, emitted-plan hash,
result-shape hash, requested pushdown policy, and the underlying
`TemporalReceipt` as its `temporal` field. Its top-level final schema, order,
row count, and canonical content identity are computed after the result-shape
projection and correspond exactly to `TemporalSqlResult.frame`; the nested
temporal receipt continues to describe the raw portable-plan carrier.

Temporal parameters use PostgreSQL-style numbered placeholders and a typed
sequence. This intentional difference from relational named parameters keeps
the temporal profile source-compatible with the existing OTS/Timescale Core
corpus. Provider-native placeholders remain entirely dialect-specific. Runtime
values must be parameters; only a positive `LIMIT` may be a literal.

Temporal `limits=None` resolves the client's mandatory configured
`ResourceBounds` profile and never means unbounded execution. Plain `Client()`
and the module default use `DEFAULT_TEMPORAL_BOUNDS_V1`: 100,000 rows,
128 MiB, and 30 seconds. Configuration may replace it only with another fully
bounded profile. Absence of a usable profile fails before describe or provider
I/O.

`prepare_sql()` first describes the handle and binds the logical name,
descriptor, exact schema, parameters, limits, result shape, and pushdown policy.
The immutable `PreparedTemporalQuery` retains an atomic `TemporalSqlProgram`
containing both the portable plan and the visible column order/aliases plus any
hidden fields required for ordering. It also retains every determinism
requirement and the exact validated constraint evidence used to discharge it.
When the description lacks required evidence, preparation may validate the
constraint only by a complete read of the query's bounded input under the same
pinned snapshot and must retain that carrier for local execution. With
`pushdown="require"`, the provider must instead enforce and receipt the
constraint. Otherwise preparation rejects the query before execution. `sql()`
executes that program's plan through the same path as `series.execute()`, then
applies only its deterministic final projection. `program.portable_plan` is
exposed for diagnostics and transport, but executing that raw plan alone
promises plan output rather than the complete SQL result shape. The plan sent
to providers never contains SQL text or physical identifiers.

The v1 statement is one deterministic `SELECT` over the handle's single
logical relation. It accepts:

- projection of descriptor-declared fields;
- exactly one `time >= $n AND time < $m` event-time range for scans and bucket
  queries;
- `time <= $n` only in the `last(value, time)` latest shape described below;
- equality and `IN` predicates on declared series keys and tags;
- grouping whose projected dimensions exactly match the declared grouping
  dimensions and the unique `bucket` alias;
- `count(*)`, `min(value)`, `max(value)`, `sum(value)`, `avg(value)`,
  `first(value, event_time)`, and `last(value, event_time)`, each with a unique
  explicit output alias;
- `time_bucket` with the portable fixed/calendar interval, origin, offset, and
  timezone forms;
- `time_bucket_gapfill`, plus `locf` and `interpolate` wrapping exactly one
  supported aggregate and only with gapfill;
- mandatory deterministic `ORDER BY` over declared output fields; and
- a positive `LIMIT` under independent plan row and byte bounds.

The latest shape contains one or more `last(value, event_time)` expressions,
uses `time <= $n`, and groups by the complete declared series key and nothing
else. Plain projection with a one-sided predicate is rejected; `series.as_of()`
remains the explicit programmatic `AsOf` interface.

SQL `first` and `last`, including the latest shape, are rejected when the
descriptor uses `duplicate_policy="preserve"`, because the existing portable
operations have no single-row tie-break field. Bucketed `first`/`last` also
require the complete series key in `GROUP BY`. Under `reject`, duplicate logical
keys fail. Under `replace-latest`, SQL v1 additionally requires a validated
unique constraint over the full replacement key: series-key fields, event-time
field, and ingestion-time field. The descriptor's greatest-ingestion-time rule
then resolves duplicate logical keys without an equal-ingestion tie. Although
the low-level portable-plan v1 contract can resolve an exact tie by source
encounter order, the SQL frontend does not treat an undeclared physical row
order as portable evidence. A future portable-plan version may add an explicit
validated tie-breaker, but v1 never invents one in the SQL frontend.

`time_bucket` and `time_bucket_gapfill` take two through five positional
arguments. Width is the first parameter and the descriptor's event-time field
is second. Optional arguments are at most one typed timezone string, origin
timestamp, and fixed offset interval. Defaults are UTC, the profile's canonical
epoch for the timestamp precision, zero offset, and ISO Monday for calendar
weeks. Calendar buckets require a day-or-larger unit. The canonical corpus owns
the interval grammar.

Comments, relation aliases, every quoted identifier, physical names, and more
than one relation are rejected in v1. Unquoted logical relation and field
identifiers bind through the handle description. Scan order must contain the
descriptor's observation key;
aggregate order must contain every group key and bucket; latest order must
contain the complete series key. When duplicate preservation makes an
observation key nonunique, the order expressions must contain a validated
unique constraint from the bound `TemporalDescription`; merely naming a
source-declared field is insufficient. For `replace-latest`, deterministic
duplicate resolution separately requires the validated full replacement key
described above. `PreparedTemporalQuery` and `TemporalSqlReceipt` retain the
constraint identities, validation methods, and matching snapshot evidence.
Otherwise an order-sensitive query is rejected as nondeterministic.

It rejects joins, CTEs, subqueries, set operations, window functions, `HAVING`,
`DISTINCT`, `OFFSET`, arbitrary functions or expressions, DDL, DML, physical
relation names, provider settings, unbound runtime literals, unbounded
scan/aggregate time,
and nondeterministic output. These restrictions are intentionally narrower
than the relational profile because they preserve the existing portable
temporal semantics.

“Unbounded time” here means a scan, aggregate, gapfill, or plain projection
without the exact half-open range. The declared latest shape is the sole
one-sided exception and remains constrained by independent row, byte, and
duration bounds.

Compilation has an exact semantic mapping:

| SQL shape | Existing portable operation |
| --- | --- |
| bounded field projection | `ScanRange` |
| `last(...)`, `time <=`, full series-key grouping | `Latest` |
| `time_bucket(...)` aggregates | `BucketAggregate` |
| `time_bucket_gapfill(...)` or fill wrapper | `GapFill` |

`pushdown="allow"` permits either certified provider lowering or bounded
connector-side residual evaluation. `pushdown="forbid"` requires the latter.
`pushdown="require"` fails before I/O unless the complete emitted plan has a
proven pushdown claim. A nonempty residual plan is reported as Connector
execution, not provider pushdown. No new SQL-text provider capability is
introduced; required capabilities are derived from the emitted portable
operation.

This application-facing compiler amends the earlier OTC statement that only
OTS parses temporal SQL. The lower provider and connector-process seams remain
plan-only. OTS still owns Add-on resolution, its wider Timescale Core/native
identity, `TimescaleNativePlan`, and OTS acceptance. When the deferred Rust
integration resumes, the Rust and Python compilers must consume one neutral,
versioned corpus and emit the same canonical `PortableTemporalPlan` wire JSON,
plan hash, and result shape for shared cases. This supersedes earlier hash
parity wording for portable plan identity only; result Arrow bytes and provider
receipts require normalized logical parity, not byte identity.

### Ergonomic temporal operations

The SDK provides typed helpers that construct the same plan operations as the
temporal SQL compiler; neither creates a second execution model:

```python
series.describe()
series.scan_range(
    start,
    end,
    *,
    columns=None,
    tags=(),
    limits: ResourceBounds | None = None,
    pushdown="allow",
)
series.latest(
    *,
    at_or_before=None,
    tags=(),
    limits: ResourceBounds | None = None,
    pushdown="allow",
)
series.as_of(
    at,
    *,
    tags=(),
    limits: ResourceBounds | None = None,
    pushdown="allow",
)
series.aggregate(
    start,
    end,
    *,
    bucket,
    measures,
    tags=(),
    limits: ResourceBounds | None = None,
    pushdown="allow",
)
series.gap_fill(
    start,
    end,
    *,
    bucket,
    measures,
    rules,
    tags=(),
    limits: ResourceBounds | None = None,
    pushdown="allow",
)
```

Each query has a corresponding `*_with_receipt` form with the same arguments.
Every helper forwards `pushdown` unchanged to `series.execute`. Timestamp,
half-open range, ordering, descriptor, bound, aggregation, and fill semantics
continue to come exclusively from `open_table_connector.timeseries`.

`columns=None` means every descriptor-declared field in canonical descriptor
order; an empty projection is invalid. Helper-generated plans use deterministic
output order and sorted, unique typed capability identities. They require
exactly scan, latest, as-of, or aggregate as appropriate; `gap_fill()` requires
both aggregate and fill. Pushdown is required only when the caller explicitly
requests that guarantee. A result row limit may not exceed the plan's maximum
row bound. `gap_fill()` is aggregate-then-gap-fill, not arbitrary dataframe
null filling; `fill()` may exist only as a deprecated alias.

### Temporal writes

The currently declared `timeseries.write.append/1.0` and
`timeseries.write.upsert/1.0` identities become real SDK operations:

```python
series.append(frame, *, idempotency_key=None) -> TemporalWriteResult
series.upsert(frame, *, idempotency_key) -> TemporalWriteResult
```

The time-series package defines the currently missing `TemporalWriter`,
`TemporalWriteRequest`, `TemporalWriteResult`, and `TemporalWriteReceipt`.
Append and upsert validate the dataframe against the exact canonical schema and
bound descriptor before provider I/O. Each request carries operation identity,
resource bounds, relation, descriptor hash, input content identity, and an
idempotency key when required. The receipt records affected rows, observed
input time range, descriptor/content identities, provider revision, and
idempotency outcome.

The logical observation key is `series_key_fields + time_field`. Duplicate and
ordering behavior follows the descriptor:

- `preserve` retains duplicate observations;
- `reject` fails the whole operation on a duplicate logical key; and
- `replace-latest` requires ingestion time and makes the greatest ingestion
  time observable for a logical key.

Append never deletes or updates a stored row. Under `replace-latest`, it may
retain history while descriptor-governed reads expose the greatest ingestion
time. Upsert is unsupported for `preserve`; for `reject` or `replace-latest` it
must provide the descriptor's observable replacement behavior atomically for
every submitted key. All rows are accepted or the operation fails; partial
success requires a future versioned capability. Reusing an idempotency key
with different content is a stable conflict. A provider must not advertise
either identity merely because ordinary `table.write(if_exists="append")`
exists.

Completion requires executable reference implementations, not methods that
always return unsupported: SQLite implements append and upsert offline;
PostgreSQL claims them only after configured-live conformance; MaybeSheet may
claim append only after its live process receipt proves it. Other providers
remain unsupported until they pass the same writer suite.

### Managed storage lifecycle

Managed operations are grouped under `series.storage`:

```python
stage = series.storage.stage(frame, idempotency_key="batch-42")
commit = series.storage.commit(stage)
readback = series.storage.readback(commit)
series.storage.abort(stage)
```

The detailed request-object forms remain available for framework bindings and
tests. The ergonomic SDK form fills operation IDs, descriptor hashes,
credentials, artifact creation, and configured resource bounds. It does not
weaken existing lifecycle semantics:

- stage remains invisible;
- commit remains idempotent on target, stage, and key;
- readback independently observes and verifies the committed snapshot; and
- abort remains idempotent and reports its disposition.

`readback.frame` is a Polars dataframe. The readback receipt remains mandatory
because snapshot verification is the purpose of the operation.

### Complete temporal-operation mapping

| Capability | SDK surface |
| --- | --- |
| `otc.sql-lite.temporal/v1` | `series.sql*()` / `series.prepare_sql()` |
| `timeseries.describe/1.0` | `series.describe()` |
| `timeseries.scan.range/1.0` | `series.scan_range()` / plan execution |
| `timeseries.scan.range.pushdown/1.0` | execution fact, not a different call |
| `timeseries.lookup.latest/1.0` | `series.latest()` / plan execution |
| `timeseries.lookup.asof/1.0` | `series.as_of()` / plan execution |
| `timeseries.aggregate.window/1.0` | `series.aggregate()` / plan execution |
| `timeseries.aggregate.window.pushdown/1.0` | execution fact, not a different call |
| `timeseries.fill/1.0` | `series.gap_fill()` / plan execution |
| `timeseries.write.append/1.0` | `series.append()` |
| `timeseries.write.upsert/1.0` | `series.upsert()` |
| `storage.stage/1.0` | `series.storage.stage()` |
| `storage.commit.idempotent/1.0` | `series.storage.commit()` |
| `storage.snapshot.read/1.0` | `series.storage.readback()` |
| `storage.readback.verify/1.0` | mandatory readback receipt evidence |
| `storage.visibility.atomic/1.0` | commit guarantee, not a different call |
| `storage.abort/1.0` | `series.storage.abort()` |

Pushdown and visibility capabilities describe observable execution guarantees;
they do not create duplicate methods.

## Provider Plugin and Extension Model

### One application-independent registration

`open_table_connector.providers` becomes the authoritative provider discovery
group. Each entry point returns a zero-I/O `PluginDescriptor`. The descriptor
contains immutable route and capability metadata plus one factory ABI. The
factory accepts `ProviderFactoryContext` and returns a `ProviderInstance` with
an optional table Connector and zero or more lazy capability-extension
factories.

Conceptually:

```python
PluginDescriptor(
    name="postgres",
    identity=CONNECTOR_IDENTITY,
    schemes=("postgres", "postgresql"),
    capabilities=(...),
    factory=create_provider_instance,
)

ProviderInstance(
    table=postgres_connector,
    extensions={
        "portable-sql/1": create_sql_binding,
        "timeseries/1": create_temporal_binding,
    },
)
```

`ProviderInstance` and its generic extension mapping live in the base contract
and do not import SQL or temporal types. The SQL package owns
`SqlFactoryContext` and `SqlBinding`; the binding exposes a
`PortableSqlExecutor` plus its exact conformance profile. The time-series
package owns `TemporalFactoryContext` and `TemporalBinding`:

```python
TemporalBinding(
    describer=temporal_describer,
    executor=portable_executor,
    writer=optional_temporal_writer,
    store=optional_managed_store,
    capabilities=typed_capability_identities,
)
```

The context contains only downward-safe structural values: table reference,
relation, optional expected descriptor, safe provider configuration, a
protected credential-value mapping excluded from representation, injected
transports, validated extension options, and a confined artifact-root path or
neutral artifact port. It never imports an SDK credential-lease or workspace
class. The SDK retains ownership of lease and workspace lifetimes outside the
context. This replaces process-document-shaped temporal factories for
in-process use without reversing package dependencies.

A distribution may publish multiple descriptors when it owns independently
routed Connectors, as `local_files` does for CSV, Excel, Markdown, and its
compatibility route. The SDK does not collapse those identities into one
CLI-specific adapter.

### Capability integrity

Static descriptor capabilities allow listing and route preflight without
constructing providers. A capability that depends on a remote service may be
marked probe-required. The SDK performs that probe only when the route is used
or the caller explicitly requests live capabilities.

`client.connectors()` returns immutable `ConnectorInfo` metadata, never raw
`PluginDescriptor` objects containing factories. Static installed capabilities
and live effective capabilities are distinguishable. Compatibility checks
match capability ID and supported version, not ID alone. Table modes carry
base-versus-sheet behavior; providers do not invent inconsistent read
capability names for each mode.

After construction, advertised capabilities must correspond to implemented
runtime protocols. `CapabilityIdentity` is the one authoritative in-memory
representation; full wire strings and process `name -> version` maps are
derived from it. Provider class constants, process registration, and extension
bindings must not maintain competing capability lists. A mismatch is a
provider configuration error, not an attribute error or fallback. Unsupported
operations fail before source or destination I/O whenever preflight can
determine the result.

Transactions have an advertised capability. Write capability metadata also
describes supported conflict policies; `table.write` does not imply that
`error`, `append`, and `replace` are all available. Destination providers retain
an internal preflight seam so `copy_to()` validates the exact policy before
reading its source.

Route collision checks remain deterministic and occur before provider
factories or credential resolution. Removing a provider wheel removes its
routes without preventing the SDK from importing.

## Configuration and Credentials

Configuration moves from CLI ownership to the SDK because every application
needs identical discovery and credential semantics.

The canonical schema becomes `otc.config/v1`. `Client.from_config(path)` uses
an explicitly supplied file. `Client.from_default_config()` and the one-shot
API use the existing precedence:

1. explicit injected path;
2. `OTC_CONFIG`;
3. `$XDG_CONFIG_HOME/open-table-connector/config.toml`;
4. `~/.config/open-table-connector/config.toml`; and
5. installed providers with safe defaults.

The schema includes complete SQL and temporal limit profiles. Omission selects
the documented `DEFAULT_SQL_LIMITS_V1` and `DEFAULT_TEMPORAL_BOUNDS_V1`; a
profile with an absent or unbounded required field is invalid. Thus the
one-shot API is usable without a config file but never silently unbounded.

The completed CLI plan's `otc.cli-config/v1` document is accepted as a
deprecated, structurally equivalent alias for one compatibility window. It is
never silently rewritten. New documentation emits only `otc.config/v1`.

The closed provider and credential-reference rules from the CLI plan remain:

- configuration can enable, disable, and safely configure installed canonical
  providers but cannot invent routes or import paths;
- secret values are resolved through injected credential resolvers;
- the default resolver may use declared environment bindings;
- credential values are excluded from representation, equality,
  serialization, diagnostics, and hashes; and
- credential leases are scoped to provider activation and closed with the
  client or operation as appropriate.

Applications may bypass file loading with immutable `ClientConfig` objects and
injected discovery, credential, environment, transport, clock, and artifact
workspace dependencies. These injection points are first-class test seams.

`TableHandle` and `TimeSeriesHandle` construction is cheap, immutable, and
does not resolve secrets. Credentials are leased for the shortest practical
operation scope. A transaction is the exception: it pins its provider instance
and lease until commit or abort. Secretless reusable transports may be cached
by the client and are closed with it.

## Errors, Results, and Lifecycle

Physical SDK operations raise the existing stable `ConnectorError` family.
Portable SQL parse, binding, typing, determinism, and admission failures raise
`SqlCompileError`; temporal execution errors retain their temporal code and
safe details. Error messages never include raw credentials, secret-bearing
URIs, provider response bodies, unrestricted SQL literals, or unrestricted
filesystem paths.

All result and metadata objects are immutable. Reads do not mutate client
state to expose evidence. The common direct-dataframe methods and explicit
receipt-bearing methods call one internal operation; they cannot diverge in
routing or semantics. Receipt schema/content fingerprints describe the
internally verified canonical Arrow carrier. They do not claim that Polars
serialization bytes or hashes are identical after conversion.

The SDK runtime also has a non-public, carrier-preserving host port returning a
`VerifiedArrowResult` or verified Arrow artifact together with that same
receipt. A future bridge host uses this port instead of converting the public
Polars result back to Arrow. The port shares all routing, authorization, and
execution code with the public operation and is not a second application API.

`Client.close()` closes activated providers, transports, credential leases,
and temporary artifact workspaces in reverse construction order. It is
idempotent. Operations on a closed client fail predictably. Module-level
convenience functions never close caller-owned injected dependencies.

The synchronous API is authoritative for version 1 because every current
Connector protocol is synchronous. An async facade is deferred until providers
have a real async seam; the SDK must not hide blocking provider work inside an
apparently async method.

## CLI Cutover

After SDK availability, CLI command behavior maps mechanically:

| CLI command | SDK call |
| --- | --- |
| `otc list` | `client.connectors()` |
| `otc inspect` | `client.table(source).inspect()` |
| `otc read` | `client.table(source).read_with_receipt()` |
| `otc convert` | `client.copy(source, local_destination, ...)` |
| `otc import` | `client.copy(source, connector_destination, ...)` |
| `otc query` | `client.sql_with_receipt()` |

The CLI may choose receipt-bearing methods because it renders evidence and
summaries. That does not change the one-shot SDK default of returning a bare
Polars dataframe for reads.

`otc query` is the one new reference command added by this refactor. It accepts
SQL from one mutually exclusive `--sql`, `--file`, or stdin source; repeated
`--relation NAME=TARGET` bindings; `--param NAME=JSON_VALUE` scalar values; and
an explicit resource-limit profile. Date, timestamp, interval, and decimal
values use JSON strings plus an explicit SQL cast. The command maps those
values directly to `client.sql_with_receipt()` and performs no SQL parsing,
routing, planning, or execution itself. A future temporal CLI command must
likewise delegate to
`series.sql_with_receipt()` rather than add another compiler.

Provider-specific CLI adapters, configured registries, credential lifecycle,
and pipeline orchestration are deleted after parity tests pass. Local codec
write behavior is first moved from CLI adapters into provider-owned
Connectors, so SDK `write()` and `copy_to()` never call CLI code. Compatibility
imports may issue deprecation warnings for one release but must delegate to the
SDK rather than retain a second implementation.

The CLI does not initially add commands for every advanced SDK method. It is a
thin reference application, not a requirement that every SDK capability have
a command-line spelling.

## Testing and Conformance

The SDK public interface becomes the primary application conformance surface.
Required coverage includes:

- one-shot and explicit-client behavior;
- exact Polars result types and Arrow isolation;
- closed `TableRef` normalization for relation, sheet/range, and local
  format selection;
- deterministic discovery, route collision, disablement, and unplugging;
- lazy provider activation and clean shutdown;
- config compatibility and strict validation;
- scoped credentials and redaction under failures;
- capability/protocol agreement and preflight-before-I/O;
- static versus probed capability versions and supported write policies;
- every table-operation mapping in this document;
- bounds that are enforced rather than applied after unbounded materialization;
- copy ordering, field policy, and dual receipts;
- transaction commit, abort, nesting rejection, and closed-state behavior;
- portable versus native SQL namespaces and row-query versus native execution
  behavior;
- relational SQL accepted/rejected corpus, typed-plan goldens, parameter and
  schema binding, and exact statement/plan identities;
- authoritative schema discovery versus rejected sampling and caller-schema
  validation;
- default, custom, partial, and invalid preparation envelopes, including
  failure before data I/O when no complete bounded envelope exists;
- preparation-time `pushdown="require"` and `consistency="require_atomic"`
  preflight, retained snapshot lifetime, and rejection of later policy changes;
- the normative type matrix across decimals, integer division, overflow,
  null/blank/empty text, Unicode, nonfinite floats, timestamps, timezones, and
  daylight-saving boundaries;
- order-independent exact float reductions and rejection of provider aggregate
  pushdown without equivalent rounding evidence;
- total-order proofs and rejection of ambiguous limits and order-sensitive
  windows, including validation of claimed unique-key evidence;
- identical SQL Lite plans and normalized results for in-memory Polars, CSV,
  Excel, SQLite, and configured-live PostgreSQL inputs;
- local and full-pushdown equivalence for every provider feature it advertises;
- complete-input enforcement, intermediate/output bounds, and rejection of
  truncated or unknown-cardinality local joins, unions, windows, or aggregates;
- cancellable-worker memory/spill/deadline enforcement and cleanup;
- prepared-plan estimate/authorization/execution identity and schema-drift
  failure;
- recorded per-source snapshots and required-atomic snapshot preflight;
- composite SQL receipts covering every source and execution location;
- temporal SQL accepted/rejected corpus and exact SQL-to-`PortableTemporalPlan`
  plus result-shape golden mapping;
- temporal execution-location policy preflight and matching receipt evidence;
- temporal unique-constraint validation, snapshot binding, and rejection of
  equal-ingestion replacement ties without proof;
- all temporal plan operations and ergonomic-helper equivalence;
- real temporal description, relation binding, descriptor hashing, and
  snapshot selection;
- append/upsert descriptor validation and idempotency;
- managed lifecycle and independent readback evidence;
- provider installation/removal independence; and
- black-box CLI equivalence before old orchestration is removed.

Provider conformance uses a shared SDK harness plus capability-specific suites.
A provider is tested only for capabilities it advertises, but every advertised
capability is mandatory. Relational and temporal golden fixtures are
independent expected plans and results rather than being generated by the same
evaluator under test. A provider cannot advertise a plan node merely because
its native engine parses similarly spelled SQL.

FinClaw receives a focused integration test proving it can bind governed
Artifact inputs to an injected `Client`, run its approved SQL Lite examples,
and preserve Polars data, statement/plan identity, and source receipts. This
supersedes its planned standalone parser and run-local SQLite evaluator. The
FinClaw migration itself may occur after the SDK release.

## Migration Strategy

The implementation plan will sequence this as a strangler refactor after the
current CLI plan finishes:

1. Characterize the completed CLI and current direct-provider behavior.
2. Add the independently installable SQL package, its closed relational IR,
   semantic matrix, parser whitelist, independent golden corpus, and bounded
   Polars evaluator.
3. Add the independently installable SDK package and stable public result
   types.
4. Move configuration, credentials, discovery, routing, and lifecycle from the
   CLI into the SDK without changing behavior.
5. Add `TableRef`, exact typed inspection, native row-query, corrected
   bounded/transaction contracts, and Polars handles.
6. Add client/table SQL relation binding, prepared estimates, SQL resource
   limits, isolated local execution, snapshot policy, receipts, and the
   optional full-plan provider pushdown extension.
7. Generalize registration to `ProviderInstance`, migrate local writers, and
   retire CLI-specific adapter factories.
8. Add temporal describe and writer protocols, the temporal SQL compiler and
   prepared result shape, execution-location policy, typed extension factory,
   reference append/upsert implementations, and all temporal handles.
9. Move copy orchestration into the SDK and cut the CLI, including `otc query`,
   to direct SDK calls.
10. Run provider, SQL, temporal, package-isolation, CLI-parity, and FinClaw
    contract tests before deleting compatibility paths.
11. Update user, provider-author, SQL-profile, and migration documentation.

Each step must leave one authoritative path for newly migrated behavior. The
plan must not create a long-lived SDK facade that simply calls back into CLI
modules.

## Acceptance Criteria

- A Python application can install the SDK plus one provider and read a target
  into a Polars dataframe without importing CLI modules.
- The public SDK exposes every table and temporal operation mapped above.
- Direct reads and temporal queries return Polars dataframes; explicit detailed
  variants preserve receipts.
- `client.sql()` executes the same SQL Lite relational semantics over named
  Polars, CSV, Excel, SQLite, and PostgreSQL inputs; media differ only in
  certified pushdown availability.
- SQL Lite accepts the complete closed v1 subset in this document, rejects
  every provider escape, and never evaluates a truncated source as complete.
- Every relation has an exact typed schema, every admitted local operator has
  an enforceable bound, and order-sensitive queries have a proven total order.
- `prepare_sql()` exposes the exact plan and conservative estimate;
  preparation binds consistency and pushdown before source reads, and
  `authorize()` binds an approved envelope that executes without recompilation.
- Cross-medium parity includes the normative type/semantic matrix and snapshot
  evidence, not only similar row values.
- `series.sql()` compiles the temporal profile into the existing portable plan
  and sends no portable SQL text across provider or process seams.
- Portable SQL and provider-native SQL have visibly different namespaces,
  types, capabilities, receipts, and conformance claims.
- The SDK discovers and activates only installed, enabled providers.
- Providers depend only on contract and optional SQL/time-series packages,
  never SDK or CLI.
- Unsupported capabilities fail with stable errors and do not trigger
  avoidable provider I/O.
- The CLI contains no provider registry, credential lifecycle, Connector
  construction, Arrow conversion, or copy pipeline.
- Existing CLI behavior passes black-box parity tests through the SDK.
- `otc query` contains presentation and argument mapping only; it calls the SDK
  compiler and evaluator unchanged.
- Time-series results and readback expose Polars without weakening temporal
  bounds, identities, or receipts.
- At least one offline provider executes temporal append and upsert; capability
  claims by other providers require matching conformance evidence.
- The SDK design contains no dependency on OTS or the deferred Rust bridge.
