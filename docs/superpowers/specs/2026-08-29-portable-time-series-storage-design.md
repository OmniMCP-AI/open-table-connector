# Portable Time-Series Storage Design

## Status

Approved in chat on 2026-08-29. Immediate delivery scope covers phases 1–5:
the shared portable plan, direct TimescaleDB integration in the sister OTS
repository, OTC Polars/Arrow execution and local transport, and the CSV, JSON,
JSONL, SQLite, PostgreSQL, Excel, and MaybeSheet capability work. Native
ClickHouse, native TDengine, and Arrow Flight transport are later tracks.

Amended in chat on 2026-08-29 to add JSON and JSONL using their normal URI
schemes, with managed lifecycle and snapshot selection carried outside the
URI and portable plan.

Architecture identifier: `ots-otc-timeseries-storage/v1`.

Companion OTS specification:
[Native and OTC Storage Backends Design](https://github.com/OmniMCP-AI/open-time-series/blob/main/docs/superpowers/specs/2026-08-29-native-and-otc-storage-backends-design.md).

Implementation plans:
[OTC portable storage](https://github.com/OmniMCP-AI/open-table-connector/blob/main/docs/superpowers/plans/2026-08-29-portable-time-series-storage.md) and
[OTS native and OTC backends](https://github.com/OmniMCP-AI/open-time-series/blob/main/docs/superpowers/plans/2026-08-29-native-and-otc-storage-backends.md).

This specification is authoritative for the portable temporal plan, OTC
capability identities, neutral execution and managed-storage receipts, the
local connector-process transport, and per-connector OTC support claims. The
companion OTS specification is authoritative for the Timescale Core SQL
language, OTS `StorageAdapter` behavior, native time-series backends, OTS
profiles, and OTS acceptance evidence.

## Decision

OTC becomes one portable, reduced-capability time-series backend family for
OTS and remains independently usable by other frameworks. It does not become
the abstraction through which native TimescaleDB, ClickHouse, or TDengine
backends must pass.

OTC implements a versioned portable temporal operation model. The first
executor evaluates that model with Polars and Arrow for local and
non-time-series providers. SQL-capable OTC connectors may lower the same model
to prepared SQLite or PostgreSQL statements. OTC does not define or parse a
new time-series SQL dialect.

OTS uses TimescaleDB-flavored SQL as its first default human-facing temporal
language, compiles the portable subset once, and sends OTC a typed
`PortableTemporalPlan` rather than executable SQL text. Native OTS adapters
lower directly to their provider languages and protocols.

## Relationship to the adapter migration analysis

This design accepts the analysis in
`open-time-series/docs/reports/ots-open-table-connector-adapter-migration-analysis.md`
for ordinary physical table connectors:

- OTC owns URI handling, caller-injected credentials, physical I/O,
  conversion, provider retries, and neutral physical receipts.
- OTS owns framework translation, logical plans, profile verification,
  canonical identities, and acceptance evidence.
- The two receipt layers never substitute for one another.

It refines one conclusion. Purpose-built time-series databases are first-class
native OTS backends rather than OTC providers. This exception preserves their
native query, lifecycle, retention, compression, and streaming leverage.

## Goals

- Add portable time-series reads, lookups, window aggregation, gap filling,
  and bounded execution without breaking the existing table contract.
- Add a neutral managed-storage lifecycle strong enough for an OTS binding to
  stage, commit, address a snapshot, verify readback, and abort.
- Give CSV, JSON, JSONL, Excel, MaybeSheet, SQLite, and PostgreSQL explicit,
  honest support tiers.
- Execute the portable core with Polars and Arrow when the selected physical
  target lacks native temporal operators.
- Define a cross-language local transport from Rust OTS to Python OTC without
  turning the OTC CLI adapter into a wire contract.
- Keep transport, operation semantics, and provider lowering at separate
  seams so a later Flight transport can reuse the same operation model.
- Preserve independent release and version pinning between the sister
  products.

## Non-goals

- Do not implement native TimescaleDB, ClickHouse, or TDengine backends in
  OTC.
- Do not define a new SQL grammar, optimizer, or general relational engine in
  OTC.
- Do not promise that all connectors are writable OTS storage backends.
- Do not emulate continuous aggregates, retention, compression, tiering,
  subscriptions, or native stream processing in Polars.
- Do not make current `NeutralReceipt` hashes equivalent to OTS content
  identities across Python and Rust.
- Do not place OTS plan hashes, profiles, or acceptance decisions in neutral
  OTC interfaces.
- Do not require a network service or gRPC deployment in v1.

## Architecture

```text
Timescale Core SQL (OTS)
          |
          v
OTS logical plan and authorization
          |
          +---------------- native path -----------------------------+
          |                                                          |
          |  thin TimescaleStorageAdapter -> TimescaleDB              |
          |  later ClickHouseStorageAdapter -> ClickHouse             |
          |  later TdengineStorageAdapter -> TDengine                 |
          |                                                          |
          +---------------- portable path ---------------------------+
          |
          v
PortableTemporalPlan v1
          |
          v
OtcStorageAdapter -> OTC transport -> OTC Connector
                                      |
                                      +-> Polars/Arrow evaluator
                                      +-> prepared SQLite SQL
                                      +-> prepared PostgreSQL SQL
```

`PortableTemporalPlan` is the stable sister-product contract. The local
process transport is one carrier for it. A future Arrow Flight carrier must
not change plan or receipt semantics.

## Package and specification structure

The OTC workspace adds two focused distributions:

- `open-table-connector-timeseries`, under
  `open_table_connector.timeseries`, owns descriptors, plan models,
  execution results, managed-storage requests and receipts, Polars/Arrow
  evaluation, and provider-lowering helpers.
- `open-table-connector-process`, under `open_table_connector.process`, owns
  control envelopes, framing, session supervision, Arrow artifact references,
  cancellation, credential-reference handling, and connector dispatch.

Machine-readable schemas live under `specification/schemas/` and include:

- `portable-temporal-plan-v1.schema.json`;
- `temporal-receipt-v1.schema.json`;
- `managed-stage-receipt-v1.schema.json`;
- `managed-commit-receipt-v1.schema.json`;
- `managed-readback-receipt-v1.schema.json`; and
- `connector-process-envelope-v1.schema.json`.

The existing `open-table-connector-contract` v1 remains source- and
wire-compatible. Time series is an overlay on `TableMode.BASE`, not a third
table mode. Existing connectors opt into the extension by importing the new
package and advertising versioned capability identities.

## Temporal table descriptor

Every temporal operation binds to an immutable descriptor:

```python
@dataclass(frozen=True)
class TemporalTableDescriptor:
    time_field: str
    timezone: str
    precision: TimestampPrecision
    series_key_fields: tuple[str, ...]
    tag_fields: tuple[str, ...]
    value_fields: tuple[str, ...]
    ingestion_time_field: str | None
    duplicate_policy: DuplicatePolicy
    ordering: TemporalOrdering
```

The descriptor rules are:

- `timezone` is an IANA timezone name. Wire timestamps are normalized to UTC.
- `precision` is one of second, millisecond, microsecond, or nanosecond.
- The event-time field is required and non-null.
- Series keys identify an independent ordered series. Tag fields are
  filterable dimensions but need not be unique.
- Value fields are the only fields accepted by aggregate measures.
- An optional ingestion-time field resolves ordering only when the declared
  duplicate policy permits it.
- Duplicate policy is `preserve`, `reject`, or `replace-latest`.
- Ordering is `unspecified`, `nondecreasing`, or `strict` within a series.

The canonical descriptor hash covers every field above plus the normalized
Arrow schema. It never covers a physical URI or credential.

## Portable temporal plan v1

`PortableTemporalPlan` is a closed, typed plan rather than SQL text. It names
a logical relation token; the executing connector request supplies the
physical `TableURI` separately.

The v1 plan supports these root operations:

- `ScanRange`: projection, inclusive start, exclusive end, equality or `IN`
  tag predicates, and deterministic ordering.
- `Latest`: the last observation per requested series at or before an optional
  UTC timestamp.
- `AsOf`: the last observation at or before a UTC timestamp for each requested
  series; ties follow descriptor duplicate policy.
- `BucketAggregate`: fixed or calendar bucket, origin, offset, timezone,
  group keys, and named aggregate measures.
- `GapFill`: empty-bucket generation followed by `null`, constant, LOCF, or
  linear interpolation.

Supported aggregate functions are `count`, `min`, `max`, `sum`, `avg`,
`first`, and `last`. `first` and `last` order by event time, then ingestion
time when declared, and otherwise apply duplicate policy.

Every plan includes:

- its plan schema version;
- the temporal descriptor hash;
- the logical relation token;
- required capability identities;
- row, byte, and duration bounds;
- output order; and
- an optional result row limit that is never a substitute for input bounds.

Timestamps use RFC 3339 UTC wire strings with the declared precision. Ranges
are always half-open `[start, end)`. SQL `BETWEEN` semantics are not used.

Fixed buckets use an integer duration in nanoseconds. Calendar buckets use a
positive count plus one of day, week, month, quarter, or year, with explicit
timezone, week start, origin, and offset. LOCF and interpolation do not read
outside the requested range in v1. Linear interpolation requires observations
on both sides inside the range and otherwise yields null.

The plan excludes joins, subqueries, common-table expressions, arbitrary
expressions, user-defined functions, DDL, and raw provider options.

## Deep execution interfaces

The stable temporal execution seam is intentionally small:

```python
class PortableTemporalExecutor(Protocol):
    def execute(
        self,
        request: TemporalExecutionRequest,
    ) -> TemporalExecutionResult: ...

class ManagedTemporalStore(Protocol):
    def stage(self, request: ManagedStageRequest) -> ManagedStageReceipt: ...
    def commit(self, request: ManagedCommitRequest) -> ManagedCommitReceipt: ...
    def readback(self, request: ManagedReadbackRequest) -> ManagedReadbackResult: ...
    def abort(self, request: ManagedAbortRequest) -> ManagedAbortReceipt: ...
```

`TemporalExecutionRequest` contains the physical target, portable plan,
credential reference, operation identity, and an optional committed snapshot
reference. The snapshot reference is transport metadata outside the portable
plan. `TemporalExecutionResult` contains an Arrow table or bounded Arrow
artifact plus a temporal receipt.

Managed staging accepts an Arrow artifact, descriptor hash, logical target,
and idempotency key. It returns a provider-invisible stage identity bound to
the submitted artifact hash. Commit is idempotent on the tuple of target,
stage identity, and idempotency key. Reuse with different content is a stable
conflict. Readback addresses the committed snapshot independently and returns
observed data and receipt facts. Abort is idempotent and reports whether the
stage was removed, already absent, or already committed.

## Capability identities

Connectors advertise only behavior they implement and test:

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
storage.snapshot.read/1.0
storage.readback.verify/1.0
storage.visibility.atomic/1.0
storage.abort/1.0
```

An unqualified operation capability describes observable semantics. A
`.pushdown` capability additionally promises that filtering or aggregation is
performed by the provider before rows cross the connector seam.

Support labels are derived summaries, never substitutes for the individual
capabilities:

- `import-export`: descriptor binding and bounded temporal reads, with append
  only when the connector can do it safely;
- `portable-storage`: temporal query and one or more managed write lifecycle
  capabilities; and
- `ots-eligible`: the connector meets the exact neutral capability set
  required by an OTS configuration.

## Receipts and identity

`TemporalReceipt` wraps an existing `NeutralReceipt` and adds:

- temporal descriptor hash;
- requested and observed time ranges;
- output ordering;
- execution location (`provider` or `connector`);
- rows and bytes examined and returned;
- elapsed milliseconds;
- physical snapshot reference when one exists; and
- plan schema version and portable plan hash.

Managed stage, commit, and readback receipts are separate closed documents.
The commit receipt identifies the physical snapshot and visibility guarantee.
The readback receipt contains independently observed schema, content, row,
byte, and time-range facts. A submitted-frame fingerprint cannot populate the
readback fields.

OTC fingerprints remain neutral physical evidence. OTS independently computes
its own identities after reading the Arrow result. Cross-language byte
identity is not assumed.

## Connector process v1

`otc.connector-process/v1` is a local control and artifact transport, not a
query language. Each control frame uses a big-endian unsigned 32-bit length
followed by one UTF-8 JSON object with no unknown fields. Arrow batches travel
as content-addressed Arrow IPC stream artifacts rather than JSON values.

Required envelope fields are:

```text
protocol, message_id, session_id, operation,
connector identity, capability version, resource limits,
credential reference, payload, artifact references
```

Supported operations are `hello`, `describe`, `execute`, `stage`, `commit`,
`readback`, `abort`, and `cancel`. `execute` carries a
`PortableTemporalPlan`. The process never accepts a Timescale SQL string as a
portable operation.

The `hello` exchange pins process protocol, connector, contract, capability,
and portable plan versions before any physical target is opened. Each
operation has a unique session, mandatory maximum rows, bytes, and duration,
and a cancellation token. Standard output contains frames only. Standard
error is bounded, redacted diagnostic text and is never parsed as a receipt.

Credential values never appear in frames. The supervisor resolves a
deployment-owned credential reference into a scoped environment or file
descriptor for the child process. The child cannot request an arbitrary secret
by name.

The operation model is transport-neutral. A later Arrow Flight carrier may
map execution to Flight streams and managed operations to versioned actions,
but must pass the same conformance suite and emit the same neutral receipt
documents.

## Provider support tiers

The process registry names every provider explicitly. The inventory below is
the maximum offline claim; configured-live evidence may narrow it and never
widens it implicitly.

| Provider | Certified role | Execution | Managed lifecycle |
| --- | --- | --- | --- |
| CSV | portable storage | Polars/Arrow | offline verified |
| JSON | portable storage | Polars/Arrow | offline verified on `json://` |
| JSONL | portable storage | Polars/Arrow | offline verified on `jsonl://` |
| SQLite | portable storage; conditionally OTS-eligible | prepared SQL plus Polars | offline verified |
| PostgreSQL | portable storage | prepared SQL plus Polars | offline; live required for OTS eligibility |
| Excel | portable storage | formula-safe values plus Polars | offline verified |
| MaybeSheet | import/export by default | probed connector plus Polars | unsupported until live proof |

### CSV

CSV supports descriptor binding, bounded scan, latest/as-of, bucket
aggregation, and gap filling through the Polars/Arrow evaluator. Managed CSV
storage uses immutable content-addressed snapshots plus a same-directory
atomic pointer manifest. A normal CSV path may be read as import/export; a
managed URI explicitly selects the sidecar layout. Atomic visibility applies
to connector snapshot reads, not to unsupervised readers of a convenience
copy.

### JSON and JSONL

JSON and JSONL support descriptor binding, bounded scan, latest/as-of, bucket
aggregation, and gap filling through the Polars/Arrow evaluator. JSON accepts
one top-level array whose elements are objects. JSONL, including files with an
`.ndjson` suffix, accepts one object per non-empty line. Top-level scalars,
top-level object maps, non-object rows, duplicate object keys, non-finite
numbers, and trailing malformed records are rejected.

Both formats preserve nested JSON values in Arrow where representable, but
the temporal time field, series-key fields, and tag fields must be scalar.
Aggregate value fields must have a supported numeric or otherwise
function-compatible Arrow type. Input bytes, decoded rows, elapsed time, and
materialized output remain independently bounded.

The physical schemes are `json://` and `jsonl://`. Lifecycle mode is not
encoded in the URI. A normal temporal execution without a snapshot reference
reads the addressed file. Managed `stage`, `commit`, `readback`, and `abort`
operations select the sidecar lifecycle by operation type. Execution against
committed storage supplies the physical snapshot reference separately and
reads the immutable snapshot selected by that reference.

Managed JSON and JSONL storage use immutable content-addressed snapshots plus
a same-directory atomic pointer manifest. JSON snapshots serialize a
top-level array of row objects. JSONL snapshots serialize one strict JSON
object per line with a final newline. Top-level row keys follow Arrow schema
order, while nested object keys are sorted recursively; compact encoding makes
repeated publication deterministic without changing column order. OTS still
computes its own independent Arrow identity after readback. Atomic visibility
applies only to connector snapshot reads.

### Excel

Excel supports the same portable read operations for governed worksheet
tables. Managed publication uses content-addressed workbook snapshots and an
atomic pointer manifest. Temporal v1 does not claim formula calculation or
formula evidence. Writes reject targets whose governed range contains formulas
unless a future capability explicitly preserves and verifies them.

### MaybeSheet

MaybeSheet supports descriptor binding, bounded reads, and append through the
`mbs` process. It advertises managed stage, commit, snapshot, atomic
visibility, or readback only after the corresponding `mbs` commands and live
receipts prove those facts. Connector-side Polars evaluation is allowed for
portable reads and is recorded as such.

### SQLite

SQLite supports the full portable plan through prepared SQL where semantics
match and through bounded Polars evaluation otherwise. A connector-owned
metadata schema stores stage identities, idempotency keys, snapshot identities,
and readback facts. Transactions provide atomic connector visibility. One
connector instance does not retain mutable global transaction state across
operations; each managed operation owns its connection or session.

### PostgreSQL

Plain PostgreSQL supports the full portable plan through prepared SQL and a
connector-owned managed-storage schema. Per-operation transactions replace the
current connector-global transaction connection. PostgreSQL does not advertise
Timescale-native retention, continuous aggregates, chunking, compression,
tiering, or gap-fill pushdown. Those belong to the direct native TimescaleDB
path in OTS.

## Error, security, and fallback policy

The extension retains current connector errors and adds stable codes for
`protocol_invalid`, `protocol_version_unsupported`, `resource_limit_exceeded`,
`snapshot_unavailable`, `idempotency_conflict`, and
`visibility_incomplete`.

Provider diagnostics are reduced to bounded safe facts. Error details contain
no SQL text with expanded parameters, credentials, environment values, raw
provider payloads, or unrestricted paths.

Unknown commit outcomes enter reconciliation by idempotency key and snapshot
readback. They never return success speculatively. Cancellation triggers
best-effort abort; a late commit is reconciled rather than blindly retried.

Unsupported operations fail before physical I/O. Connector-side evaluation is
allowed only when the unqualified semantic capability is advertised and the
plan does not require pushdown. Native-only plans never fall back to OTC.

## Conformance

The OTC suite has four layers:

1. JSON-schema and Python round-trip tests for descriptors, plans, envelopes,
   receipts, and every closed enum.
2. Polars/Arrow semantic fixtures for range, latest/as-of, bucket, aggregate,
   gap-fill, ordering, duplicate, timezone, and resource-bound behavior.
3. Process transport tests for framing, handshake, artifact hashes,
   cancellation, limit enforcement, credential isolation, redaction, and
   malformed or adversarial messages.
4. Per-provider offline and configured-live lifecycle tests for every claimed
   capability.

Cross-product parity uses normalized Arrow schemas and logical values. It does
not require Python and Rust serialization bytes or hashes to match. Fixtures
cover DST transitions, fixed and calendar buckets, origins and offsets,
nanosecond timestamps, empty buckets, null aggregates, out-of-order input,
duplicate keys, LOCF and interpolation edges, latest/as-of ties, and limit
failures.

The executable suite is checked in under
[`specification/conformance/timeseries/`](../../../specification/conformance/timeseries/).
Its process cases use the same hello, execute, stage, commit, readback, abort,
and Arrow-artifact shapes consumed by the Rust OTS binding.

## Delivery phases

The immediate 2026-08-29 delivery scope is:

1. Publish the portable plan and receipt schemas plus Python models.
2. Enable the OTS sister repository's direct TimescaleDB path against the
   shared plan semantics.
3. Add Polars/Arrow execution and the local connector-process transport.
4. Add managed CSV, JSON, JSONL, and SQLite implementations with conformance
   evidence.
5. Add PostgreSQL, Excel, and MaybeSheet according to the capability rules
   above.

Later independent tracks add native ClickHouse and TDengine backends in OTS
and an optional Arrow Flight transport in OTC.

## Acceptance criteria

- Existing OTC contract v1 consumers and connector tests remain compatible.
- `PortableTemporalPlan` and every receipt pass closed-schema wire tests.
- The Polars/Arrow evaluator passes the shared temporal semantic corpus.
- Local process tests prove bounds, cancellation, credential isolation,
  redaction, and content-addressed artifact integrity.
- CSV, JSON, JSONL, and SQLite pass offline managed-storage lifecycle
  conformance.
- JSON and JSONL use their normal schemes for both direct and managed
  operations; snapshot selection remains outside the portable plan.
- JSON array/object shape, JSONL record boundaries, duplicate-key rejection,
  nested-value handling, and strict-number behavior pass format conformance.
- PostgreSQL passes offline lifecycle conformance and configured-live evidence
  before any stable claim.
- Excel claims only formula-safe temporal behavior.
- MaybeSheet claims only capabilities backed by actual `mbs` operations and
  configured-live receipts.
- OTS pins exact OTC package, process, plan, and capability versions before
  enabling an OTC-backed profile.
- No native TimescaleDB operation is routed through OTC.

## Primary references

- [OTS/OTC adapter migration analysis](https://github.com/OmniMCP-AI/open-time-series/blob/main/docs/reports/ots-open-table-connector-adapter-migration-analysis.md)
- [Apache Arrow Flight SQL specification](https://arrow.apache.org/docs/format/FlightSql.html)
- [Apache Arrow Flight RPC specification](https://arrow.apache.org/docs/format/Flight.html)
- [Polars time-series functionality](https://docs.pola.rs/user-guide/transformations/time-series/rolling/)
- [TimescaleDB time-series API](https://docs.tigerdata.com/api/latest/hyperfunctions/)
