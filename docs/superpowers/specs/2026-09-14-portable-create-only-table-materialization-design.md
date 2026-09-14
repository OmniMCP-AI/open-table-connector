# Portable Create-Only Table Materialization Design

## Status

Approved in design review on 2026-09-14. Implementation is pending.

Architecture identifier: `otc-portable-materialization/v1`.

This specification is the OTC half of the FinClaw Gold result-backend
closeout. Its companion is
`2026-09-14-gold-result-backend-v2-design.md` in `finclaw-ng`.

The implementation baseline is OTC commit `6a67a4d`, which already contains
verified Excel worksheet-table materialization. FinClaw currently pins that
commit. This document does not authorize a FinClaw-side provider workaround.

## Implementation checklist

The implementation follows the delivery order in Section 13. Each task is
complete only after its focused tests and the task review pass.

### Task 1 — Contract, portable profile, and shared conformance

- [x] Add the `otc.portable-table/v1` logical profile, validation, schema and
      content fingerprints, capability identity, structured materialization
      request/result data, and the outcome/error states required by Sections
      5, 6, and 10.
- [x] Extend `Client.materialize` and connector dispatch with profile and
      idempotency-key validation while preserving legacy unprofiled calls.
- [x] Add shared public-interface conformance cases for the profile,
      capability discovery, fresh readback, idempotency, and safe receipts.

### Task 2 — Portable local JSON and JSONL materialization

- [x] Implement deterministic versioned JSON and JSONL envelopes, typed
      recovery, strict destination validation, atomic no-replace publication,
      and independent readback for local JSON/JSONL.
- [x] Preserve legacy untyped reads without implicit upgrade and add race,
      failure-injection, zero-row, all-null, Unicode, and exact-value tests.

### Task 3 — Portable Excel worksheet materialization

- [x] Align Excel creation with the portable profile, durable adapter-owned
      schema metadata, structured sheet destinations/addresses, revision
      comparison, and typed independent readback while preserving unrelated
      workbook content.
- [x] Add the required conflict, stale-revision, metadata, typed-value, and
      committed-readback-failure tests.

### Task 4 — Maybe native Base create and reconciliation

- [x] Add the provider-native `mbs db-table create` process contract with
      stable table IDs, typed schema/rows, idempotency, and reconciliation.
- [x] Implement the Maybe adapter gate, canonical container validation,
      stable-ID binding/readback, unknown/partial outcomes, and recorded
      conformance coverage without append or name-based emulation.

### Task 5 — Full verification and release evidence

- [x] Run the complete workspace verification and the shared/local/Excel/
      Maybe conformance suites, fixing regressions without weakening the
      create-only contract.
- [x] Record the exact verified commands and evidence needed for OTC to be
      pinned by downstreams; leave only this checklist's completed boxes and
      the final commit/PR metadata to be filled in during delivery.

Verification evidence (2026-09-14):

- `uv run --all-packages pytest -q`: 1598 passed, 5 skipped, 2 warnings.
- Focused portable JSON/JSONL, Excel, Maybe, and SDK regression suites:
  62 passed; universal public-SDK portable materialization conformance: 2
  passed; discovery/contract/CLI regression suites: 74 passed.
- `uv run --all-packages pytest -q packages/cli/tests/test_pipeline.py specification/conformance/universal/test_cli_surface.py`: 80 passed.
- Changed-file Ruff, `uv run --frozen ruff check scripts specification/conformance/universal/test_package_boundaries.py`, and `uv run --frozen mypy scripts`: passed.
- `check_package_metadata.py`, `check_package_boundaries.py`,
  `check_canonical_literals.py`, `check_package_independence.py --build`,
  schema parity, provider independence, `git diff --check`, and
  `scripts/smoke_wheels.py --build`: passed.
- Final review fix pass covers durable local replay identity, committed
  readback mismatch outcomes, real local public-SDK registrations, the exact
  JSON/JSONL v1 wire contract, Maybe reconciliation evidence validation,
  Excel receipt redaction, additive capability metadata, pre-mutation limits,
  and centralized portable success postconditions.

## 1. Decision

OTC will make create-only materialization an explicit, discoverable connector
capability. Local JSON/JSONL, local Excel worksheet tables, and Maybe Base
tables will implement the same SDK interface and the same portable typed-table
profile:

```python
Client.materialize(
    source,
    *,
    to: TableDestination,
    profile: Literal["otc.portable-table/v1"] | None = None,
    idempotency_key: str | None = None,
) -> OperationResult[Table]
```

