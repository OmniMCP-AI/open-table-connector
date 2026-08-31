# Critical Review Correctness and Data Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate silent wrong results, row loss, ineffective write-safety modes, incorrect receipt evidence, and broken managed-storage paths identified as A1–A15.

**Architecture:** Correct semantics at their source and share precision/identity helpers across providers. Every fix begins with a reproduction that observes the public result or wire evidence; provider parity tests follow whenever Polars, SQLite, and PostgreSQL implement the same operation. Hosted connectors reject safety modes they cannot enforce before mutation.

**Tech Stack:** Python 3.11–3.14, PyArrow 14–19, Polars 1.x, SQLite, PostgreSQL 17, psycopg2, urllib transports, pytest 9, and uv workspace commands.

**Spec:** `docs/superpowers/specs/2026-08-31-critical-review-remediation-design.md`

**Owned findings:** A1, A2, A3, A4, A5, A6, A7, A8, A9, A10, A11, A12, A13, A14, A15, and D1. The specification plan establishes A2/A8/A9 wire prerequisites; this plan closes their runtime behavior.

**Prerequisite:** Complete Tasks 1 and 3 of `docs/superpowers/plans/2026-08-31-critical-review-specification-conformance.md` so COUNT and receipt bounds have matching normative, Python, and schema rules.

**Execution status (2026-08-31):** Tasks 1–7 implemented and verified in the
isolated remediation worktree. See the remediation ledger for commit-backed
evidence and any findings that remain open outside this plan.

## Global Constraints

- Preserve valid v1 wire documents; version any public identity whose canonical bytes must change.
- `count` remains row count equivalent to `COUNT(*)`; providers never interpret a non-null COUNT field.
- Gap-fill keeps a left join from the generated domain and checks the final output bound.
- Timestamp conversions honor the descriptor's second, millisecond, microsecond, or nanosecond precision.
- Hosted `if_exists="error"` is rejected before provider I/O unless the provider can enforce atomic create-if-empty.
- Google Sheets user data is written with `valueInputOption=RAW`.
- All invalid plan behavior maps to `TemporalErrorCode.PROTOCOL_INVALID`, not raw library exceptions.
- Work red-green-refactor. Each task runs focused tests, owning package tests, `git diff --check`, updates the remediation ledger, and creates one Conventional Commit.
- Run `uv sync --all-packages --group dev` before executing tests in a fresh checkout.

---

## File Map

- `packages/timeseries/src/open_table_connector/timeseries/buckets.py` — fixed and calendar bucket arithmetic.
- `packages/timeseries/src/open_table_connector/timeseries/precision.py` — shared wire/storage timestamp conversion.
- `packages/timeseries/src/open_table_connector/timeseries/evaluator.py` — bounded execution, gap-fill, validation mapping, receipts, and injected identity.
- `packages/contract/src/open_table_connector/contract/fingerprints.py` — chunk-insensitive v1 table fingerprint.
- `packages/sqlite/src/open_table_connector/sqlite/temporal.py` — precision-aware predicates/receipts and floor-division lowering.
- `packages/sqlite/src/open_table_connector/sqlite/reader.py` — component-wise qualified identifiers.
- `packages/postgres/src/open_table_connector/postgres/temporal.py` — schema bootstrap and repeatable-read snapshot transactions.
- `packages/google_sheets/src/open_table_connector/google_sheets/connector.py` — gid resolution, raw writes, and safe policy rejection.
- `packages/feishu_bitable/src/open_table_connector/feishu_bitable/connector.py` — safe policy rejection.
- `packages/cli/src/open_table_connector/cli/output.py` — real CSV cell encoding.
- `packages/cli/src/open_table_connector/cli/adapters.py` — explicit local input-format dispatch.

### Task 1: Fix calendar progression and protect gap-fill domain integrity

**Files:**
- Modify: `packages/timeseries/src/open_table_connector/timeseries/buckets.py:45-90`
- Modify: `packages/timeseries/src/open_table_connector/timeseries/evaluator.py:352-423`
- Modify: `packages/timeseries/tests/fixtures/calendar-cases.json`
- Modify: `packages/timeseries/tests/test_evaluator_buckets.py`
- Modify: `packages/timeseries/tests/test_evaluator_gapfill.py`
- Create: `packages/timeseries/tests/test_bucket_properties.py`
- Modify: `specification/fixtures/timeseries/v1/expected/gap-fill.json`

