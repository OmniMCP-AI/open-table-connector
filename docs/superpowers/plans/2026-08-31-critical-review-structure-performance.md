# Critical Review Structure and Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the highest-cost duplication and avoidable materialization identified as T2 and F1–F4 while preserving the corrected semantics, receipts, and provider boundaries established by the other remediation plans.

**Architecture:** The timeseries package owns two deep modules: one precision-safe Arrow artifact reader and one managed-SQL lifecycle core parameterized by a deliberately small SQLite/PostgreSQL dialect. Temporal sources return data plus projection-independent snapshot evidence. Evaluation serializes each Arrow result once, vectorizes fixed buckets, and computes calendar labels only for unique timestamps. Streaming is introduced only through a versioned bounded-read capability so a partial CLI result can never masquerade as a complete v1 read.

**Tech Stack:** Python 3.11–3.14, PyArrow 14–19, Polars 1.x, SQLite, PostgreSQL 17, psycopg2, urllib, pytest 9, `perf_counter_ns`, `tracemalloc`, and uv workspace commands.

**Spec:** `docs/superpowers/specs/2026-08-31-critical-review-remediation-design.md`

**Owned findings:** T2, F1, F2, F3, and F4. Performance dispositions stay hypotheses until Task 7 has compatible before/after evidence.

**Prerequisites:** Complete the correctness/data-safety plan and Tasks 1–4 of the specification/conformance plan before changing shared storage or evaluator code. Complete packaging/CI/CLI Tasks 4–6 before adding the bounded CLI path. Run Task 1 first and retain its baseline results; do not refactor from unmeasured assumptions.

## Global Constraints

- Preserve all corrected behavior with characterization tests before moving code.
- The shared managed-SQL core owns lifecycle state transitions, artifact verification, receipt construction, retry reconciliation, and bound checks. Dialects own only SQL syntax, placeholder binding, locking, and transaction setup.
- Provider packages keep their public `SQLiteManagedTemporalStore` and `PostgresManagedTemporalStore` facades.
- `source_revision` identifies the physical source snapshot and never changes solely because projection changes.
- A v1 complete-read receipt is never emitted for a truncated stream. Bounded reads use the new `table.read.arrow.bounded/2.0` capability and receipt schema.
- The CLI uses bounded reads only when the selected connector advertises that capability; otherwise it performs the complete v1 read and applies `--limit` as presentation.
- Feishu `batch_create` uses the official limit of 500 records per request, sourced from the [Feishu Create records API](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/batch_create). Keep the limit as a named provider constant and cover boundary sizes 0, 1, 500, 501, and 1001.
- Benchmark claims remain `hypothesis` until a checked-in before/after artifact records command, commit, runtime versions, OS/CPU, data shape, repetitions, and raw samples.
- Work red-green-refactor. Each task ends with focused tests, owning package tests, `git diff --check`, a ledger update, and one Conventional Commit.

---

## File Map

- `benchmarks/temporal_evaluator.py` — deterministic fixed/calendar evaluator workload.
- `benchmarks/managed_storage.py` — deterministic local and SQL lifecycle workload.
- `benchmarks/cli_streaming.py` — peak-memory and time workload for bounded local reads.
- `benchmarks/run.py` — metadata-rich benchmark runner and JSON artifact writer.
- `benchmarks/results/README.md` — artifact schema and comparison policy.
- `packages/timeseries/src/open_table_connector/timeseries/artifacts.py` — one bounded, precision-safe Arrow artifact reader.
- `packages/timeseries/src/open_table_connector/timeseries/managed_sql.py` — lifecycle core plus narrow dialect protocol.
- `packages/timeseries/src/open_table_connector/timeseries/evaluator.py` — source evidence, vectorized buckets, and one serialization boundary.
- `packages/contract/src/open_table_connector/contract/bounded_reads.py` — explicit partial-read request/result/receipt types with no nested complete-v1 receipt.
- `packages/local_files/src/open_table_connector/local_files/bounded_reader.py` — streaming CSV/JSONL implementation of bounded read v2.
- `packages/cli/src/open_table_connector/cli/pipeline.py` — capability-selected bounded CLI path.
- `packages/feishu_bitable/src/open_table_connector/feishu_bitable/connector.py` — provider-sourced batching and typed bounded transport errors.

### Task 1: Establish characterization coverage and reproducible baselines