A successful operation creates one table, returns its exact structured
address and observed revision, and proves the committed table through an
independent typed readback. `materialize` never appends, replaces, clears, or
selects an existing table by a mutable name.

The existing `Client.materialize` seam, `TableDestination` union,
`TableAddress` union, `TableBinding`, and `OperationResult` remain the public
module. Provider-specific serialization, metadata, URL translation, locking,
and recovery stay behind connector adapters.

## 2. Context

The SDK already defines create-only semantics and preserves
`DESTINATION_EXISTS`, but connector support is not discoverable. A connector
may implement `create_table` only to return `UNSUPPORTED_CAPABILITY`.

At the baseline:

- local-files reads strict JSON and JSONL but rejects SDK materialization for
  those formats;
- local-files materializes `file:///...xlsx#sheet=Name`, preserves an existing
  workbook, rejects an existing worksheet, and performs a fresh lexical
  readback;
- Maybe ordinary table writes are append-only and do not satisfy create-only
  semantics;
- Maybe RAW writes cannot prove preservation of typed numbers, booleans, or
  literal empty strings; and
- `https://maybe.ai/sheet/<document-id>` redirects to `www` and is not a valid
  document route. The canonical current route is
  `https://www.maybe.ai/docs/spreadsheets/d/<document-id>`.

FinClaw therefore cannot select one result-backend contract that works across
local JSON, Excel, and Maybe. Adding special writes in FinClaw would duplicate
OTC's safety and type responsibilities.

## 3. Goals

- Advertise create-only materialization independently from append/update
  capabilities.
- Define one closed portable logical type profile shared by JSON, Excel, and
  Maybe.
- Preserve exact schema and values across a fresh client and process.
- Support zero-row tables, all-null columns, Unicode, and exact Int64 values.
- Return exact structured addresses rather than mutable creation names.
- Make conflicts, stale writes, committed readback failures, partial effects,
  and unknown remote outcomes distinguishable.
- Make local creation no-replace and process-race safe.
- Require provider-native Maybe Base creation, stable table IDs, idempotency,
  and reconciliation.
- Provide shared conformance tests that downstreams can use as an admission
  gate.

## 4. Non-goals

- No generic replace, upsert, clear, or append fallback is added.
- No document/workbook creation is folded into Maybe Base materialization.
- No generic transaction spanning providers is promised.
- No nested Arrow types, binary values, arbitrary Python objects, or
  non-finite numbers are included in the first portable profile.
- No FinClaw Gold policy, Gold identity, finance approval, projection layout,
  or registry behavior belongs in OTC.
- No full immutable artifact store, named-reference store, or multi-version
  storage lifecycle is introduced.
- No provider URL or table name is treated as a substitute for a returned
  stable table ID.

## 5. Public interface

### 5.1 Capability

The contract package adds:

```text
table.materialize.create/1.0
```

An adapter may advertise this capability only when it passes the shared
portable materialization conformance suite for every destination form it
claims. Read, append, spreadsheet, and formula capabilities remain separate.

Capability discovery must identify the supported destination modes and
portable profiles. A connector that supports Excel sheet-mode creation but not
JSON direct creation cannot claim both through one ambiguous manifest entry.

### 5.2 Request

`Client.materialize` accepts:

- a bounded table source that can be collected to a logical frame;
- one `TableDestination`;
- the exact profile identifier `otc.portable-table/v1`; and
- a caller-generated, non-secret idempotency key.

Both values are mandatory when the caller requests the advertised portable
create capability. The optional defaults preserve existing unprofiled SDK
calls as a legacy compatibility surface; such calls do not qualify as
`table.materialize.create/1.0` evidence and FinClaw never uses them.

The key is scoped to connector identity plus canonical destination. Reusing a
key with a different schema, content fingerprint, or destination returns
`IDEMPOTENCY_CONFLICT` before a second mutation.

The SDK validates the profile and request shape before connector dispatch.
The connector validates provider limits and representability before mutation.

### 5.3 Successful result

Success requires exactly:

```text
outcome = succeeded
commit = committed
verification = passed
continuation = null
```

The returned `TableBinding` contains:

- the exact `TableAddress`;
- `otc.portable-table/v1`;
- the complete logical schema;
- the exact observed revision;
- row count;
- schema and content fingerprints; and
- ordered mutation and independent-readback receipts.