**Interfaces:**
- Consumes: `calendar_bucket_start(label, bucket) -> str` and `CalendarBucket`.
- Produces: `calendar_bucket_next(label, bucket) -> str` satisfying strict advance and start/next round-trip; `_bucket_domain()` contains every aggregate bucket; `_gap_fill()` never exceeds `max_rows` after joining.

- [ ] **Step 1: Add DST regression and invariant tests**

Add Santiago and New York spring/fall transitions:

```python
@pytest.mark.parametrize("timezone,start", [
    ("America/Santiago", "2026-09-05T04:00:00.000000000Z"),
    ("America/New_York", "2026-03-07T05:00:00.000000000Z"),
])
def test_calendar_bucket_next_round_trips_across_dst(timezone: str, start: str) -> None:
    bucket = CalendarBucket(1, CalendarUnit.DAY, timezone, 1, start, 0)
    current = calendar_bucket_start(start, bucket)
    for _ in range(4):
        following = calendar_bucket_next(current, bucket)
        assert _timestamp_ns(following) > _timestamp_ns(current)
        assert calendar_bucket_start(following, bucket) == following
        current = following
```

Add a gap-fill case whose source row was previously dropped and assert its
bucket and aggregate remain in output. Add a test that monkeypatches a bad
domain and expects `PROTOCOL_INVALID`, not silent loss. In
`test_bucket_properties.py`, exhaust a deterministic grid of negative/positive
epochs, day/week/month units, month ends, leap days, and IANA zones with
gaps/folds; assert `next > current`, `start(next) == next`, and every generated
domain label is unique.

- [ ] **Step 2: Run the focused tests and confirm the red phase**

```bash
uv run --frozen python -m pytest packages/timeseries/tests/test_evaluator_buckets.py packages/timeseries/tests/test_evaluator_gapfill.py packages/timeseries/tests/test_bucket_properties.py -q
```

Expected: at least the Santiago progression or retained-row assertion fails.

- [ ] **Step 3: Correct calendar progression and assert membership**

Advance in local calendar space from the canonical bucket boundary, resolve
the local wall time with `ZoneInfo`, and canonicalize the result through
`calendar_bucket_start`. In `_gap_fill`, compute
`aggregate.select(keys).join(domain_keys, on=keys, how="anti")`; raise
`TemporalExtensionError(PROTOCOL_INVALID, "aggregate bucket is outside gap-fill domain")`
when non-empty. Keep `expanded.join(aggregate, how="left")`.

- [ ] **Step 4: Check the bound after the join and update the golden output**

Call `_check_size_bounds(expanded.height, estimated_size, bounds, "gap-fill result")`
after the join/fills and before return. Recalculate the expected gap-fill JSON
manually from the normative domain, then inspect the diff row by row.

- [ ] **Step 5: Run bucket, gap-fill, and semantic conformance tests**

```bash
uv run --frozen python -m pytest packages/timeseries/tests/test_evaluator_buckets.py packages/timeseries/tests/test_evaluator_gapfill.py packages/timeseries/tests/test_bucket_properties.py specification/conformance/timeseries/test_semantic_matrix.py -q
git diff --check
```

- [ ] **Step 6: Update A1 in the ledger and commit**

```bash
git add packages/timeseries/src/open_table_connector/timeseries/buckets.py packages/timeseries/src/open_table_connector/timeseries/evaluator.py packages/timeseries/tests/fixtures/calendar-cases.json packages/timeseries/tests/test_evaluator_buckets.py packages/timeseries/tests/test_evaluator_gapfill.py packages/timeseries/tests/test_bucket_properties.py specification/fixtures/timeseries/v1/expected/gap-fill.json docs/reviews/2026-08-31-critical-review-remediation.md
git commit -m "fix: preserve gap-fill rows across DST"
```

### Task 2: Centralize precision conversion and correct SQL temporal arithmetic

