# Portable Time-Series Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a versioned portable time-series execution and managed-storage extension to Open Table Connector for CSV, JSON, JSONL, Excel, MaybeSheet, SQLite, and PostgreSQL without turning OTC into the native TimescaleDB path.

**Architecture:** Introduce two deep packages. `open-table-connector-timeseries` owns the closed `PortableTemporalPlan v1`, temporal descriptors, neutral receipts, managed-storage requests, and the Polars/Arrow evaluator. `open-table-connector-process` carries those models over a bounded local process protocol. Existing connectors opt into the extension through small provider modules; native TimescaleDB remains a direct OTS adapter in the sister repository.

**Tech Stack:** Python 3.11–3.14, frozen dataclasses, PyArrow 14–19, Polars 1.x, JSON Schema 2020-12, pytest 9, Python DB-API, openpyxl 3.1, the existing MaybeSheet process seam, and uv workspace packaging.

**Spec:** `docs/superpowers/specs/2026-08-29-portable-time-series-storage-design.md`

**Companion OTS spec:** [Native and OTC Storage Backends Design](https://github.com/OmniMCP-AI/open-time-series/blob/main/docs/superpowers/specs/2026-08-29-native-and-otc-storage-backends-design.md)

**Companion OTS plan:** [Native and OTC Storage Backends Implementation Plan](https://github.com/OmniMCP-AI/open-time-series/blob/main/docs/superpowers/plans/2026-08-29-native-and-otc-storage-backends.md)

## Global Constraints

- Preserve source and wire compatibility of `open-table-connector-contract` v1 and all existing connector APIs.
- Time-series behavior is an extension over `TableMode.BASE`; do not add a third table mode.
- OTC accepts only `PortableTemporalPlan v1` for temporal execution. It never parses Timescale Core SQL or accepts arbitrary SQL as the portable contract.
- OTC does not implement native TimescaleDB, ClickHouse, or TDengine features. Continuous aggregates, retention, columnstore/compression, tiering, hyperfunctions, and subscriptions remain outside this plan.
- Every request carries non-zero maximum rows, bytes, and duration. Unsupported operations and missing pushdown capabilities fail before opening the target.
- Wire timestamps are RFC 3339 UTC at the declared precision. Ranges are half-open `[start, end)`.
- Physical URIs and credential references stay outside descriptor and plan hashes. Credential values never enter control frames, receipts, exceptions, or logs.
- Neutral OTC hashes and receipts are physical evidence only. They are never asserted to equal OTS identities across Python and Rust.
- Provider capabilities are advertised only after the matching offline test passes; configured-live evidence is additionally required before PostgreSQL or MaybeSheet lifecycle claims are marked stable.
- Work in strict red-green-refactor slices. Each task ends with its focused tests, `git diff --check`, and a Conventional Commit.
- The immediate scope is phases 1–5. Arrow Flight and native ClickHouse/TDengine work are not part of these tasks.

---

## Cross-Repository Delivery Order

1. Complete OTC Tasks 1 and 2 and publish their schemas and golden fixtures.
2. Complete OTS Tasks 1–3, vendoring the exact OTC fixture files and checksum.
3. Complete OTC Tasks 3–5 and OTS Tasks 4–6; the local process recording client is the integration boundary.
4. Complete OTC Tasks 6–11 and the matching OTS conformance work.
5. Commit OTC Task 12 conformance without an attestation, complete OTS Tasks 9 and the non-attestation portion of Task 10, then write the same compatibility record into both repositories. The record pins the two pre-attestation surface commits so its own commits do not create a hash cycle.

The repositories remain independently buildable. Tests may read vendored fixtures but must not import code or resolve files from a sibling checkout.

## File Map

### New time-series package

- `packages/timeseries/pyproject.toml` — package metadata and Arrow/Polars dependencies.
- `packages/timeseries/src/open_table_connector/timeseries/__init__.py` — deliberately small public surface.
- `packages/timeseries/src/open_table_connector/timeseries/capabilities.py` — closed capability identities and support summaries.
- `packages/timeseries/src/open_table_connector/timeseries/descriptor.py` — temporal descriptor and canonical hash.
- `packages/timeseries/src/open_table_connector/timeseries/plan.py` — closed plan nodes, bounds, wire codec, and plan hash.
- `packages/timeseries/src/open_table_connector/timeseries/receipts.py` — execution and managed lifecycle receipts.
- `packages/timeseries/src/open_table_connector/timeseries/storage.py` — request/result records and the two stable protocols.
- `packages/timeseries/src/open_table_connector/timeseries/evaluator.py` — bounded Polars/Arrow execution.
- `packages/timeseries/src/open_table_connector/timeseries/lowering.py` — shared prepared-SQL lowering records.
- `packages/timeseries/tests/fixtures/*.json` — canonical valid and invalid v1 documents.
- `packages/timeseries/tests/test_*.py` — wire, semantics, bounds, and error tests.

### New process package

- `packages/process/pyproject.toml` — package metadata and `otc-process` entry point.
- `packages/process/src/open_table_connector/process/envelope.py` — closed control envelope models.
- `packages/process/src/open_table_connector/process/framing.py` — unsigned big-endian length framing.
- `packages/process/src/open_table_connector/process/artifacts.py` — content-addressed Arrow IPC artifacts.
- `packages/process/src/open_table_connector/process/credentials.py` — deployment-owned reference resolver protocol.
- `packages/process/src/open_table_connector/process/registry.py` — explicit connector/executor registration.
- `packages/process/src/open_table_connector/process/server.py` — handshake, dispatch, cancellation, and redaction.
- `packages/process/src/open_table_connector/process/__main__.py` — stdio entry point.
- `packages/process/tests/test_*.py` — adversarial framing, handshake, artifact, dispatch, and cancellation tests.

### Provider extensions

- `packages/local_files/src/open_table_connector/local_files/managed_snapshots.py` — immutable snapshot and pointer-manifest primitive.
- `packages/local_files/src/open_table_connector/local_files/temporal_csv.py` — CSV evaluator and managed store.
- `packages/local_files/src/open_table_connector/local_files/json_codec.py` — strict shared JSON/JSONL Arrow codec.
- `packages/local_files/src/open_table_connector/local_files/json_connector.py` — ordinary `json://` and `jsonl://` reads.
- `packages/local_files/src/open_table_connector/local_files/temporal_json.py` — JSON/JSONL evaluator and managed store.
- `packages/local_files/src/open_table_connector/local_files/temporal_excel.py` — workbook evaluator and formula-safe managed store.
- `packages/sqlite/src/open_table_connector/sqlite/temporal.py` — prepared SQLite lowering and managed lifecycle.
- `packages/postgres/src/open_table_connector/postgres/temporal.py` — prepared PostgreSQL lowering and managed lifecycle.
- `packages/maybe_sheet/src/open_table_connector/maybe_sheet/temporal.py` — recording/live capability probe and portable execution.
- `packages/conformance/src/open_table_connector/conformance/timeseries.py` — reusable semantic and lifecycle assertions.
- `specification/conformance/timeseries/*.py` — cross-provider matrix and process end-to-end tests.

### Machine-readable specification

- `specification/schemas/temporal-table-descriptor-v1.schema.json`
- `specification/schemas/portable-temporal-plan-v1.schema.json`
- `specification/schemas/temporal-receipt-v1.schema.json`
- `specification/schemas/managed-stage-receipt-v1.schema.json`
- `specification/schemas/managed-commit-receipt-v1.schema.json`
- `specification/schemas/managed-readback-receipt-v1.schema.json`
- `specification/schemas/managed-abort-receipt-v1.schema.json`
- `specification/schemas/connector-process-envelope-v1.schema.json`
- `specification/fixtures/timeseries/v1/*.json`
- `specification/fixtures/timeseries/v1/manifest.sha256`

---

### Task 1: Publish the temporal descriptor and portable plan v1

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `packages/timeseries/pyproject.toml`
- Create: `packages/timeseries/src/open_table_connector/timeseries/__init__.py`
- Create: `packages/timeseries/src/open_table_connector/timeseries/capabilities.py`
- Create: `packages/timeseries/src/open_table_connector/timeseries/descriptor.py`
- Create: `packages/timeseries/src/open_table_connector/timeseries/plan.py`
- Create: `packages/timeseries/tests/test_descriptor.py`
- Create: `packages/timeseries/tests/test_plan_wire.py`
- Create: `specification/schemas/temporal-table-descriptor-v1.schema.json`
- Create: `specification/schemas/portable-temporal-plan-v1.schema.json`
- Create: `specification/fixtures/timeseries/v1/scan-range.json`
- Create: `specification/fixtures/timeseries/v1/latest.json`
- Create: `specification/fixtures/timeseries/v1/as-of.json`
- Create: `specification/fixtures/timeseries/v1/bucket-aggregate.json`
- Create: `specification/fixtures/timeseries/v1/gap-fill.json`
- Create: `specification/fixtures/timeseries/v1/manifest.sha256`

**Interfaces:**
- Produces `TemporalTableDescriptor`, `PortableTemporalPlan`, `ResourceBounds`, `ScanRange`, `Latest`, `AsOf`, `BucketAggregate`, `GapFill`, `plan_from_wire()`, and `portable_plan_hash()`.
- Consumes only `TableURI`-independent Arrow schema data; no provider package dependency is allowed.
- `packages/timeseries/pyproject.toml` depends on `open-table-connector-contract==0.1.0`, `polars>=1,<2`, and `pyarrow>=14,<20` through workspace sources. Add `jsonschema>=4,<5` and `PyYAML>=6,<7` to the root dev group for schema and compatibility tests.
- `capabilities.py` defines exactly `timeseries.describe/1.0`, `timeseries.scan.range/1.0`, `timeseries.scan.range.pushdown/1.0`, `timeseries.lookup.latest/1.0`, `timeseries.lookup.asof/1.0`, `timeseries.aggregate.window/1.0`, `timeseries.aggregate.window.pushdown/1.0`, `timeseries.fill/1.0`, `timeseries.write.append/1.0`, `timeseries.write.upsert/1.0`, `storage.stage/1.0`, `storage.commit.idempotent/1.0`, `storage.snapshot.read/1.0`, `storage.readback.verify/1.0`, `storage.visibility.atomic/1.0`, and `storage.abort/1.0`.

- [ ] **Step 1: Write failing descriptor and closed-wire tests**

Use a canonical descriptor with `ts`, series key `symbol`, tag `venue`, value `price`, UTC nanoseconds, duplicate policy `replace-latest`, and ingestion field `received_at`. Assert that field reordering is rejected, UTC normalization is stable, every unknown key is rejected recursively, and descriptor hashes change when any descriptor field or normalized Arrow schema changes.

~~~python
def test_scan_range_round_trips_as_a_closed_document() -> None:
    plan = PortableTemporalPlan(
        schema_version="otc.portable-temporal-plan/v1",
        descriptor_hash=DESCRIPTOR_HASH,
        relation="ticks",
        required_capabilities=("timeseries.scan.range/1.0",),
        resource_bounds=ResourceBounds(max_rows=1000, max_bytes=1_000_000, max_duration_ms=5000),
        operation=ScanRange(
            start="2026-08-29T00:00:00.000000000Z",
            end="2026-08-30T00:00:00.000000000Z",
            projection=("ts", "symbol", "price"),
            tag_predicates=(TagPredicate(field="symbol", operator="in", values=("AAPL",)),),
        ),
        output_order=(OrderKey(field="symbol", direction="asc"), OrderKey(field="ts", direction="asc")),
        result_row_limit=500,
    )
    assert plan_from_wire(plan.to_wire()) == plan
    assert set(plan.to_wire()) == {
        "schema_version", "descriptor_hash", "relation",
        "required_capabilities", "resource_bounds", "operation",
        "output_order", "result_row_limit",
    }
~~~

- [ ] **Step 2: Run the tests and verify the red phase**

Run:

~~~bash
uv run python -m pytest packages/timeseries/tests/test_descriptor.py packages/timeseries/tests/test_plan_wire.py -q
~~~

Expected: collection fails because the package and models do not exist.

- [ ] **Step 3: Implement immutable models and validation**

Use frozen, slotted dataclasses and closed string enums. `TemporalTableDescriptor` fields are `time_field`, `timezone`, `precision`, `series_key_fields`, `tag_fields`, `value_fields`, `ingestion_time_field`, `duplicate_policy`, and `ordering`. Precision values are `second`, `millisecond`, `microsecond`, and `nanosecond`; duplicate policies are `preserve`, `reject`, and `replace-latest`; ordering values are `unspecified`, `nondecreasing`, and `strict`.

Define exactly these root operation kinds: `scan_range`, `latest`, `as_of`, `bucket_aggregate`, and `gap_fill`. Define aggregate functions `count`, `min`, `max`, `sum`, `avg`, `first`, and `last`; fill modes `null`, `constant`, `locf`, and `linear`. Reject zero bounds, unbounded ranges, non-UTC wire timestamps, duplicate projections/order keys, aggregates over non-value fields, predicates over undeclared fields, and result limits above `max_rows`.

Canonical hashes use `sha256(canonical_json_bytes)`, where canonical JSON is UTF-8 with sorted keys, no insignificant whitespace, and no non-finite numbers. Descriptor canonical input includes `arrow_schema.serialize().to_pybytes().hex()`. Plan canonical input is exactly `plan.to_wire()`. Physical targets and credentials are not model fields.

- [ ] **Step 4: Add strict JSON schemas and golden fixtures**

Use JSON Schema 2020-12, `additionalProperties: false` at every object, discriminated `oneOf` branches for operations/buckets/fills, and positive integer bounds. Generate `manifest.sha256` with one line per fixture in lexical filename order:

~~~text
<lowercase-sha256><two spaces><filename>
~~~

Validate every fixture with the Python codec and the schema. The future OTS implementation vendors these files byte-for-byte.

- [ ] **Step 5: Run focused tests and package build**

~~~bash
uv lock
uv run --frozen python -m pytest packages/timeseries/tests -q
uv build --package open-table-connector-timeseries
git diff --check
~~~

Expected: all time-series model tests pass and the wheel/sdist are built.

- [ ] **Step 6: Commit**

~~~bash
git add pyproject.toml uv.lock packages/timeseries specification/schemas/temporal-table-descriptor-v1.schema.json specification/schemas/portable-temporal-plan-v1.schema.json specification/fixtures/timeseries/v1
git commit -m "feat: define portable temporal plan v1"
~~~

### Task 2: Add temporal receipts and managed-storage protocols

**Files:**
- Create: `packages/timeseries/src/open_table_connector/timeseries/receipts.py`
- Create: `packages/timeseries/src/open_table_connector/timeseries/storage.py`
- Modify: `packages/timeseries/src/open_table_connector/timeseries/__init__.py`
- Create: `packages/timeseries/tests/test_receipts.py`
- Create: `packages/timeseries/tests/test_storage_protocols.py`
- Create: `specification/schemas/temporal-receipt-v1.schema.json`
- Create: `specification/schemas/managed-stage-receipt-v1.schema.json`
- Create: `specification/schemas/managed-commit-receipt-v1.schema.json`
- Create: `specification/schemas/managed-readback-receipt-v1.schema.json`
- Create: `specification/schemas/managed-abort-receipt-v1.schema.json`
- Create: `specification/fixtures/timeseries/v1/temporal-receipt.json`
- Create: `specification/fixtures/timeseries/v1/managed-lifecycle.json`
- Modify: `specification/fixtures/timeseries/v1/manifest.sha256`

**Interfaces:**
- Produces:

~~~python
class PortableTemporalExecutor(Protocol):
    def execute(self, request: TemporalExecutionRequest) -> TemporalExecutionResult: ...

class ManagedTemporalStore(Protocol):
    def stage(self, request: ManagedStageRequest) -> ManagedStageReceipt: ...
    def commit(self, request: ManagedCommitRequest) -> ManagedCommitReceipt: ...
    def readback(self, request: ManagedReadbackRequest) -> ManagedReadbackResult: ...
    def abort(self, request: ManagedAbortRequest) -> ManagedAbortReceipt: ...
~~~

- `TemporalExecutionRequest` carries `target: TableURI`, `plan`, `credential_reference: str | None`, `operation_id`, and `snapshot_reference: str | None`. Snapshot selection is transport metadata and never enters `PortableTemporalPlan`.
- `ManagedStageRequest` carries a content-addressed Arrow artifact reference, descriptor hash, logical target, physical target, and idempotency key.
- `ManagedReadbackResult` carries independently observed Arrow data or an Arrow artifact reference plus `ManagedReadbackReceipt`.

- [ ] **Step 1: Write failing receipt/lifecycle tests**

Assert closed round trips, state transitions, safe URI serialization, and that a readback receipt cannot be constructed from submitted facts alone.

~~~python
def test_readback_requires_independent_observation() -> None:
    with pytest.raises(ValueError, match="observed_at"):
        ManagedReadbackReceipt(
            schema_version="otc.managed-readback-receipt/v1",
            operation_id="readback-1",
            snapshot_id="sha256:" + "a" * 64,
            observed_at=None,
            observed_schema_hash="sha256:" + "b" * 64,
            observed_content_hash="sha256:" + "c" * 64,
            observed_rows=2,
            observed_bytes=128,
            observed_range=TimeRange(START, END),
        )
~~~

Test idempotency conflicts on the tuple `(logical_target, stage_id, idempotency_key)`, abort dispositions `removed`, `already_absent`, and `already_committed`, and commit visibility values `atomic` and `non_atomic`.

- [ ] **Step 2: Run focused tests and verify red**

~~~bash
uv run --frozen python -m pytest packages/timeseries/tests/test_receipts.py packages/timeseries/tests/test_storage_protocols.py -q
~~~

Expected: collection fails for the missing modules.

- [ ] **Step 3: Implement the closed request/result and receipt records**

`TemporalReceipt` wraps `NeutralReceipt` and adds descriptor hash, requested/observed ranges, order, execution location, examined/returned rows and bytes, elapsed milliseconds, snapshot reference, schema version, and portable plan hash. Enforce `returned <= examined <= request bounds`.

Stage receipts bind `stage_id` to the submitted artifact hash and are explicitly invisible. Commit receipts bind target, stage, idempotency key, snapshot identity, committed timestamp, and visibility guarantee. Readback receipts require a new observation timestamp and observed schema/content/range/size facts. Abort receipts report one closed disposition.

Add stable error codes in the extension package: `protocol_invalid`, `protocol_version_unsupported`, `resource_limit_exceeded`, `snapshot_unavailable`, `idempotency_conflict`, and `visibility_incomplete`. Do not change the existing contract enum.

- [ ] **Step 4: Add schemas, lifecycle fixture, and manifest hashes**

The lifecycle fixture contains one stage, commit, readback, and abort document sharing stable IDs. Each schema rejects OTS plan hashes, acceptance states, credential values, raw SQL, and unknown provider payload fields.

- [ ] **Step 5: Run tests and commit**

~~~bash
uv run --frozen python -m pytest packages/timeseries/tests -q
git diff --check
git add packages/timeseries specification/schemas specification/fixtures/timeseries/v1
git commit -m "feat: add temporal storage receipts"
~~~

### Task 3: Implement bounded ScanRange, Latest, and AsOf evaluation

**Files:**
- Create: `packages/timeseries/src/open_table_connector/timeseries/evaluator.py`
- Create: `packages/timeseries/tests/fixtures.py`
- Create: `packages/timeseries/tests/test_evaluator_lookup.py`
- Create: `packages/timeseries/tests/test_evaluator_bounds.py`
- Modify: `packages/timeseries/src/open_table_connector/timeseries/__init__.py`

**Interfaces:**
- Produces `PolarsTemporalExecutor(source: TemporalSource)`.
- Produces `TemporalSource.read_bounded(target, projection, predicates, bounds) -> pa.Table`.
- Consumes `TemporalExecutionRequest` and returns `TemporalExecutionResult` with Arrow data and `execution_location="connector"`.

- [ ] **Step 1: Write semantic and limit tests**

Build an in-memory Arrow fixture in `fixtures.py` containing two symbols, out-of-order rows, duplicate event timestamps, nanosecond timestamps, null values, and an ingestion timestamp. Cover exact half-open exclusion at `end`, tag equality/`IN`, projection, deterministic ordering, latest/as-of ties under all three duplicate policies, missing series, and zero matching rows.

Add malicious source doubles that over-return rows/bytes or delay past the deadline. Assert `resource_limit_exceeded` and no partial success receipt.

- [ ] **Step 2: Run tests and verify red**

~~~bash
uv run --frozen python -m pytest packages/timeseries/tests/test_evaluator_lookup.py packages/timeseries/tests/test_evaluator_bounds.py -q
~~~

Expected: import or unsupported-operation failures.

- [ ] **Step 3: Implement one bounded scan pipeline**

Read only declared projection plus fields needed for filtering/order/tie-breaking. Convert Arrow to lazy Polars, validate the Arrow schema against the descriptor, apply range and tag predicates, resolve duplicate policy, then sort and collect. Check elapsed time before and after source read and every materialization. Measure returned Arrow IPC bytes and reject rows or bytes above request bounds.

`Latest` groups by declared series keys and chooses the maximum event time, then ingestion time when declared. `AsOf` applies `time <= as_of` before the same selection. `preserve` requires deterministic output of all exact ties; `reject` fails on ties; `replace-latest` requires ingestion time.

- [ ] **Step 4: Run tests and commit**

~~~bash
uv run --frozen python -m pytest packages/timeseries/tests/test_evaluator_lookup.py packages/timeseries/tests/test_evaluator_bounds.py -q
git diff --check
git add packages/timeseries
git commit -m "feat: evaluate portable temporal lookups"
~~~

### Task 4: Implement bucket aggregation and gap filling

**Files:**
- Modify: `packages/timeseries/src/open_table_connector/timeseries/evaluator.py`
- Create: `packages/timeseries/src/open_table_connector/timeseries/buckets.py`
- Create: `packages/timeseries/tests/test_evaluator_buckets.py`
- Create: `packages/timeseries/tests/test_evaluator_gapfill.py`
- Create: `packages/timeseries/tests/fixtures/calendar-cases.json`

**Interfaces:**
- Produces pure `fixed_bucket_start()` and `calendar_bucket_start()` helpers.
- Extends `PolarsTemporalExecutor` for `BucketAggregate` and `GapFill`.

- [ ] **Step 1: Write failing fixed/calendar bucket tests**

Cover nanosecond fixed buckets with origin and offset; UTC and `America/New_York` daily/monthly buckets across both 2026 DST transitions; week starts; quarter/year boundaries; empty input; null aggregates; grouped series; and `first`/`last` tie rules. Assert bucket labels match the golden calendar fixture.

- [ ] **Step 2: Write failing fill tests**

Cover `null`, typed constants, LOCF, and linear interpolation. Assert LOCF does not look before `start`, interpolation requires observations on both sides inside the range, integer input produces the declared output type, and no fill crosses series groups.

- [ ] **Step 3: Run tests and verify red**

~~~bash
uv run --frozen python -m pytest packages/timeseries/tests/test_evaluator_buckets.py packages/timeseries/tests/test_evaluator_gapfill.py -q
~~~

Expected: unsupported operation failures.

- [ ] **Step 4: Implement bucket and fill semantics**

Fixed buckets use integer nanosecond arithmetic, never floating point. Calendar buckets use `zoneinfo.ZoneInfo` and calendar field arithmetic before converting labels back to UTC. Generate bucket domains only within the requested range and enforce the row bound before materializing the Cartesian product of series groups and buckets.

Implement aggregates with explicit output types. `first`/`last` sort by event and optional ingestion time before aggregation. Apply fill only after aggregate output is complete and sorted.

- [ ] **Step 5: Run tests and commit**

~~~bash
uv run --frozen python -m pytest packages/timeseries/tests -q
git diff --check
git add packages/timeseries
git commit -m "feat: add portable temporal aggregation"
~~~

### Task 5: Add otc.connector-process/v1

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `packages/process/pyproject.toml`
- Create: `packages/process/src/open_table_connector/process/__init__.py`
- Create: `packages/process/src/open_table_connector/process/envelope.py`
- Create: `packages/process/src/open_table_connector/process/framing.py`
- Create: `packages/process/src/open_table_connector/process/artifacts.py`
- Create: `packages/process/src/open_table_connector/process/credentials.py`
- Create: `packages/process/src/open_table_connector/process/registry.py`
- Create: `packages/process/src/open_table_connector/process/server.py`
- Create: `packages/process/src/open_table_connector/process/__main__.py`
- Create: `packages/process/tests/test_envelope.py`
- Create: `packages/process/tests/test_framing.py`
- Create: `packages/process/tests/test_artifacts.py`
- Create: `packages/process/tests/test_server.py`
- Create: `packages/process/tests/test_security.py`
- Create: `specification/schemas/connector-process-envelope-v1.schema.json`

**Interfaces:**
- Produces `read_frame(stream, max_frame_bytes) -> Mapping[str, object]` and `write_frame(stream, envelope) -> None`.
- Produces `ArtifactStore.put_arrow(table) -> ArtifactReference` and `get_arrow(reference, bounds) -> pa.Table`.
- Produces `CredentialResolver.resolve(reference, connector_id) -> CredentialLease`.
- Produces `ConnectorProcessServer(registry, artifact_store, credential_resolver, clock)`.
- Supports exactly `hello`, `describe`, `execute`, `stage`, `commit`, `readback`, `abort`, and `cancel`.
- `packages/process/pyproject.toml` depends on the workspace contract/timeseries packages and `pyarrow>=14,<20`; it contains no provider dependency.
- Every envelope contains exactly `protocol`, `message_id`, `session_id`, `operation`, `connector`, `capability_version`, `resource_limits`, `credential_reference`, `payload`, and `artifact_references`.
- An `execute` payload carries `target`, `portable_plan`, and optional `snapshot_reference` as sibling fields; the snapshot reference never changes portable plan bytes or hash.

- [ ] **Step 1: Write framing and envelope tests**

Assert a four-byte unsigned big-endian length prefix, one UTF-8 JSON object, exact required envelope keys, unique message/session IDs, maximum frame rejection before allocation, truncated-frame rejection, invalid UTF-8 rejection, duplicate JSON key rejection, unknown-field rejection, and clean EOF between frames.

- [ ] **Step 2: Write handshake, artifact, and security tests**

`hello` must pin process protocol `otc.connector-process/v1`, connector identity/version, contract version, capability versions, and portable plan version before target resolution. Test SHA-256-addressed Arrow IPC stream artifacts, tamper detection, symlink rejection, ownership/permission checks, expiry cleanup, cancellation, bounded stderr, and secret redaction. stdout must contain frames only.

- [ ] **Step 3: Run tests and verify red**

~~~bash
uv run python -m pytest packages/process/tests -q
~~~

Expected: collection fails because the process package is absent.

- [ ] **Step 4: Implement the minimal synchronous supervisor**

Parse frames with `json.loads(..., object_pairs_hook=reject_duplicate_keys)`. Dispatch sessions through an explicit registry keyed by connector ID; do not import connectors by arbitrary module path. Resolve credentials only after `hello` and capability validation, give the handler a scoped lease, and dispose it in `finally`. Treat cancellation as a session state transition and call provider abort best-effort.

Artifacts live under a supervisor-configured root, are named by lower-case SHA-256, and are written to a same-directory temporary file followed by `os.replace`. Verify hash and bounds on every read. Responses include artifact references, never Arrow bytes in JSON.

- [ ] **Step 5: Add the command entry point**

Define:

~~~toml
[project.scripts]
otc-process = "open_table_connector.process.__main__:main"
~~~

`main()` reads stdin in binary mode, writes stdout in binary mode, directs bounded redacted diagnostics to stderr, and exits non-zero only for process-fatal framing failures. Operation failures return a framed safe error.

- [ ] **Step 6: Run tests, build, and commit**

~~~bash
uv lock
uv run --frozen python -m pytest packages/process/tests -q
uv build --package open-table-connector-process
git diff --check
git add pyproject.toml uv.lock packages/process specification/schemas/connector-process-envelope-v1.schema.json
git commit -m "feat: add local connector process protocol"
~~~

### Task 6: Add managed CSV temporal storage

**Files:**
- Modify: `packages/local_files/pyproject.toml`
- Create: `packages/local_files/src/open_table_connector/local_files/managed_snapshots.py`
- Create: `packages/local_files/src/open_table_connector/local_files/temporal_csv.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/__init__.py`
- Create: `packages/local_files/tests/test_temporal_csv.py`
- Create: `packages/local_files/tests/test_managed_csv.py`
- Create: `packages/local_files/tests/test_managed_snapshot_recovery.py`

**Interfaces:**
- Produces internal `ManagedSnapshotStore.stage_artifact(...)`, `publish_snapshot(...)`, `resolve_snapshot(target: TableURI, snapshot_reference: str) -> Path`, `read_snapshot(...)`, and `abort_stage(...)` primitives used by every managed local format.
- Produces `CsvTemporalExecutor` and `CsvManagedTemporalStore`.
- Defines managed targets as `managed+csv:///absolute/path/to/logical-name`. The logical path is a namespace, not a mutable CSV file.
- Uses layout `<logical-name>.otc/snapshots/<content-hash>.csv`, `stages/<stage-id>.arrow`, `receipts/<operation-id>.json`, and atomic `current.json`.
- Adds `open-table-connector-timeseries==0.1.0` as a workspace dependency of `open-table-connector-local-files`.

- [ ] **Step 1: Write failing lifecycle and recovery tests**

Test stage invisibility, immutable content-addressed CSV snapshots, idempotent commit, conflicting reuse, independent readback, abort dispositions, atomic pointer replacement, stale temporary-file cleanup, crash before pointer replacement, crash after pointer replacement, concurrent commit serialization, and rejection of traversal/symlink targets.

- [ ] **Step 2: Write portable execution tests**

Read the committed snapshot through `PolarsTemporalExecutor` and assert range/latest/as-of/bucket/gap-fill parity with Task 3–4 fixtures. Advertise unqualified semantic capabilities but no pushdown capabilities.

- [ ] **Step 3: Run tests and verify red**

~~~bash
uv run --frozen python -m pytest packages/local_files/tests/test_temporal_csv.py packages/local_files/tests/test_managed_csv.py packages/local_files/tests/test_managed_snapshot_recovery.py -q
~~~

Expected: missing module failures.

- [ ] **Step 4: Implement the snapshot primitive**

Lock `<logical-name>.otc/commit.lock` with an OS file lock. Stage validates and hashes the Arrow artifact but writes no pointer. Commit converts the staged Arrow table to a deterministic CSV snapshot, fsyncs file and directory, writes a closed pointer document to a temporary sibling, fsyncs it, and replaces `current.json`. Reconciliation reads the pointer and receipt by idempotency key; it never guesses from a convenience copy.

Readback reopens the snapshot path named by `current.json` and recomputes Arrow schema/content/range/row/byte facts. Atomic visibility is claimed only for readers using this managed layout.

- [ ] **Step 5: Run tests and commit**

~~~bash
uv lock
uv run --frozen python -m pytest packages/local_files/tests -q
git diff --check
git add packages/local_files pyproject.toml uv.lock
git commit -m "feat: add managed CSV temporal storage"
~~~

### Task 7: Add JSON and JSONL temporal storage on normal URI schemes

**Files:**
- Create: `packages/local_files/src/open_table_connector/local_files/json_codec.py`
- Create: `packages/local_files/src/open_table_connector/local_files/json_connector.py`
- Create: `packages/local_files/src/open_table_connector/local_files/temporal_json.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/probe.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/resolver.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/local_files_connector.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/__init__.py`
- Modify: `packages/cli/src/open_table_connector/cli/formats.py`
- Modify: `packages/cli/tests/test_formats.py`
- Create: `packages/local_files/tests/test_json_codec.py`
- Create: `packages/local_files/tests/test_json_connector.py`
- Create: `packages/local_files/tests/test_temporal_json.py`
- Create: `packages/local_files/tests/test_managed_json.py`

**Interfaces:**
- Produces `parse_json_table(text: str, *, source: str) -> pa.Table`, `parse_jsonl_table(text: str, *, source: str) -> pa.Table`, `encode_json_table(table: pa.Table) -> str`, and `encode_jsonl_table(table: pa.Table) -> str`.
- Produces `JsonConnector` and `JsonTableReadRequest` for `json://` and `jsonl://` in `TableMode.BASE`; `.ndjson` is accepted by the JSONL format. The v1 codec is always strict UTF-8 and has no permissive parse options.
- Produces `JsonTemporalExecutor` and `JsonManagedTemporalStore(format: Literal["json", "jsonl"])`.
- Uses target schemes `json:///absolute/path/data.json` and `jsonl:///absolute/path/data.jsonl` for both direct and managed operations. Lifecycle mode is not encoded in the URI.
- Uses `TemporalExecutionRequest.snapshot_reference` to distinguish a direct file execution from execution against an immutable committed snapshot.

- [ ] **Step 1: Write failing strict codec and connector tests**

Require JSON to contain one top-level array of objects and JSONL to contain one object per non-empty line. Assert first-seen column ordering, null filling for missing keys, UTF-8, nested struct/list preservation where Arrow can represent it, final newline for JSONL, compact deterministic output, and round-trip parity.

~~~python
from pathlib import Path

from open_table_connector.contract import TableURI
from open_table_connector.local_files import JsonConnector, JsonTableReadRequest


def json_uri(scheme: str, path: Path) -> TableURI:
    return TableURI(path.as_uri().replace("file://", f"{scheme}://", 1))


def test_json_and_jsonl_use_normal_connector_schemes(tmp_path: Path) -> None:
    json_path = tmp_path / "ticks.json"
    json_path.write_text(
        '[{"ts":"2026-08-29T00:00:00Z","symbol":"A","price":1}]',
        encoding="utf-8",
    )
    jsonl_path = tmp_path / "ticks.jsonl"
    jsonl_path.write_text(
        '{"ts":"2026-08-29T00:00:00Z","symbol":"A","price":1}\n',
        encoding="utf-8",
    )
    connector = JsonConnector()
    json_result = connector.read_arrow(
        JsonTableReadRequest(json_uri("json", json_path))
    )
    jsonl_result = connector.read_arrow(
        JsonTableReadRequest(json_uri("jsonl", jsonl_path))
    )
    assert json_result.table.num_rows == 1
    assert jsonl_result.table.num_rows == 1
~~~

Add explicit failures for a top-level scalar/object, a non-object row, duplicate keys at any object depth, `NaN`/`Infinity`, malformed/trailing JSON, a malformed late JSONL line, invalid UTF-8, and row/byte/time bounds. Safe errors expose line/column or row index but no record payload.

- [ ] **Step 2: Run codec and connector tests to verify red**

~~~bash
uv run --frozen python -m pytest packages/local_files/tests/test_json_codec.py packages/local_files/tests/test_json_connector.py packages/cli/tests/test_formats.py -q
~~~

Expected: imports fail because the shared local-files codec and connector do not exist.

- [ ] **Step 3: Promote the CLI codecs into the local-files package**

Implement duplicate-key rejection with `json.loads(..., object_pairs_hook=reject_duplicate_keys, parse_constant=reject_non_finite)`. JSONL applies the same decoder independently to every non-empty line. Compute the first-seen union of object keys, normalize every row to that ordered key set, then convert with `pa.Table.from_pylist`. Reject incompatible nested shapes with stable `execution_failed` details.

`JsonConnector.resolve` accepts only `json` or `jsonl`, requires a regular file for ordinary reads, verifies content rather than suffix alone, and enforces input byte limits before decoding. Extend `LocalFormat` and `LocalFilesConnector` detection/dispatch for `.json`, `.jsonl`, and `.ndjson`. Replace the CLI's private JSON functions with imports from `json_codec.py` so both surfaces share exact behavior.

- [ ] **Step 4: Write failing temporal and managed lifecycle tests**

Run every Task 3–4 semantic fixture through both formats. Require time, series-key, and tag fields to be scalar and aggregate inputs to be function-compatible. Test direct execution with `snapshot_reference=None`, exact committed-snapshot execution with a reference, mismatched target/reference rejection, stage invisibility, deterministic immutable snapshots, idempotent commit, independent readback, abort, pointer recovery, concurrent commit serialization, and traversal/symlink rejection.

- [ ] **Step 5: Run temporal tests to verify red**

~~~bash
uv run --frozen python -m pytest packages/local_files/tests/test_temporal_json.py packages/local_files/tests/test_managed_json.py -q
~~~

Expected: temporal executor/store imports fail.

- [ ] **Step 6: Implement temporal execution and managed snapshots**

`JsonTemporalExecutor` resolves the direct path when no snapshot reference is supplied. With a snapshot reference, it asks `ManagedSnapshotStore` to resolve the immutable snapshot bound to the same target and rejects an unknown or cross-target reference before decoding.

`JsonManagedTemporalStore` reuses the Task 6 locking, staging, receipt, fsync, and atomic-pointer primitive. It writes `<target>.otc/snapshots/<content-hash>.json` or `.jsonl`. JSON output is one compact top-level array; JSONL is one compact object per line with a final newline. Top-level row keys follow Arrow schema order, nested object keys are sorted recursively, non-finite values are rejected, and observed Arrow facts are recomputed from a newly decoded snapshot during readback.

- [ ] **Step 7: Run tests and commit**

~~~bash
uv run --frozen python -m pytest packages/local_files/tests packages/cli/tests/test_formats.py -q
git diff --check
git add packages/local_files packages/cli/src/open_table_connector/cli/formats.py packages/cli/tests/test_formats.py
git commit -m "feat: add JSON and JSONL temporal storage"
~~~

### Task 8: Add SQLite temporal lowering and lifecycle storage

**Files:**
- Create: `packages/timeseries/src/open_table_connector/timeseries/lowering.py`
- Modify: `packages/sqlite/pyproject.toml`
- Modify: `packages/sqlite/src/open_table_connector/sqlite/reader.py`
- Create: `packages/sqlite/src/open_table_connector/sqlite/temporal.py`
- Modify: `packages/sqlite/src/open_table_connector/sqlite/__init__.py`
- Create: `packages/sqlite/tests/test_temporal_lowering.py`
- Create: `packages/sqlite/tests/test_temporal_storage.py`
- Create: `packages/sqlite/tests/test_transaction_isolation.py`

**Interfaces:**
- Produces shared immutable `PreparedTemporalQuery(statement: str, parameters: tuple[object, ...], residual_plan: PortableTemporalPlan | None)` in `lowering.py`.
- Produces `lower_sqlite(plan, descriptor, physical_table) -> PreparedTemporalQuery`.
- Produces `SQLiteTemporalExecutor` and `SQLiteManagedTemporalStore`.
- Uses adapter-owned tables `_otc_ts_stages`, `_otc_ts_commits`, `_otc_ts_snapshots`, and `_otc_ts_receipts`.
- Adds `open-table-connector-timeseries==0.1.0` as a workspace dependency of `open-table-connector-sqlite`.

- [ ] **Step 1: Write lowering and injection tests**

Assert quoted authorized identifiers, positional parameters for every runtime value, half-open predicates, deterministic order, and no interpolation of relation/tag/value text into SQL. Test range/latest/as-of and supported fixed-bucket aggregates. Calendar buckets, gap fill, and any semantically mismatched operation must return a bounded source scan for connector-side evaluation rather than claim pushdown.

- [ ] **Step 2: Write lifecycle and per-operation transaction tests**

Use a temporary SQLite database. Test invisible stage rows, `BEGIN IMMEDIATE` publication, idempotent commit/reconciliation, readback in a fresh connection, abort, rollback after injected failure, two connector instances, and two concurrent operations. Assert no `_transaction_connection` remains on the connector.

- [ ] **Step 3: Run tests and verify red**

~~~bash
uv run --frozen python -m pytest packages/sqlite/tests/test_temporal_lowering.py packages/sqlite/tests/test_temporal_storage.py packages/sqlite/tests/test_transaction_isolation.py -q
~~~

Expected: missing temporal module and global-transaction assertions fail.

- [ ] **Step 4: Refactor connection ownership and implement temporal storage**

Replace connector-global transaction state with a private context manager that opens one connection for one read/write/execute/managed operation, commits only that operation, rolls back on error, and always closes. Preserve existing `TransactionalStore` methods through an explicit transaction handle object instead of mutable connector state.

Store stage payloads as Arrow IPC blobs with content hashes. Publish by inserting a new immutable snapshot record and atomically updating the logical-target commit row in one transaction. Readback starts a separate read transaction and reconstructs Arrow values from the committed snapshot.

- [ ] **Step 5: Run tests and commit**

~~~bash
uv lock
uv run --frozen python -m pytest packages/sqlite/tests -q
git diff --check
git add packages/sqlite pyproject.toml uv.lock
git commit -m "feat: add SQLite temporal storage"
~~~

### Task 9: Add PostgreSQL temporal lowering and lifecycle storage

**Files:**
- Modify: `packages/postgres/pyproject.toml`
- Modify: `packages/postgres/src/open_table_connector/postgres/reader.py`
- Create: `packages/postgres/src/open_table_connector/postgres/temporal.py`
- Modify: `packages/postgres/src/open_table_connector/postgres/__init__.py`
- Create: `packages/postgres/tests/test_temporal_lowering.py`
- Create: `packages/postgres/tests/test_temporal_storage_recording.py`
- Create: `packages/postgres/tests/test_transaction_isolation.py`
- Create: `packages/postgres/tests/test_temporal_storage_live.py`

**Interfaces:**
- Produces `lower_postgres(plan, descriptor, physical_table) -> PreparedTemporalQuery`.
- Produces `PostgresTemporalExecutor` and `PostgresManagedTemporalStore`.
- Uses schema `_otc_ts` with `stages`, `commits`, `snapshots`, and `receipts` tables.
- Live tests require `OTC_TEST_POSTGRES_DSN` and are skipped when it is absent.
- Adds `open-table-connector-timeseries==0.1.0` as a workspace dependency and a `live` optional dependency group containing `psycopg2-binary>=2.9,<3`.

- [ ] **Step 1: Write prepared lowering and capability tests**

Cover every portable operation. PostgreSQL may push down range/latest/as-of, fixed/calendar buckets, and matching aggregates. Plain PostgreSQL must not advertise Timescale gap-fill or any `timescale.*` identity. Gap fill/LOCF/interpolation execute connector-side after a bounded prepared scan.

Assert all values are `%s` parameters, all identifiers come from an authorized mapping and are double-quoted, and neither logical relation names nor user predicates become raw SQL.

- [ ] **Step 2: Write recording lifecycle and transaction tests**

Extend the existing recording DB-API fixture with transaction, isolation, server-side cursor, and close state. Test `INSERT ... ON CONFLICT` idempotency, advisory lock by logical target, unknown commit reconciliation by idempotency key, statement timeout, cancellation, rollback, independent readback connection, and secret-safe errors. Assert no connector-global connection exists.

- [ ] **Step 3: Run tests and verify red**

~~~bash
uv run --frozen python -m pytest packages/postgres/tests/test_temporal_lowering.py packages/postgres/tests/test_temporal_storage_recording.py packages/postgres/tests/test_transaction_isolation.py -q
~~~

Expected: missing module and transaction ownership failures.

- [ ] **Step 4: Implement per-operation connections and managed schema**

Create one connection per operation and set `SET LOCAL statement_timeout` from request bounds inside the transaction. Use a server-side cursor or bounded `fetchmany` for scans. Stage payloads in `_otc_ts.stages`, publish a snapshot and logical-target pointer in one transaction, and read back through a new repeatable-read transaction. On an ambiguous commit response, reconnect and query the idempotency record; do not rerun the write blindly.

- [ ] **Step 5: Add opt-in live evidence**

The live test creates a unique schema, runs stage/commit/readback/abort and all pushed operations, verifies a concurrent reader never sees a partial snapshot, and drops only that unique schema in `finally`. It prints no DSN. A passing recording test is not stable live evidence.

- [ ] **Step 6: Run tests and commit**

~~~bash
uv lock
uv run --frozen python -m pytest packages/postgres/tests -q
OTC_TEST_POSTGRES_DSN="$OTC_TEST_POSTGRES_DSN" uv run --frozen python -m pytest packages/postgres/tests/test_temporal_storage_live.py -q
git diff --check
git add packages/postgres pyproject.toml uv.lock
git commit -m "feat: add PostgreSQL temporal storage"
~~~

Expected: offline tests pass. The live test either passes with a configured DSN or reports one explicit skip without one.

### Task 10: Add formula-safe Excel temporal storage

**Files:**
- Create: `packages/local_files/src/open_table_connector/local_files/temporal_excel.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/__init__.py`
- Create: `packages/local_files/tests/test_temporal_excel.py`
- Create: `packages/local_files/tests/test_managed_excel.py`
- Create: `packages/local_files/tests/excel_fixtures.py`

**Interfaces:**
- Produces `ExcelTemporalExecutor` and `ExcelManagedTemporalStore`.
- Defines managed targets as `managed+xlsx:///absolute/path/to/logical-name#sheet=<encoded-name>`.
- Reuses `ManagedSnapshotStore` with immutable `.xlsx` snapshots.
- Reuses the time-series workspace dependency added to `open-table-connector-local-files` in Task 6.

- [ ] **Step 1: Write read, lifecycle, and formula rejection tests**

Have `excel_fixtures.py` create value-only and formula-bearing workbooks under pytest `tmp_path` with openpyxl. Verify descriptor binding to one governed worksheet table, all portable operations through Polars/Arrow, immutable workbook snapshots, atomic pointer publication, independent readback, preserved values/types, and rejection when any governed cell contains a formula. Assert no formula calculation or formula-evidence capability is advertised.

- [ ] **Step 2: Run tests and verify red**

~~~bash
uv run --frozen python -m pytest packages/local_files/tests/test_temporal_excel.py packages/local_files/tests/test_managed_excel.py -q
~~~

Expected: missing module failures.

- [ ] **Step 3: Implement formula-safe publication**

Load workbooks with `data_only=False` for formula detection. Reject a governed range containing a cell whose data type is `f` before staging succeeds. Write a new workbook snapshot from validated Arrow values; never copy cached formula results as evidence. Use the same fsync/replace pointer protocol as CSV and record the worksheet name in the snapshot receipt.

- [ ] **Step 4: Run tests and commit**

~~~bash
uv run --frozen python -m pytest packages/local_files/tests -q
git diff --check
git add packages/local_files
git commit -m "feat: add Excel temporal storage"
~~~

### Task 11: Add capability-gated MaybeSheet temporal support

**Files:**
- Modify: `packages/maybe_sheet/pyproject.toml`
- Create: `packages/maybe_sheet/src/open_table_connector/maybe_sheet/temporal.py`
- Modify: `packages/maybe_sheet/src/open_table_connector/maybe_sheet/__init__.py`
- Create: `packages/maybe_sheet/tests/fixtures/temporal-describe.json`
- Create: `packages/maybe_sheet/tests/fixtures/temporal-read.jsonl`
- Create: `packages/maybe_sheet/tests/test_temporal_recording.py`
- Create: `packages/maybe_sheet/tests/test_temporal_capabilities.py`
- Create: `packages/maybe_sheet/tests/test_temporal_live.py`

**Interfaces:**
- Produces `MaybeSheetTemporalExecutor` and `probe_temporal_capabilities(client) -> frozenset[str]`.
- Produces `MaybeSheetManagedTemporalStore` only when the installed `mbs` reports all required lifecycle commands and receipt versions.
- Live tests require `OTC_TEST_MBS_URI` and `OTC_TEST_MBS_ENABLED=1`.
- Adds `open-table-connector-timeseries==0.1.0` as a workspace dependency of `open-table-connector-maybe-sheet`.

- [ ] **Step 1: Write recording protocol and capability tests**

Use the injected process client. Assert descriptor/read calls send credential-free argv plus JSONL stdin, enforce time/row/byte limits, return Arrow to the connector-side evaluator, and mark execution location `connector`. A recording response without explicit `stage`, `commit`, `snapshot-read`, `readback`, `abort`, and atomic visibility evidence must advertise none of those capabilities.

- [ ] **Step 2: Write conditional managed-store tests**

Provide a recording `mbs` description with exact command/receipt versions and test the full lifecycle. Remove each required command in turn and assert construction fails before target I/O with `unsupported_capability`.

- [ ] **Step 3: Run tests and verify red**

~~~bash
uv run --frozen python -m pytest packages/maybe_sheet/tests/test_temporal_recording.py packages/maybe_sheet/tests/test_temporal_capabilities.py -q
~~~

Expected: missing temporal module failures.

- [ ] **Step 4: Implement truthful probing and portable execution**

Probe once per process identity/version and cache only immutable capability facts. Execute all v1 temporal semantics in `PolarsTemporalExecutor` after a bounded `mbs` read unless an exact tested pushdown capability exists. Map provider receipts into neutral fields without copying provider payloads or claiming independent readback from submitted data.

- [ ] **Step 5: Add opt-in live test and commit**

The live test uses the configured URI, runs only capabilities reported by the real binary, and stores its safe capability/evidence hash as test output. It must skip rather than infer support when configuration or commands are absent.

~~~bash
uv lock
uv run --frozen python -m pytest packages/maybe_sheet/tests -q
git diff --check
git add packages/maybe_sheet pyproject.toml uv.lock
git commit -m "feat: add MaybeSheet temporal capabilities"
~~~

### Task 12: Add cross-provider conformance, process integration, and the compatibility attestation

**Files:**
- Modify: `packages/conformance/pyproject.toml`
- Create: `packages/conformance/src/open_table_connector/conformance/timeseries.py`
- Create: `specification/conformance/timeseries/conftest.py`
- Create: `specification/conformance/timeseries/test_semantic_matrix.py`
- Create: `specification/conformance/timeseries/test_lifecycle_matrix.py`
- Create: `specification/conformance/timeseries/test_process_e2e.py`
- Create: `specification/conformance/timeseries/test_schema_parity.py`
- Create: `specification/conformance/timeseries/README.md`
- Create: `specification/compatibility/ots-otc-timeseries-v1.yaml`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-08-29-portable-time-series-storage-design.md`

**Interfaces:**
- Produces `assert_temporal_semantics(executor, case)` and `assert_managed_lifecycle(store, case)`.
- Produces a compatibility record containing architecture ID, OTC/OTS surface commits, process protocol, plan schema, receipt schemas, fixture manifest hash, Python/Rust/Arrow ranges, provider oracle versions, and per-provider evidence status.

- [ ] **Step 1: Write the failing capability-driven matrix**

Parametrize ScanRange, Latest, AsOf, BucketAggregate, and GapFill over Polars, CSV, JSON, JSONL, SQLite, PostgreSQL recording, Excel, and MaybeSheet recording executors. Compare normalized Arrow schemas and logical values, not serialized IPC bytes. Parametrize lifecycle assertions only over stores that advertise each lifecycle capability.

Include DST, origin/offset, nanoseconds, empty buckets, nulls, duplicates, out-of-order rows, LOCF/interpolation edges, strict JSON structure, JSONL late-record failures, nested values, formula rejection, bounds failures, idempotency conflicts, unknown commit reconciliation, and abort.

- [ ] **Step 2: Add OTS-shaped process end-to-end tests**

Spawn `otc-process` with a temporary artifact root. Send the same `hello` and `execute` frames the Rust binding will send, verify returned Arrow and receipt documents, then run stage/commit/readback/abort. Add mismatched process/plan/capability version tests, cancellation, credential reference isolation, and artifact tamper tests.

- [ ] **Step 3: Run the new suites and verify red**

~~~bash
uv run --frozen python -m pytest specification/conformance/timeseries -q
~~~

Expected: matrix failures identify any missing registration, capability, or schema parity.

- [ ] **Step 4: Complete registry wiring and support labels**

Register CSV, JSON, JSONL, Excel, SQLite, PostgreSQL, and MaybeSheet providers explicitly in the process package. Add the two new distributions to discovery/build documentation. Generate the fixture manifest hash from the checked-in bytes. The compatibility record is created only after the OTS plan has vendored and passed the same fixtures.

Use these support labels:

- CSV and Excel: `portable-storage` only when managed lifecycle tests pass.
- JSON and JSONL: `portable-storage` only when strict format, snapshot-reference, and managed lifecycle tests pass.
- SQLite: `portable-storage` and `ots-eligible` when the configured OTS requirements fit its evidence.
- PostgreSQL: `portable-storage` offline; `ots-eligible` only with configured-live evidence.
- MaybeSheet: `import-export` by default; stronger labels only from probed live commands and receipts.

- [ ] **Step 5: Run full verification**

~~~bash
uv lock --check
uv run --frozen python -m pytest packages/timeseries/tests packages/process/tests specification/conformance/timeseries -q
uv run --frozen python -m pytest -q
uv build --all-packages
python -m compileall -q packages specification/conformance
git diff --check
~~~

Expected: all tests pass, every workspace distribution builds, compilation succeeds, and no whitespace errors remain.

- [ ] **Step 6: Scan for forbidden scope and unsafe placeholders**

~~~bash
rg -n "time_bucket_gapfill|continuous.aggregate|retention|columnstore|tiering|hyperfunction|FlightSql" packages/timeseries packages/process
rg -n "password|access_token|api_key|secret" specification/fixtures/timeseries packages/process/tests
rg -n "T[B]D|T[O]DO|FIX[M]E|pass$|NotImplemented" packages/timeseries packages/process specification/conformance/timeseries
~~~

Expected: the first command finds only the portable gap-fill enum/tests and documented rejections; the second finds only redaction test literals; the third returns no unfinished implementation.

- [ ] **Step 7: Commit the OTC compatibility surface**

~~~bash
git add packages/conformance specification/conformance/timeseries README.md docs/superpowers/specs/2026-08-29-portable-time-series-storage-design.md
git commit -m "test: certify portable temporal storage"
~~~

Record this commit as `otc_surface_commit`. It is the OTC side of the compatible pair and intentionally precedes the attestation file.

- [ ] **Step 8: Add the shared compatibility attestation after the OTS surface commit exists**

After OTS Task 10 commits its non-attestation API/docs surface, create `specification/compatibility/ots-otc-timeseries-v1.yaml`. Pin `otc_surface_commit` from Step 7 and that OTS `ots_surface_commit`. Include architecture ID, process/plan/receipt versions, fixture manifest hash, Python/Rust/Arrow ranges, TimescaleDB/PostgreSQL oracle versions, and each provider's evidence status.

The OTS repository must contain byte-for-byte the same YAML. The two later attestation commits are not the values being pinned, which avoids a circular commit dependency.

~~~bash
uv run --frozen python - <<'PY'
from pathlib import Path
import yaml

path = Path("specification/compatibility/ots-otc-timeseries-v1.yaml")
record = yaml.safe_load(path.read_text(encoding="utf-8"))
assert record["architecture"] == "ots-otc-timeseries-storage/v1"
assert len(record["otc_surface_commit"]) == 40
assert len(record["ots_surface_commit"]) == 40
assert len(record["fixture_manifest_sha256"]) == 64
PY
git diff --check
git add specification/compatibility/ots-otc-timeseries-v1.yaml
git commit -m "docs: attest OTS OTC compatibility"
~~~

## Phase 1–5 Exit Criteria

- The existing contract and all current connector tests remain green.
- Python models and JSON schemas reject unknown fields and round-trip all checked-in v1 fixtures.
- The OTS repository vendors the exact fixture bytes and verifies `manifest.sha256`.
- Polars/Arrow passes the complete portable semantic corpus with mandatory bounds.
- `otc.connector-process/v1` proves version pinning, cancellation, secret isolation, bounded diagnostics, and Arrow artifact integrity.
- CSV, JSON, JSONL, and SQLite pass offline managed lifecycle conformance.
- JSON and JSONL use `json://` and `jsonl://` for both direct and managed operations, with committed snapshot selection outside the portable plan.
- PostgreSQL passes offline conformance and has an opt-in live evidence test; stable live claims are gated on its result.
- Excel rejects formula-bearing governed ranges and claims no formula calculation/evidence.
- MaybeSheet advertises only capabilities proven by its actual process description and receipts.
- The byte-identical compatibility record in both repositories names exact pre-attestation surface commits, evidence hashes, and every schema/protocol version without a circular commit dependency.
- TimescaleDB, ClickHouse, TDengine, and Flight are absent from OTC production dependencies.