The returned `Table.read()` and a fresh client's `open(address).read()` must
both recover the same logical schema and values. Verification based only on
the submitted in-memory frame is invalid.

## 6. Portable table profile

`otc.portable-table/v1` is a closed logical profile. It supports nullable:

- UTF-8 string;
- boolean;
- signed Int64;
- finite Float64;
- fixed decimal with declared precision and scale;
- date; and
- UTC datetime with explicit precision.

The profile also supports zero rows, all-null columns, Unicode strings, empty
strings, and the full Int64 range. Column order, row order, field names,
nullability, decimal precision/scale, and datetime precision are significant.

The profile rejects before mutation:

- list, struct, map, binary, object, duration, and provider-defined values;
- NaN and infinities;
- timezone-naive or non-UTC datetimes;
- duplicate or invalid field names;
- values outside the declared integer, decimal, or provider resource limits;
  and
- any physical encoding that cannot be decoded unambiguously into the
  declared logical type.

Adapters may support additional profiles, but capability conformance for this
profile cannot depend on those extensions.

Logical equality requires equal profile, schema, row order, row count, null
positions, and values. There is no floating-point tolerance in v1.

## 7. Destination and address contracts

### 7.1 Local JSON and JSONL

Creation uses `DirectDestination` with an absolute, credential-free URI:

```text
file:///absolute/result.json
file:///absolute/result.jsonl
json:///absolute/result.json
jsonl:///absolute/result.jsonl
```

The suffix and explicit scheme must agree. The returned address is a
`DirectTableAddress` for the canonical absolute URI. Query, fragment,
credentials, relative paths, parent traversal, and symlinks are rejected.

### 7.2 Local Excel

Excel creation is represented as a sheet-mode destination with:

- an absolute `file:///...xlsx` grid;
- one explicit worksheet name;
- anchor `A1`; and
- `header=true`.

The existing string shorthand `file:///...xlsx#sheet=Name` may remain at the
SDK compatibility seam, but canonical wire data keeps `grid`, `worksheet`,
`anchor`, and `header` separate. The returned `SheetModeTableAddress` binds the
workbook grid and exact worksheet table identity.

The adapter supports both a new workbook and a new worksheet in an existing
workbook. It never creates a second table in an existing destination
worksheet.

### 7.3 Maybe Base

Maybe creation uses `BaseModeDestination`:

```yaml
kind: base-mode-destination
container: https://www.maybe.ai/docs/spreadsheets/d/<document-id>
table_name: GoldResult
```

Only the canonical HTTPS host and path are accepted. Query, fragment,
credentials, redirecting short URLs, and mutable sharing links are rejected.
The adapter extracts the provider document ID internally. The existing
`maybe://` form may remain a compatibility input for older callers, but new
wire data and receipts use the canonical HTTPS container.

The document must already exist and be exactly identified. Materialization
creates only a Base table. Success returns:

```yaml
kind: base-mode-table
container: https://www.maybe.ai/docs/spreadsheets/d/<document-id>
table_id: <provider-stable-table-id>
```

`table_name` is a requested creation label, not a durable read identity.
Reads, verification, reconciliation, and downstream evidence use `table_id`.

## 8. Physical formats and typed recovery

### 8.1 JSON envelope

Materialized JSON uses one deterministic UTF-8 file:

```json
{
  "schemaVersion": "otc.table-json/v1",
  "profile": "otc.portable-table/v1",
  "schema": {"fields": []},
  "rows": []
}
```

Key order, field order, scalar encoding, datetime rendering, decimal
rendering, separators, final newline policy, and Unicode policy are fixed by
the codec. The revision is `sha256:` of the committed bytes.

The reader continues to accept legacy top-level row arrays as untyped JSON
input, but only the versioned envelope qualifies as a portable materialized
table. A legacy array cannot be upgraded implicitly during read.

### 8.2 JSONL envelope

Materialized JSONL uses a required metadata record followed by row records:

```jsonl
{"$otc":{"schemaVersion":"otc.table-jsonl/v1","profile":"otc.portable-table/v1","schema":{"fields":[]}}}
{"field":"value"}
```

A zero-row table contains only the metadata record. Legacy JSONL remains a
read-only untyped form. The reserved `$otc` metadata shape is rejected if it
appears as a data row.

### 8.3 Excel metadata

Excel may encode cells lexically or through safe native cell types, but the
workbook must carry adapter-owned metadata sufficient to recover the complete
portable schema in a fresh process. Metadata is bound to the exact worksheet
table and included in the workbook revision.