**Files:**
- Create: `packages/timeseries/src/open_table_connector/timeseries/precision.py`
- Modify: `packages/timeseries/src/open_table_connector/timeseries/__init__.py`
- Create: `packages/timeseries/tests/test_precision.py`
- Modify: `packages/timeseries/tests/test_bucket_properties.py`
- Modify: `packages/sqlite/src/open_table_connector/sqlite/temporal.py:142-230,730-848`
- Modify: `packages/sqlite/tests/temporal_fixtures.py`
- Modify: `packages/sqlite/tests/test_temporal_lowering.py`
- Modify: `packages/sqlite/tests/test_temporal_storage.py`
- Modify: `packages/postgres/src/open_table_connector/postgres/temporal.py:930-970`
- Modify: `packages/postgres/tests/test_temporal_storage_recording.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/managed_snapshots.py`

**Interfaces:**
- Produces: `timestamp_to_storage(value: str, precision: TimestampPrecision) -> int`; `storage_to_timestamp(value: int, precision: TimestampPrecision) -> str`; `arrow_time_bounds(table: pa.Table, field: str, precision: TimestampPrecision) -> tuple[str, str] | None`.
- Consumes: `TimestampPrecision` and RFC 3339 UTC values validated by `_utc_parts()`.

- [ ] **Step 1: Write precision round-trip tests for all four units**

```python
@pytest.mark.parametrize("precision,value,stored", [
    (TimestampPrecision.SECOND, "1969-12-31T23:59:59Z", -1),
    (TimestampPrecision.MILLISECOND, "2026-08-29T00:00:00.123Z", 1787961600123),
    (TimestampPrecision.MICROSECOND, "2026-08-29T00:00:00.123456Z", 1787961600123456),
    (TimestampPrecision.NANOSECOND, "2026-08-29T00:00:00.123456789Z", 1787961600123456789),
])
def test_timestamp_storage_round_trip(precision, value, stored) -> None:
    assert timestamp_to_storage(value, precision) == stored
    assert storage_to_timestamp(stored, precision) == value
```

Add SQLite execution cases for seconds/milliseconds/microseconds and a fixed
bucket whose timestamp is before its origin. Extend the deterministic property
grid to assert storage/wire round-trips and mathematical floor-bucket
inequalities for representative negative/positive epochs at all precisions.

- [ ] **Step 2: Run precision and SQLite tests to confirm the red phase**

```bash
uv run --frozen python -m pytest packages/timeseries/tests/test_precision.py packages/sqlite/tests/test_temporal_lowering.py packages/sqlite/tests/test_temporal_storage.py -q
```

Expected: missing precision module or non-nanosecond filter returns no rows.

- [ ] **Step 3: Implement the shared conversion functions**

Use integer scale factors `{second: 1, millisecond: 1_000, microsecond:
1_000_000, nanosecond: 1_000_000_000}`. Preserve negative values with
`divmod`; never round through float or `datetime.timestamp()`.

- [ ] **Step 4: Apply precision to predicates, receipts, and fixed buckets**

SQLite `_where` and `_storage_where` use `timestamp_to_storage`. Both SQL
stores and local managed snapshots use `arrow_time_bounds`. Replace SQLite's
truncating bucket quotient with:

```sql
(delta / width) - CASE WHEN delta < 0 AND delta % width != 0 THEN 1 ELSE 0 END
```

where `delta = time - origin - offset`; multiply the floored quotient by width
and add origin/offset. Bind every repeated value as a parameter.

- [ ] **Step 5: Run all precision-sensitive provider tests**

```bash
uv run --frozen python -m pytest packages/timeseries/tests/test_precision.py packages/sqlite/tests packages/postgres/tests/test_temporal_storage_recording.py packages/local_files/tests/test_managed_csv.py packages/local_files/tests/test_managed_json.py -q
git diff --check
```

- [ ] **Step 6: Update A3/A5/A15 and commit**

```bash
git add packages/timeseries/src/open_table_connector/timeseries/precision.py packages/timeseries/src/open_table_connector/timeseries/__init__.py packages/timeseries/tests/test_precision.py packages/timeseries/tests/test_bucket_properties.py packages/sqlite/src/open_table_connector/sqlite/temporal.py packages/sqlite/tests/temporal_fixtures.py packages/sqlite/tests/test_temporal_lowering.py packages/sqlite/tests/test_temporal_storage.py packages/postgres/src/open_table_connector/postgres/temporal.py packages/postgres/tests/test_temporal_storage_recording.py packages/local_files/src/open_table_connector/local_files/managed_snapshots.py docs/reviews/2026-08-31-critical-review-remediation.md
git commit -m "fix: honor temporal timestamp precision"
```