**Files:**
- Create: `benchmarks/__init__.py`
- Create: `benchmarks/datasets.py`
- Create: `benchmarks/run.py`
- Create: `benchmarks/temporal_evaluator.py`
- Create: `benchmarks/managed_storage.py`
- Create: `benchmarks/cli_streaming.py`
- Create: `benchmarks/results/README.md`
- Create: `packages/timeseries/tests/test_performance_characterization.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `docs/reviews/2026-08-31-critical-review-remediation.md`

**Interfaces:**
- Produces: `BenchmarkSample`, `BenchmarkEnvironment`, and `write_result(path: Path, result: BenchmarkResult) -> None`; deterministic `temporal_table(rows: int, unique_timestamps: int) -> pa.Table`.
- Consumes: fixed seeds and workload sizes `10_000`, `100_000`, and `1_000_000`; the review identifiers `T2` and `F1`–`F4`.

- [ ] **Step 1: Write the benchmark artifact contract test**

```python
def test_benchmark_result_records_reproducible_environment(tmp_path: Path) -> None:
    result = run_benchmark("temporal-fixed", repetitions=3, rows=10_000)
    path = tmp_path / "result.json"
    write_result(path, result)
    document = json.loads(path.read_text())
    assert document["schema_version"] == "1.0"
    assert document["commit"]
    assert document["environment"]["python"]
    assert document["environment"]["pyarrow"]
    assert document["environment"]["polars"]
    assert len(document["samples_ns"]) == 3