The metadata layout is private implementation. It must not collide with user
worksheet names, appear as a Gold data row, activate formulas, or require a
FinClaw-specific reader. Missing, ambiguous, stale, or malformed metadata
fails readback; inference is not a fallback.

### 8.4 Maybe typed fields

Maybe uses provider-native Base field definitions. The native create request
includes the complete portable schema and rows. If the provider cannot express
or round-trip a declared type, the adapter rejects before creation. OTC does
not create a companion metadata table and does not encode an unsupported
typed Base table through append or RAW worksheet writes.

## 9. Mutation, concurrency, and recovery

### 9.1 Local JSON/JSONL

The parent directory must already exist and must not be a symlink. The adapter
encodes to a private file in the destination directory, flushes and fsyncs it,
publishes with an atomic no-replace primitive, fsyncs the directory, and then
reopens the final path independently.

An existing destination returns `DESTINATION_EXISTS` without changing bytes.
Concurrent creators produce exactly one success. A loser removes only its own
private file. A crash cannot expose a partially encoded destination as a
successful table.

### 9.2 Excel

For a new workbook, publication is create-only. For an existing workbook, the
adapter observes the exact workbook revision, stages the added worksheet and
metadata, and commits with revision comparison. A competing workbook change
returns `STALE_REVISION` and preserves the winner.

An existing worksheet under case-insensitive Excel naming rules returns
`DESTINATION_EXISTS`. Other worksheets, styles, formulas, and workbook content
must be preserved. The post-commit revision is the hash of the complete
persisted workbook bytes.

### 9.3 Maybe

The process/provider contract gains a native Base create operation equivalent
to:

```text
mbs db-table create
  --uri <canonical-document-url>
  --table-name <name>
  --schema-in <schema>
  --frame-in <rows>
  --idempotency-key <key>
```

Its successful response includes document ID, stable table ID, provider
revision, affected rows, idempotency key, and vendor receipt ID. The adapter
then performs a fresh read by stable table ID.

The provider must enforce idempotency and expose reconciliation by key. A lost
response returns `UNCERTAIN_MUTATION` with `CommitState.UNKNOWN` and a
`ReconciliationReference`. Callers must reconcile and must not create with a
new key. Name lookup is never reconciliation.

If the installed mbs/provider lacks native create, stable IDs, typed fields,
idempotency, or reconciliation, the adapter does not advertise
`table.materialize.create/1.0` for Maybe and returns
`UNSUPPORTED_CAPABILITY` before mutation.

## 10. Outcomes and errors

| Condition | Outcome | Commit | Verification | Error |
| --- | --- | --- | --- | --- |
| Invalid URI, schema, profile, or value | `rejected` | `not_started` | `skipped` | `INVALID_TARGET` or `INVALID_SCHEMA` |
| Capability unavailable | `rejected` | `not_started` | `skipped` | `UNSUPPORTED_CAPABILITY` |
| Destination already exists | `rejected` | `not_started` | `skipped` | `DESTINATION_EXISTS` |
| Idempotency key reused for another request | `rejected` | `not_started` | `skipped` | `IDEMPOTENCY_CONFLICT` |
| Concurrent target revision changed | `rejected` | `not_committed` | `skipped` | `STALE_REVISION` |
| Created and exact typed readback passed | `succeeded` | `committed` | `passed` | none |
| Commit succeeded but readback differs | `failed` | `committed` | `failed` | `READBACK_MISMATCH` |
| Provider reports partial effects | `partial` | `partial` | `failed` | `PARTIAL_EFFECT` |
| Remote outcome cannot be determined | `unknown` | `unknown` | `unavailable` | `UNCERTAIN_MUTATION` |

Known receipts and reconciliation references survive every post-dispatch
failure. Safe details contain no credentials, access tokens, temporary file
contents, or provider response bodies.

## 11. Requirements

- **OTC-MAT-001:** capability discovery identifies create-only
  materialization and supported profiles/modes.
- **OTC-MAT-002:** successful materialization returns a structured exact
  address, complete logical schema, exact revision, and ordered write/readback
  receipts.
- **OTC-MAT-003:** `otc.portable-table/v1` round-trips its closed type set in a
  fresh process without lexical drift.
- **OTC-MAT-004:** unsupported types and resource-limit violations fail before
  mutation.
- **OTC-MAT-005:** local JSON and JSONL use versioned, deterministic,
  self-describing single-file encodings.