### Task 3: Separate PostgreSQL schema bootstrap from snapshot transactions

**Files:**
- Modify: `packages/postgres/src/open_table_connector/postgres/temporal.py:562-720`
- Modify: `packages/postgres/tests/test_temporal_storage_recording.py`
- Modify: `packages/postgres/tests/test_temporal_storage_live.py`

**Interfaces:**
- Produces: `PostgresManagedTemporalStore.ensure_schema(credentials=None) -> None`; `_connection(..., ensure_schema: bool = True)`; snapshot reads start `REPEATABLE READ` before any query in their transaction.
- Consumes: existing connection factory and metadata schema.

- [ ] **Step 1: Add a recording test for SQL order**

```python
def test_readback_sets_isolation_before_any_query(store, recording_factory, request) -> None:
    store.ensure_schema()
    recording_factory.statements.clear()
    store.readback(request)
    assert recording_factory.statements[0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"
    assert not any(statement.startswith("CREATE ") for statement in recording_factory.statements)
```

- [ ] **Step 2: Run the recording test and confirm the red phase**

```bash
uv run --frozen python -m pytest packages/postgres/tests/test_temporal_storage_recording.py -q
```

Expected: CREATE statements precede SET TRANSACTION.

- [ ] **Step 3: Implement idempotent bootstrap and clean snapshot transactions**

`ensure_schema()` opens and commits its own connection. Constructor does not
perform I/O. Stage/commit/abort call the ensuring connection path; readback and
read_snapshot call `ensure_schema()` before opening a new connection with
`ensure_schema=False`, then execute isolation and timeout first.

- [ ] **Step 4: Run the configured live lifecycle**

```bash
uv run --frozen python -m pytest packages/postgres/tests/test_temporal_storage_recording.py -q
OTC_TEST_POSTGRES_DSN="$OTC_TEST_POSTGRES_DSN" uv run --frozen python -m pytest packages/postgres/tests/test_temporal_storage_live.py -q
```

Expected: recording tests pass. The live command passes when the DSN is
configured; otherwise record `configured_live` as open rather than passed.

- [ ] **Step 5: Update A4 evidence and commit**

```bash
git add packages/postgres/src/open_table_connector/postgres/temporal.py packages/postgres/tests/test_temporal_storage_recording.py packages/postgres/tests/test_temporal_storage_live.py docs/reviews/2026-08-31-critical-review-remediation.md
git commit -m "fix: initialize postgres temporal schema separately"
```

### Task 4: Enforce hosted write policies and resolve Google sheet IDs

**Files:**
- Modify: `packages/google_sheets/src/open_table_connector/google_sheets/connector.py:100-180`
- Modify: `packages/google_sheets/tests/test_connector.py`
- Modify: `packages/feishu_bitable/src/open_table_connector/feishu_bitable/connector.py:150-190`
- Modify: `packages/feishu_bitable/tests/test_connector.py`
- Modify: `packages/cli/src/open_table_connector/cli/adapters.py:130-210`
- Modify: `packages/cli/tests/test_pipeline.py`
- Modify: `specification/conformance/universal/test_table_connectors.py`

**Interfaces:**
- Produces: `GoogleSheetsConnector._sheet_title(spreadsheet_id: str, gid: int) -> str`; both hosted connectors and their CLI adapters reject unsupported `error` before source/destination provider I/O; Sheets uses `RAW`.
- Consumes: Google spreadsheet metadata `sheets.properties(sheetId,title)`.

- [ ] **Step 1: Write failing no-I/O policy and gid tests**

```python
@pytest.mark.parametrize("factory,uri", [
    (google_connector, TableURI("gsheets://sheet-123/Orders")),
    (feishu_connector, TableURI("feishu://app-token/table-id")),
])
def test_error_policy_is_rejected_before_provider_io(factory, uri) -> None:
    connector, transport = factory()
    with pytest.raises(ConnectorError) as raised:
        connector.write(TableWriteRequest(uri, pl.DataFrame({"id": [1]}), "error"))
    assert raised.value.code is ConnectorErrorCode.UNSUPPORTED_CAPABILITY
    assert transport.calls == []
```