```

Add characterization assertions that current fixed/calendar outputs, managed
receipts, and CLI output are identical across repeated execution. These are
semantic tests, not time thresholds.

- [ ] **Step 2: Run the new tests and confirm missing benchmark support**

```bash
uv run --frozen python -m pytest packages/timeseries/tests/test_performance_characterization.py -q
```

- [ ] **Step 3: Implement the runner without pass/fail speed assertions**

Use `time.perf_counter_ns()` for raw samples and `tracemalloc` for Python peak
allocation. Record Git commit and dirty state, platform, CPU, Python,
PyArrow, Polars, SQLite, psycopg2, workload parameters, warmups, repetitions,
median, minimum, and every raw sample. Exit non-zero if metadata is missing.

- [ ] **Step 4: Capture the pre-refactor baseline**

```bash
uv run --frozen python -m benchmarks.run --suite all --phase before --repetitions 7
```

Write generated JSON under `benchmarks/results/` with the current pre-refactor
commit and date in its name. Do not state an improvement yet; mark F1–F4 as `hypothesis`
with a link to this baseline in the ledger.

- [ ] **Step 5: Run characterization suites and commit**

```bash
uv run --frozen python -m pytest packages/timeseries/tests/test_performance_characterization.py packages/timeseries/tests packages/sqlite/tests packages/postgres/tests packages/local_files/tests packages/cli/tests -q
git diff --check
git add benchmarks/__init__.py benchmarks/datasets.py benchmarks/run.py benchmarks/temporal_evaluator.py benchmarks/managed_storage.py benchmarks/cli_streaming.py benchmarks/results/README.md benchmarks/results/*-before-*.json pyproject.toml uv.lock packages/timeseries/tests/test_performance_characterization.py docs/reviews/2026-08-31-critical-review-remediation.md
git commit -m "test: establish remediation performance baselines"
```

### Task 2: Centralize artifact verification and managed-SQL lifecycle logic

**Files:**
- Create: `packages/timeseries/src/open_table_connector/timeseries/artifacts.py`
- Create: `packages/timeseries/src/open_table_connector/timeseries/managed_sql.py`
- Modify: `packages/timeseries/src/open_table_connector/timeseries/__init__.py`
- Create: `packages/timeseries/tests/test_artifacts.py`
- Create: `packages/timeseries/tests/test_managed_sql.py`
- Modify: `packages/sqlite/src/open_table_connector/sqlite/temporal.py:259-671`
- Modify: `packages/postgres/src/open_table_connector/postgres/temporal.py:299-802`
- Modify: `packages/local_files/src/open_table_connector/local_files/managed_snapshots.py:478-534`
- Modify: `packages/process/src/open_table_connector/process/artifacts.py:75-156`
- Modify: `packages/maybe_sheet/src/open_table_connector/maybe_sheet/temporal.py:439-470`
- Modify: `packages/sqlite/tests/test_temporal_storage.py`
- Modify: `packages/postgres/tests/test_temporal_storage_recording.py`
- Modify: `packages/postgres/tests/test_temporal_storage_live.py`
- Modify: `packages/process/tests/test_artifacts.py`
- Modify: `packages/maybe_sheet/tests/test_temporal_capabilities.py`

**Interfaces:**
- Produces: `VerifiedArtifact(data: bytes, table: pa.Table, observed_range: TimeRange | None)`; `read_verified_artifact(reference: ArrowArtifactReference, artifact_root: Path, bounds: ResourceBounds, descriptor: TemporalTableDescriptor | None = None) -> VerifiedArtifact`; `ManagedSqlDialect`, `ManagedSqlStatements`, and `ManagedSqlLifecycleCore`.
- Consumes: `arrow_time_bounds()` from the correctness plan, existing stage/commit/readback/abort request and receipt types, injected `now`, and injected fault callbacks.

- [ ] **Step 1: Write artifact traversal, hash, size, and precision tests**

```python
def test_verified_artifact_rejects_hash_mismatch(tmp_path: Path) -> None:
    reference = write_reference(tmp_path, table=sample_table(), declared_hash="0" * 64)
    with pytest.raises(TemporalExtensionError) as raised:
        read_verified_artifact(reference, tmp_path, BOUNDS, DESCRIPTOR)
    assert raised.value.code is TemporalErrorCode.SNAPSHOT_UNAVAILABLE

@pytest.mark.parametrize("store_factory", [sqlite_store, postgres_recording_store])
def test_managed_sql_characterization_is_dialect_independent(store_factory) -> None:
    assert lifecycle_documents(store_factory()) == EXPECTED_LIFECYCLE_DOCUMENTS
```

Cover root confinement, symlink rejection, short/oversized files, canonical
hash validation, Arrow decoding, row/byte bounds, and all timestamp
precisions. Feed the same lifecycle transcript to both dialect facades.

- [ ] **Step 2: Run focused tests and capture the red phase**

```bash
uv run --frozen python -m pytest packages/timeseries/tests/test_artifacts.py packages/timeseries/tests/test_managed_sql.py -q
```

- [ ] **Step 3: Implement the deep artifact reader**

Read with `os.open(..., O_NOFOLLOW)` where available, validate the resolved
path remains under the injected artifact root, enforce `max_bytes` while
reading, validate SHA-256 before Arrow decoding, enforce `max_rows`, and
derive `observed_range` with `arrow_time_bounds` when a descriptor is supplied.
Replace the SQL, local snapshot, MaybeSheet, and process artifact-read paths
with this function; provider facades only translate existing requests into
its arguments. Keep process artifact creation/expiry in `ArtifactStore`.

- [ ] **Step 4: Define the narrow dialect seam**

```python
class ManagedSqlDialect(Protocol):
    def placeholder(self, position: int) -> str: ...
    def quote(self, identifier: str) -> str: ...
    def begin(self, connection: object, *, write: bool) -> None: ...
    def lock_target(self, cursor: object, target: TableURI) -> None: ...
    def ensure_schema(self, cursor: object, names: ManagedTableNames) -> None: ...
    def statements(self, names: ManagedTableNames) -> ManagedSqlStatements: ...
    def json_parameter(self, document: Mapping[str, object]) -> object: ...

class ManagedSqlLifecycleCore:
    def stage(self, request: ManagedStageRequest) -> ManagedStageReceipt: ...
    def commit(self, request: ManagedCommitRequest) -> ManagedCommitReceipt: ...
    def readback(self, request: ManagedReadbackRequest) -> ManagedReadbackResult: ...
    def abort(self, request: ManagedAbortRequest) -> ManagedAbortReceipt: ...
```

`ManagedSqlStatements` names the select/insert/update statements for stage,
commit, current-pointer upsert, abort, and receipt append; it contains no
policy callbacks. The core owns retry lookup, state transitions,
deadline/row/byte checks, receipt documents, and fault-injection events.
`SQLiteManagedDialect` and `PostgresManagedDialect` implement only the seven
methods above, including their placeholder/upsert/locking differences. Keep
provider-specific connection ownership and public store constructors in the
provider packages.

- [ ] **Step 5: Move one lifecycle operation at a time**

Move `stage`, run both store suites; then `commit`, `readback`, and `abort`,
running both suites after each move. Delete a provider helper only after the
shared equivalent is exercised through both public facades. The final diff
must contain no copied stage/commit state-machine SQL outside dialect methods.

- [ ] **Step 6: Run managed-store suites and commit**

```bash
uv run --frozen python -m pytest packages/timeseries/tests/test_artifacts.py packages/timeseries/tests/test_managed_sql.py packages/sqlite/tests/test_temporal_storage.py packages/postgres/tests/test_temporal_storage_recording.py packages/postgres/tests/test_temporal_storage_live.py packages/local_files/tests/test_managed_snapshot_recovery.py packages/process/tests/test_artifacts.py packages/maybe_sheet/tests/test_temporal_capabilities.py -q
git diff --check
git add packages/timeseries/src/open_table_connector/timeseries/artifacts.py packages/timeseries/src/open_table_connector/timeseries/managed_sql.py packages/timeseries/src/open_table_connector/timeseries/__init__.py packages/timeseries/tests/test_artifacts.py packages/timeseries/tests/test_managed_sql.py packages/sqlite/src/open_table_connector/sqlite/temporal.py packages/postgres/src/open_table_connector/postgres/temporal.py packages/local_files/src/open_table_connector/local_files/managed_snapshots.py packages/process/src/open_table_connector/process/artifacts.py packages/maybe_sheet/src/open_table_connector/maybe_sheet/temporal.py packages/sqlite/tests/test_temporal_storage.py packages/postgres/tests/test_temporal_storage_recording.py packages/postgres/tests/test_temporal_storage_live.py packages/process/tests/test_artifacts.py packages/maybe_sheet/tests/test_temporal_capabilities.py docs/reviews/2026-08-31-critical-review-remediation.md
git commit -m "refactor: centralize managed artifact and SQL lifecycle logic"
```

### Task 3: Serialize temporal evidence once and vectorize bucket evaluation

**Files:**
- Modify: `packages/timeseries/src/open_table_connector/timeseries/evaluator.py:58-548`
- Modify: `packages/timeseries/src/open_table_connector/timeseries/buckets.py`
- Create: `packages/timeseries/tests/test_evaluator_evidence.py`
- Modify: `packages/timeseries/tests/test_evaluator_buckets.py`
- Modify: `packages/timeseries/tests/test_evaluator_bounds.py`
- Modify: `benchmarks/temporal_evaluator.py`
- Modify: `docs/reviews/2026-08-31-critical-review-remediation.md`

**Interfaces:**
- Produces: `ArrowEvidence(table: pa.Table, ipc_bytes: bytes, schema_fingerprint: str, content_fingerprint: str)`; `build_arrow_evidence(table: pa.Table) -> ArrowEvidence`; `fixed_bucket_labels(series: pl.Series, bucket: FixedBucket) -> pl.Series`; `calendar_bucket_labels(series: pl.Series, bucket: CalendarBucket) -> pl.Series`.
- Consumes: canonical v1 Arrow IPC encoding, fingerprint rules from the correctness plan, and existing `calendar_bucket_start()` semantics.

- [ ] **Step 1: Prove the existing duplicate work**

```python
def test_execute_serializes_each_result_once(monkeypatch) -> None:
    calls: Counter[int] = Counter()
    original = evaluator._arrow_ipc_bytes
    def counted(table: pa.Table) -> bytes:
        calls[id(table)] += 1
        return original(table)
    monkeypatch.setattr(evaluator, "_arrow_ipc_bytes", counted)
    execute_fixture()
    assert calls and all(count == 1 for count in calls.values())
    assert len(calls) == 2  # source and final result

def test_calendar_labels_call_scalar_logic_once_per_unique_timestamp(monkeypatch) -> None:
    calls = count_calendar_calls(monkeypatch, values=[T0, T0, T1, T1, T1])
    assert calls == 2
```

Add equivalence cases for negative fixed-bucket deltas, offsets, nulls, DST,
and unordered duplicate timestamps.

- [ ] **Step 2: Run the evidence and bucket tests to confirm the red phase**

```bash
uv run --frozen python -m pytest packages/timeseries/tests/test_evaluator_evidence.py packages/timeseries/tests/test_evaluator_buckets.py -q
```

- [ ] **Step 3: Introduce one evidence object at the execution boundary**

Serialize the source table once after its bounded read and the result table
once after final ordering/validation. Derive each content identity and byte
count from its one byte string. Derive schema identity from the schema, not by
serializing either table again. Pass source/result `ArrowEvidence` into
`_receipt`; remove repeated IPC conversion from receipt and result construction.

- [ ] **Step 4: Vectorize fixed buckets and de-duplicate calendar mapping**

Use Polars integer expressions for fixed buckets:

```python
delta = pl.col(field).dt.epoch("ns") - origin_ns - offset_ns
quotient = delta // width_ns
label_ns = origin_ns + offset_ns + quotient * width_ns
```

Confirm Polars floor division on negative integers with an explicit test; if
the supported Polars range differs, use the same quotient/remainder correction
as the SQLite correctness fix. For calendar buckets, select unique non-null
timestamps, map the scalar timezone function once per unique value, then join
labels back by timestamp. Preserve null and row-order behavior.

- [ ] **Step 5: Run evaluator/conformance suites and commit**

```bash
uv run --frozen python -m pytest packages/timeseries/tests specification/conformance/timeseries -q
git diff --check
git add packages/timeseries/src/open_table_connector/timeseries/evaluator.py packages/timeseries/src/open_table_connector/timeseries/buckets.py packages/timeseries/tests/test_evaluator_evidence.py packages/timeseries/tests/test_evaluator_buckets.py packages/timeseries/tests/test_evaluator_bounds.py benchmarks/temporal_evaluator.py docs/reviews/2026-08-31-critical-review-remediation.md
git commit -m "perf: eliminate repeated temporal serialization and bucket loops"
```

### Task 4: Push true projection while keeping source revision projection-independent

**Files:**
- Modify: `packages/timeseries/src/open_table_connector/timeseries/evaluator.py:58-226`
- Modify: `packages/timeseries/src/open_table_connector/timeseries/storage.py`
- Modify: `packages/timeseries/src/open_table_connector/timeseries/__init__.py`
- Modify: `packages/sqlite/src/open_table_connector/sqlite/temporal.py:673-808`
- Modify: `packages/postgres/src/open_table_connector/postgres/temporal.py:804-935`
- Modify: `packages/local_files/src/open_table_connector/local_files/temporal_csv.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/temporal_json.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/temporal_excel.py`
- Modify: `packages/timeseries/tests/test_storage_protocols.py`
- Create: `packages/timeseries/tests/test_source_revision.py`
- Modify: `packages/sqlite/tests/test_temporal_storage.py`
- Modify: `packages/postgres/tests/test_temporal_storage_recording.py`
- Modify: `packages/local_files/tests/test_temporal_csv.py`
- Modify: `packages/local_files/tests/test_temporal_json.py`
- Modify: `packages/local_files/tests/test_temporal_excel.py`

**Interfaces:**
- Produces: `TemporalSourceRead(table: pa.Table, source_revision: str, rows_examined: int | None, bytes_examined: int | None)`; `TemporalSource.read_bounded(...) -> TemporalSourceRead`.
- Consumes: `_required_fields()` and provider snapshot identity. PostgreSQL revision hashes `txid_current_snapshot()` plus the target table OID; SQLite revision hashes the read-transaction `PRAGMA data_version`, database header change counter, WAL identity when present, and target name, rejecting a token capture that changes around the read; managed-file revision is the immutable snapshot/content reference; in-memory fallback hashes a canonical full-source representation once at source construction.

- [ ] **Step 1: Write projection and revision invariants**

```python
def test_source_receives_only_fields_required_by_plan() -> None:
    source = RecordingSource(table_with_extra_columns())
    PolarsTemporalExecutor(source).execute(projecting_request(("entity", "ts")))
    assert source.projection == ("entity", "ts")

def test_source_revision_is_independent_of_projection() -> None:
    narrow = execute_projection(("entity", "ts"))
    wide = execute_projection(("entity", "ts", "value"))
    assert narrow.receipt.source_revision == wide.receipt.source_revision
```

Add provider-level SQL recording tests that inspect selected columns, plus a
mutation-between-snapshots case proving the revision changes when source data
changes.

- [ ] **Step 2: Run the new invariants and confirm the red phase**

```bash
uv run --frozen python -m pytest packages/timeseries/tests/test_source_revision.py packages/timeseries/tests/test_storage_protocols.py -q
```

- [ ] **Step 3: Introduce `TemporalSourceRead` and adapt sources**

Change the protocol first, then adapt test fakes, local sources, SQLite, and
PostgreSQL. Each source computes its snapshot identity independently of the
selected column bytes and returns only `_required_fields(plan, descriptor)`.
The evaluator consumes `read.table` for semantics and `read.source_revision`
for the receipt; it never re-hashes the projected table as source evidence.

- [ ] **Step 4: Push projections into actual I/O**

SQL builders emit only quoted required columns. CSV/JSON use PyArrow reader
projection where supported; Excel may parse its sheet but must drop unrelated
columns before Arrow conversion. Record `rows_examined` and `bytes_examined`
when the provider can measure them, leaving `None` rather than inventing a
number.

- [ ] **Step 5: Run provider parity and commit**

```bash
uv run --frozen python -m pytest packages/timeseries/tests packages/sqlite/tests packages/postgres/tests packages/local_files/tests specification/conformance/timeseries -q
git diff --check
git add packages/timeseries/src/open_table_connector/timeseries/evaluator.py packages/timeseries/src/open_table_connector/timeseries/storage.py packages/timeseries/src/open_table_connector/timeseries/__init__.py packages/sqlite/src/open_table_connector/sqlite/temporal.py packages/postgres/src/open_table_connector/postgres/temporal.py packages/local_files/src/open_table_connector/local_files/temporal_csv.py packages/local_files/src/open_table_connector/local_files/temporal_json.py packages/local_files/src/open_table_connector/local_files/temporal_excel.py packages/timeseries/tests/test_storage_protocols.py packages/timeseries/tests/test_source_revision.py packages/sqlite/tests/test_temporal_storage.py packages/postgres/tests/test_temporal_storage_recording.py packages/local_files/tests/test_temporal_csv.py packages/local_files/tests/test_temporal_json.py packages/local_files/tests/test_temporal_excel.py docs/reviews/2026-08-31-critical-review-remediation.md
git commit -m "perf: push temporal projection without weakening source evidence"
```

### Task 5: Add an explicit bounded-read v2 capability for streaming CLI limits

**Files:**
- Create: `packages/contract/src/open_table_connector/contract/bounded_reads.py`
- Modify: `packages/contract/src/open_table_connector/contract/capabilities.py`
- Modify: `packages/contract/src/open_table_connector/contract/__init__.py`
- Create: `specification/schemas/bounded-read-receipt-v2.schema.json`
- Create: `specification/schemas/bounded-table-read-request-v2.schema.json`
- Modify: `specification/schemas/capability-manifest-v1.schema.json`
- Create: `packages/contract/tests/test_bounded_reads.py`
- Create: `packages/local_files/src/open_table_connector/local_files/bounded_reader.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/identity.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/manifest.py`
- Create: `packages/local_files/tests/test_bounded_reader.py`
- Modify: `packages/cli/src/open_table_connector/cli/adapters.py`
- Modify: `packages/cli/src/open_table_connector/cli/pipeline.py`
- Modify: `packages/cli/src/open_table_connector/cli/registry.py`
- Modify: `packages/cli/tests/test_pipeline.py`
- Modify: `packages/cli/tests/test_cli_e2e.py`
- Modify: `benchmarks/cli_streaming.py`

**Interfaces:**
- Produces: `BOUNDED_ARROW_TABLE_READ_CAPABILITY = CapabilityIdentity("table.read.arrow.bounded", "2.0")`; `ReadExtent(COMPLETE, TRUNCATED)`; `BoundedTableReadRequest(uri, max_output_rows, resource_limits)`; `BoundedReadReceipt(connector, capability, operation_id, safe_uri, mode, source_snapshot_reference, schema_fingerprint, emitted_content_fingerprint, coordinate_convention, rows_emitted, batches_emitted, extent, next_token)`; `BoundedArrowTableReader.read_arrow_bounded(request) -> BoundedArrowTableReadResult`.
- Consumes: ordinary hard `ResourceLimits`, complete v1 reader fallback, CLI `--limit`, and local codec inference from the packaging plan.

- [ ] **Step 1: Write closed-wire and completeness tests**

```python
def test_truncated_result_can_never_decode_as_neutral_v1_receipt() -> None:
    result = bounded_reader.read_arrow_bounded(request(max_output_rows=2))
    assert result.receipt.extent is ReadExtent.TRUNCATED
    assert result.table.num_rows == 2
    with pytest.raises(ValueError):
        NeutralReceipt.from_wire(result.receipt.to_wire())

def test_cli_uses_bounded_capability_only_when_advertised() -> None:
    result = run_cli_read(limit=2, connector=bounded_recording_connector())
    assert result.connector.bounded_calls == 1
    assert result.connector.complete_calls == 0
```

Add schema parity, unknown-field rejection, zero/negative limit validation,
complete-short-file, truncated-large-file, byte-bound, CSV quoted-newline, and
JSONL cases. The truncated receipt must contain no `next_token` unless the
provider can actually resume from it.

- [ ] **Step 2: Run contract and CLI tests to confirm the red phase**

```bash
uv run --frozen python -m pytest packages/contract/tests/test_bounded_reads.py packages/local_files/tests/test_bounded_reader.py packages/cli/tests/test_pipeline.py -q
```

- [ ] **Step 3: Add the closed v2 contract and manifest advertisement**

Keep v1 types unchanged. The v2 receipt is a separate closed document and
does not contain or inherit a `NeutralReceipt`; its `rows_emitted`,
`batches_emitted`, and `emitted_content_fingerprint` fields describe emitted
rows, while `extent` states whether they cover the entire source.
`source_snapshot_reference` is nullable and may be populated only from a
provider snapshot token or a complete-source hash; never derive it from the
emitted prefix. Add schema
and Python allowlists and cross-check them in schema-parity tests. Advertise
v2 only from connectors that implement it.

- [ ] **Step 4: Stream local CSV and JSONL in record batches**

CSV uses `pyarrow.csv.open_csv`; JSONL uses a batch iterator over decoded
lines. Stop after enough rows to determine `COMPLETE` versus `TRUNCATED`
(read at most one record beyond the requested output), slice the final batch,
and enforce the hard byte/time bounds during iteration. Parquet/Arrow/Excel
continue through complete v1 reads until they gain independently tested
bounded readers.

- [ ] **Step 5: Select bounded v2 in the CLI without changing fallback truth**

When `--limit` is set and the route advertises v2, call
`read_arrow_bounded`. Otherwise call the complete v1 reader and slice only for
presentation. JSON summaries name the receipt version and extent. `convert`
and `import` never use a truncated read unless a future command explicitly
opts into partial transfer. Delete the legacy Google/Feishu read-entire-table
existence preflights (the correctness plan makes their `error` policy an
immediate rejection). Any adapter that retains an existence check must call a
bounded capability with `max_output_rows=1`; add a recording-adapter test that
fails if a complete read is used for that probe.

- [ ] **Step 6: Run contract/local/CLI suites and commit**

```bash
uv run --frozen python -m pytest packages/contract/tests packages/local_files/tests packages/cli/tests specification/conformance/universal/test_cli_surface.py -q
git diff --check
git add packages/contract/src/open_table_connector/contract/bounded_reads.py packages/contract/src/open_table_connector/contract/capabilities.py packages/contract/src/open_table_connector/contract/__init__.py packages/contract/tests/test_bounded_reads.py specification/schemas/bounded-read-receipt-v2.schema.json specification/schemas/bounded-table-read-request-v2.schema.json specification/schemas/capability-manifest-v1.schema.json packages/local_files/src/open_table_connector/local_files/bounded_reader.py packages/local_files/src/open_table_connector/local_files/identity.py packages/local_files/src/open_table_connector/local_files/manifest.py packages/local_files/tests/test_bounded_reader.py packages/cli/src/open_table_connector/cli/adapters.py packages/cli/src/open_table_connector/cli/pipeline.py packages/cli/src/open_table_connector/cli/registry.py packages/cli/tests/test_pipeline.py packages/cli/tests/test_cli_e2e.py benchmarks/cli_streaming.py docs/reviews/2026-08-31-critical-review-remediation.md
git commit -m "feat: add truthful bounded reads for CLI limits"
```

### Task 6: Bound hosted transports and chunk Feishu writes

**Files:**
- Modify: `packages/feishu_bitable/src/open_table_connector/feishu_bitable/connector.py:30-175`
- Modify: `packages/feishu_bitable/tests/test_connector.py`
- Modify: `packages/cli/tests/test_pipeline.py`
- Create: `packages/feishu_bitable/tests/test_transport_limits.py`
- Modify: `packages/google_sheets/src/open_table_connector/google_sheets/connector.py:25-180`
- Modify: `packages/google_sheets/tests/test_connector.py`
- Create: `packages/google_sheets/tests/test_transport_limits.py`
- Modify: `docs/reviews/2026-08-31-critical-review-remediation.md`

**Interfaces:**
- Produces: `FEISHU_BATCH_CREATE_LIMIT = 500`; `FEISHU_MAX_RESPONSE_BYTES = GOOGLE_MAX_RESPONSE_BYTES = 8 * 1024 * 1024`; `_record_batches(records, size=FEISHU_BATCH_CREATE_LIMIT) -> Iterator[list[Mapping[str, object]]]`; both urllib transports preserve authentication/timeout/provider/response-limit error mapping.
- Consumes: the official 500-record `batch_create` limit, typed `ConnectorErrorCode`, redaction helpers from the transport/security plan, and the existing injected transport protocol.

- [ ] **Step 1: Add boundary and typed-error tests**

```python
@pytest.mark.parametrize("rows,batches", [
    (0, []), (1, [1]), (500, [500]), (501, [500, 1]), (1001, [500, 500, 1]),
])
def test_feishu_chunks_batch_create_at_provider_limit(rows: int, batches: list[int]) -> None:
    transport = RecordingTransport()
    result = connector(transport).write(write_request(rows))
    assert [len(call.body["records"]) for call in transport.calls] == batches
    assert result.receipt.row_count == rows
    assert result.receipt.batch_count == len(batches)

@pytest.mark.parametrize("status,code", [
    (401, ConnectorErrorCode.AUTHENTICATION),
    (403, ConnectorErrorCode.AUTHENTICATION),
    (429, ConnectorErrorCode.RESOURCE_LIMIT_EXCEEDED),
])
def test_feishu_transport_preserves_typed_http_failures(status, code) -> None:
    assert raised_code(status) is code
```

Add timeout, malformed JSON, response larger than 8 MiB, provider JSON
`code != 0`, and mid-sequence batch failure cases. Assert exception details
contain batch index and accepted-row count but no token, URL credentials, or
response body. Mirror the HTTP/timeout/malformed/oversized cases through
`UrllibGoogleSheetsTransport` so the two hosted urllib paths share the same
typed behavior.

- [ ] **Step 2: Run Feishu tests and confirm the red phase**

```bash
uv run --frozen python -m pytest packages/feishu_bitable/tests/test_connector.py packages/feishu_bitable/tests/test_transport_limits.py packages/google_sheets/tests/test_connector.py packages/google_sheets/tests/test_transport_limits.py -q
```

- [ ] **Step 3: Bound urllib responses before JSON decoding**

Each urllib transport reads at most its `MAX_RESPONSE_BYTES + 1`; if the extra byte exists, raise
`RESOURCE_LIMIT_EXCEEDED`. Map HTTP 401/403 to `AUTHENTICATION`, 408/timeout to
`TIMEOUT`, 429 to `RESOURCE_LIMIT_EXCEEDED`, other HTTP/provider failures to
`EXECUTION_FAILED`, and malformed JSON to `PROTOCOL_INVALID`. Preserve
provider request IDs in redacted details when present.

- [ ] **Step 4: Chunk sequential writes and aggregate truthful evidence**

Send batches in source order. Stop on the first failure. On success, aggregate
provider record IDs into one deterministic receipt reference without storing
the full response. `row_count` is total accepted rows and `batch_count` is
actual calls. For zero rows, make no HTTP call and return a zero-row receipt.
Do not retry a mutating batch unless Feishu supplies an idempotency mechanism
and a separate plan specifies its use.

- [ ] **Step 5: Run provider and CLI integration tests and commit**

```bash
uv run --frozen python -m pytest packages/feishu_bitable/tests packages/google_sheets/tests packages/cli/tests/test_pipeline.py -q
git diff --check
git add packages/feishu_bitable/src/open_table_connector/feishu_bitable/connector.py packages/feishu_bitable/tests/test_connector.py packages/feishu_bitable/tests/test_transport_limits.py packages/google_sheets/src/open_table_connector/google_sheets/connector.py packages/google_sheets/tests/test_connector.py packages/google_sheets/tests/test_transport_limits.py packages/cli/tests/test_pipeline.py docs/reviews/2026-08-31-critical-review-remediation.md
git commit -m "fix: bound hosted responses and chunk Feishu writes"
```

### Task 7: Capture after-results and close only evidence-backed performance findings

**Files:**
- Modify: `benchmarks/results/README.md`
- Create: new `benchmarks/results/*-after-*.json` artifacts
- Modify: `benchmarks/run.py`
- Create: `benchmarks/test_results.py`
- Modify: `docs/reviews/2026-08-31-critical-review-remediation.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Produces: `compare_results(before: BenchmarkResult, after: BenchmarkResult) -> BenchmarkComparison`; ledger entries with `verified`, `acceptance`, and exact artifact/command references.
- Consumes: same machine/runtime/workload compatibility rules and the Task 1 baseline.

- [ ] **Step 1: Add comparison rejection tests**

```python
@pytest.mark.parametrize("field", ["python", "pyarrow", "polars", "platform", "cpu"])
def test_comparison_rejects_incompatible_environment(field: str) -> None:
    before, after = comparable_results()
    setattr(after.environment, field, "different")
    with pytest.raises(ValueError, match=field):
        compare_results(before, after)
```

Also reject different data seed, rows, unique timestamps, warmups, or
repetitions. Comparison reports median and peak-memory ratios plus raw samples;
it never labels statistical significance from seven samples.

- [ ] **Step 2: Run comparison tests and implement strict matching**

```bash
uv run --frozen python -m pytest benchmarks -q
```

Implement exact environment/workload compatibility checks and a human-readable
Markdown summary generated from, but never replacing, the raw JSON.

- [ ] **Step 3: Capture the post-refactor artifact on the baseline machine**

```bash
uv run --frozen python -m benchmarks.run --suite all --phase after --repetitions 7
uv run --frozen python -m benchmarks.run --compare before after
```

If the original environment is unavailable, leave performance ledger claims
as `hypothesis` and record `after measurement blocked: incompatible
environment`; do not manufacture a comparison.

- [ ] **Step 4: Run the complete verification matrix**

```bash
uv run --frozen ruff check .
uv run --frozen mypy packages
uv run --frozen python -m pytest -q
uv run --frozen python scripts/check_package_boundaries.py
uv run --frozen python scripts/verify_compatibility.py
uv run --frozen python scripts/smoke_wheels.py --build
git diff --check
```

- [ ] **Step 5: Update evidence and commit**

Mark T2/F1–F4 resolved only where acceptance tests and compatible measurements
support the claim. Document bounded-read v2, provider batch behavior, and
managed-SQL consolidation in `CHANGELOG.md`.

```bash
git add benchmarks/results/README.md benchmarks/results/*-after-*.json benchmarks/run.py benchmarks/test_results.py docs/reviews/2026-08-31-critical-review-remediation.md CHANGELOG.md
git commit -m "perf: record critical review remediation evidence"
```

## Final Acceptance

- [ ] Existing correctness, security, process-wire, and conformance suites remain green.
- [ ] SQLite and PostgreSQL public stores pass the same shared lifecycle transcript and their provider-specific transaction tests.
- [ ] Each evaluator source/result table produces at most one Arrow IPC serialization; fixed buckets are vectorized; calendar scalar conversion count is bounded by unique timestamps.
- [ ] Projection changes do not change `source_revision`; a physical source mutation does.
- [ ] A truncated result is observable only through bounded-read v2 and cannot decode as a complete v1 neutral receipt.
- [ ] Feishu write calls never contain more than 500 records and provider responses are bounded before decoding.
- [ ] Performance claims cite compatible raw before/after artifacts; unmatched claims remain explicitly labeled hypotheses.
- [ ] The full test, lint, typing, boundary, compatibility, wheel-smoke, and diff-check matrix passes.