- **OTC-MAT-006:** local publication is atomic, no-replace, symlink-safe, and
  process-race safe.
- **OTC-MAT-007:** Excel preserves unrelated workbook content, rejects an
  existing worksheet, uses revision comparison, and restores types from
  durable metadata.
- **OTC-MAT-008:** Maybe creation is provider-native and returns a stable Base
  table ID; append and name-based emulation are forbidden.
- **OTC-MAT-009:** Maybe create is idempotent and reconcilable after an unknown
  outcome.
- **OTC-MAT-010:** committed readback failures preserve the committed state and
  return `READBACK_MISMATCH`.
- **OTC-MAT-011:** all adapters preserve exact empty, null, Unicode, numeric,
  decimal, date, and UTC datetime cases admitted by the portable profile.
- **OTC-MAT-012:** conformance evidence distinguishes recorded, local, and live
  provider results.

## 12. Verification

The shared conformance suite covers every requirement through the public SDK
interface. Connector-private helper tests do not substitute for interface
tests.

### 12.1 Shared cases

- capability discovery and unsupported-profile rejection;
- every portable type, boundary value, null pattern, empty string, Unicode,
  zero-row table, and all-null column;
- schema, column-order, row-order, row-count, and content fingerprints;
- existing destination, idempotent replay, idempotency conflict, and stale
  revision;
- pre-dispatch rejection, post-commit mismatch, partial effect, timeout, and
  unknown outcome;
- fresh-client and fresh-process address readback; and
- secret-safe wire results and receipts.

### 12.2 Local JSON/JSONL

- deterministic golden bytes and byte revisions;
- legacy untyped read compatibility without implicit upgrade;
- file/json/jsonl URI routing and suffix mismatch rejection;
- no parent creation, symlink rejection, permissions failures, and bounded
  resource limits;
- two-process create race with one winner; and
- injected failures before fsync, before publication, and after publication.

### 12.3 Excel

- new workbook and existing workbook creation;
- case-insensitive worksheet conflict;
- unrelated worksheet/formula/style preservation;
- concurrent workbook winner preservation;
- durable schema metadata and fresh typed readback; and
- committed workbook plus failed readback evidence.

### 12.4 Maybe

- recorded native command request/response contract;
- stable table-ID binding and read by ID;
- provider type/limit rejection before creation;
- duplicate name, duplicate key, changed payload, timeout, reconciliation,
  partial, and readback mismatch cases; and
- an opt-in disposable live test using a fresh document namespace.

The live test creates and reads a Base table, reconciles one injected unknown
response if the provider test surface permits it, verifies exact portable
values, records stable IDs/revisions/receipts, and deletes only its disposable
test document or table. Recorded responses cannot promote the Maybe capability
to live-supported status.

## 13. Compatibility and rollout

- Existing untyped JSON/JSONL reads remain supported.
- Existing unprofiled `Client.materialize(source, to=...)` calls remain a
  legacy compatibility surface. They do not advertise or prove the portable
  capability until the caller supplies both profile and idempotency key.
- Existing `file:///...xlsx#sheet=Name` callers remain accepted at the SDK
  compatibility seam while canonical wire addresses become structured.
- Existing Maybe append writes remain a separate capability and are never used
  by `materialize`.
- Existing `maybe://` reads may remain supported, but new materialization
  requests, returned addresses, and receipts use canonical HTTPS containers.
- The capability is not advertised until the corresponding adapter passes its
  required conformance, including the Maybe live gate for live support.

Delivery order is contract/profile and shared conformance, JSON/JSONL,
Excel alignment, Maybe native process contract and adapter, full workspace
verification, then an exact OTC release or commit for FinClaw to pin.

## 14. Rejected alternatives

- **FinClaw writes JSON directly:** duplicates atomicity, type, revision, and
  receipt behavior outside OTC.
- **Maybe check-then-append:** races, permits partial effects, and cannot return
  a trustworthy created-table identity.
- **Name-based Maybe readback:** names are creation labels, not exact table
  identities.
- **Plain JSON row arrays:** cannot preserve zero-row or all-null schema.
- **JSON schema sidecars:** introduce a two-file partial-commit problem.
- **Excel lexical equality only:** cannot prove independent typed readback.
- **Provider URL as table identity:** a document URL identifies the container;
  the returned stable table ID identifies the table.
- **A full artifact store:** exceeds the required table-creation lifecycle and
  introduces unrelated reference-management interfaces.