Add a Google URL `#gid=42`; the fake metadata returns title `Orders`; assert
the values request uses `Orders`, not `42`. Assert writes contain
`valueInputOption=RAW`. Add CLI import tests proving `if_exists=error` invokes
neither the destination preflight reader nor the source reader for Google or
Feishu.

- [ ] **Step 2: Run hosted connector tests and confirm the red phase**

```bash
uv run --frozen python -m pytest packages/google_sheets/tests/test_connector.py packages/feishu_bitable/tests/test_connector.py -q
```

- [ ] **Step 3: Implement policy rejection, metadata resolution, and RAW writes**

Reject `error` before `resolve()` or transport calls. For shared URLs, parse
`gid` as a non-negative integer, request only sheet properties, require one
matching `sheetId`, and use its `title`. Map missing/duplicate matches to a
credential-safe `INVALID_URI` error. Replace both CLI adapters' legacy
read-entire-destination preflights with the same immediate
`UNSUPPORTED_CAPABILITY` rejection.

- [ ] **Step 4: Run hosted and universal conformance tests**

```bash
uv run --frozen python -m pytest packages/google_sheets/tests packages/feishu_bitable/tests packages/cli/tests/test_pipeline.py specification/conformance/universal/test_table_connectors.py -q
git diff --check
```

- [ ] **Step 5: Update A6/A12/D1 and commit**

```bash
git add packages/google_sheets/src/open_table_connector/google_sheets/connector.py packages/google_sheets/tests/test_connector.py packages/feishu_bitable/src/open_table_connector/feishu_bitable/connector.py packages/feishu_bitable/tests/test_connector.py packages/cli/src/open_table_connector/cli/adapters.py packages/cli/tests/test_pipeline.py specification/conformance/universal/test_table_connectors.py docs/reviews/2026-08-31-critical-review-remediation.md
git commit -m "fix: enforce hosted connector write safety"
```

### Task 5: Honor explicit local formats and emit uncorrupted CSV

**Files:**
- Modify: `packages/cli/src/open_table_connector/cli/output.py:54-110`
- Modify: `packages/cli/src/open_table_connector/cli/adapters.py:399-421`
- Modify: `packages/cli/tests/test_formats.py`
- Modify: `packages/cli/tests/test_local_format_adapters.py`
- Modify: `packages/cli/tests/test_cli_e2e.py`

**Interfaces:**
- Produces: `_csv_cell(value: Any) -> str`; explicit `from_format != AUTO` always selects the requested decoder for local paths.
- Consumes: Python `csv.writer`, existing `read_local()`, and `FormatName`.

- [ ] **Step 1: Write failing CSV and explicit-format tests**

```python
def test_summary_csv_preserves_pipes_backslashes_and_newlines() -> None:
    out = StringIO()
    emit_csv([{"value": "a|b\\c\nnext"}], out)
    assert list(csv.DictReader(StringIO(out.getvalue()))) == [
        {"value": "a|b\\c\nnext"}
    ]

@pytest.mark.parametrize("format_name", [FormatName.CSV, FormatName.EXCEL, FormatName.TABLE])
def test_explicit_from_format_is_not_replaced_by_probe(format_name, endpoint, monkeypatch) -> None:
    called = spy_read_local(monkeypatch)
    LocalAdapter().read(endpoint, CliOptions(from_format=format_name))
    assert called.formats == [format_name]
```

- [ ] **Step 2: Run focused CLI tests and confirm the red phase**

```bash
uv run --frozen python -m pytest packages/cli/tests/test_formats.py packages/cli/tests/test_local_format_adapters.py -q
```

- [ ] **Step 3: Separate CSV cells from Markdown display and route explicit formats**

`_csv_cell` returns scalar text unchanged and JSON-encodes dict/list values
with sorted keys. `emit_csv` passes values to `csv.writer`; it never calls the
Markdown `_display`. `_uses_legacy_reader` returns true for stdio or every
explicit `from_format`; AUTO retains content probing.

- [ ] **Step 4: Run CLI unit and e2e tests**

```bash
uv run --frozen python -m pytest packages/cli/tests -q
git diff --check
```

- [ ] **Step 5: Update A7/A10 and commit**

```bash
git add packages/cli/src/open_table_connector/cli/output.py packages/cli/src/open_table_connector/cli/adapters.py packages/cli/tests/test_formats.py packages/cli/tests/test_local_format_adapters.py packages/cli/tests/test_cli_e2e.py docs/reviews/2026-08-31-critical-review-remediation.md
git commit -m "fix: preserve explicit CLI formats and CSV cells"
```

### Task 6: Fix SQLite qualified reads and reject ephemeral managed stores

**Files:**
- Modify: `packages/sqlite/src/open_table_connector/sqlite/reader.py:55-80,202-228`
- Modify: `packages/sqlite/tests/test_reader.py`
- Modify: `packages/sqlite/src/open_table_connector/sqlite/temporal.py:808-825`
- Modify: `packages/sqlite/tests/test_temporal_storage.py`

**Interfaces:**
- Produces: `_quote_qualified_identifier(value: str) -> str`; `SQLiteManagedTemporalStore` rejects `sqlite:///:memory:` during construction.
- Consumes: existing `_IDENTIFIER` validation and SQLite URI resolution.

- [ ] **Step 1: Write failing qualified-name and managed-memory tests**

```python
def test_default_qualified_table_reads_main_table(sqlite_uri_with_table) -> None:
    result = SQLiteConnector().read_arrow(SQLiteTableReadRequest(sqlite_uri_with_table))
    assert result.table.to_pylist() == [{"id": 1}]

def test_managed_store_rejects_memory_database(tmp_path, descriptor) -> None:
    with pytest.raises(TemporalExtensionError, match="persistent database"):
        SQLiteManagedTemporalStore(TableURI("sqlite:///:memory:"), tmp_path, descriptor)
```

- [ ] **Step 2: Run SQLite tests and confirm the red phase**

```bash
uv run --frozen python -m pytest packages/sqlite/tests/test_reader.py packages/sqlite/tests/test_temporal_storage.py -q
```

- [ ] **Step 3: Quote components and fail closed on memory lifecycle**

Split a validated identifier on `.`, quote each component independently, and
join with `.`. Use the helper for reads, writes, and inspection. Reject the
`:memory:` path in the managed-store constructor with
`TemporalErrorCode.PROTOCOL_INVALID`; ordinary non-managed SQLite reads may
continue to use memory when the caller retains one transaction connection.

- [ ] **Step 4: Run the SQLite package suite**

```bash
uv run --frozen python -m pytest packages/sqlite/tests -q
git diff --check
```

- [ ] **Step 5: Update A11/A14 and commit**

```bash
git add packages/sqlite/src/open_table_connector/sqlite/reader.py packages/sqlite/src/open_table_connector/sqlite/temporal.py packages/sqlite/tests/test_reader.py packages/sqlite/tests/test_temporal_storage.py docs/reviews/2026-08-31-critical-review-remediation.md
git commit -m "fix: handle qualified sqlite resources safely"
```

### Task 7: Make fingerprints, receipts, identity, and output validation truthful

**Files:**
- Modify: `packages/contract/src/open_table_connector/contract/fingerprints.py:15-24`
- Modify: `packages/contract/tests/test_receipts.py`
- Modify: `packages/timeseries/src/open_table_connector/timeseries/evaluator.py:72-190,426-570`
- Modify: `packages/timeseries/src/open_table_connector/timeseries/plan.py:667-711`
- Modify: `packages/timeseries/tests/fixtures.py`
- Modify: `packages/timeseries/tests/test_evaluator_bounds.py`
- Modify: `packages/timeseries/tests/test_evaluator_gapfill.py`
- Modify: `packages/timeseries/tests/test_plan_wire.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/temporal_csv.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/temporal_json.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/temporal_excel.py`
- Modify: `packages/sqlite/src/open_table_connector/sqlite/temporal.py`
- Modify: `packages/postgres/src/open_table_connector/postgres/temporal.py`
- Modify: `packages/maybe_sheet/src/open_table_connector/maybe_sheet/temporal.py`

**Interfaces:**
- Produces: `canonical_arrow_table(table: pa.Table) -> pa.Table`; `PolarsTemporalExecutor(source, *, connector_identity: ConnectorIdentity)`; output-order validation against the operation's actual result fields.
- Consumes: provider `CONNECTOR_IDENTITY` constants and relaxed receipt bounds from the specification plan.

- [ ] **Step 1: Write failing chunk, receipt, identity, and output-order tests**

```python
def test_equal_tables_with_different_chunks_have_one_fingerprint() -> None:
    one = pa.table({"x": [1, 2, 3]})
    many = pa.Table.from_batches([
        pa.record_batch({"x": [1]}), pa.record_batch({"x": [2, 3]})
    ])
    assert one.equals(many)
    assert arrow_content_fingerprint(one) == arrow_content_fingerprint(many)

def test_gap_fill_receipt_reports_source_rows_without_inflation(execution) -> None:
    assert execution.receipt.examined_rows == 3
    assert execution.receipt.returned_rows == 6

def test_unknown_output_order_fails_as_protocol_invalid(executor, request) -> None:
    request = replace(request, plan=replace(request.plan, output_order=(OrderKey("missing", "asc"),)))
    with pytest.raises(TemporalExtensionError) as raised:
        executor.execute(request)
    assert raised.value.code is TemporalErrorCode.PROTOCOL_INVALID
```

- [ ] **Step 2: Run focused tests and confirm the red phase**

```bash
uv run --frozen python -m pytest packages/contract/tests/test_receipts.py packages/timeseries/tests/test_evaluator_bounds.py packages/timeseries/tests/test_evaluator_gapfill.py packages/timeseries/tests/test_plan_wire.py -q
```

- [ ] **Step 3: Canonicalize chunking and preserve truthful counters**

`canonical_arrow_table` calls `combine_chunks()` and reconstructs a table with
the original schema metadata in deterministic column order. Fingerprints use
that table. Remove both `max(examined, returned)` adjustments; validate source
and result bounds independently.

- [ ] **Step 4: Inject connector identity and validate output fields early**

Require a keyword-only `connector_identity`; update every executor wrapper to
pass its package identity. `validate_plan_for_descriptor` computes allowed
result fields from projection or `group_by + bucket + measure outputs`; reject
unknown order keys and duplicate aggregate outputs. Translate all plan
validation failures to `PROTOCOL_INVALID` before source I/O.

- [ ] **Step 5: Run contract, temporal, and provider suites**

```bash
uv run --frozen python -m pytest packages/contract/tests packages/timeseries/tests packages/local_files/tests packages/sqlite/tests packages/postgres/tests/test_temporal_lowering.py packages/maybe_sheet/tests/test_temporal_recording.py -q
git diff --check
```

- [ ] **Step 6: Update A8/A9/A13 and commit**

```bash
git add packages/contract/src/open_table_connector/contract/fingerprints.py packages/contract/tests/test_receipts.py packages/timeseries/src/open_table_connector/timeseries/evaluator.py packages/timeseries/src/open_table_connector/timeseries/plan.py packages/timeseries/tests/fixtures.py packages/timeseries/tests/test_evaluator_bounds.py packages/timeseries/tests/test_evaluator_gapfill.py packages/timeseries/tests/test_plan_wire.py packages/local_files/src/open_table_connector/local_files/temporal_csv.py packages/local_files/src/open_table_connector/local_files/temporal_json.py packages/local_files/src/open_table_connector/local_files/temporal_excel.py packages/sqlite/src/open_table_connector/sqlite/temporal.py packages/postgres/src/open_table_connector/postgres/temporal.py packages/maybe_sheet/src/open_table_connector/maybe_sheet/temporal.py docs/reviews/2026-08-31-critical-review-remediation.md
git commit -m "fix: make temporal evidence deterministic and truthful"
```

## Plan Verification

After all seven tasks:

```bash
uv run --frozen python -m pytest packages/contract/tests packages/timeseries/tests packages/sqlite/tests packages/postgres/tests packages/local_files/tests packages/google_sheets/tests packages/feishu_bitable/tests packages/maybe_sheet/tests packages/cli/tests specification/conformance/timeseries specification/conformance/universal -q
git diff --check
```

Run the PostgreSQL live lifecycle separately with a configured
`OTC_TEST_POSTGRES_DSN`. Expected: all non-live tests pass; live evidence is
recorded only when the configured test actually runs; every A finding has a
terminal or explicitly open ledger disposition.
