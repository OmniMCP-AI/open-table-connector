# Critical Review Specification and Conformance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make OTC v1 semantics, schemas, fixtures, provider evidence, and compatibility attestations independently reproducible instead of deriving expected behavior from the implementation under test.

**Architecture:** A pinned remediation ledger tracks every review finding. Normative prose and closed schemas define v1 behavior; vendored input/output fixtures become the conformance oracle. Compatibility evidence is computed from declared file manifests and exact commits, with distinct tiers for unit, recording-stub, configured-live, and cross-implementation results.

**Tech Stack:** Python 3.11–3.14, frozen dataclasses, JSON Schema 2020-12, PyArrow 14–19, Polars 1.x, pytest 9, JSON fixture manifests, SHA-256, and uv workspace commands.

**Spec:** `docs/superpowers/specs/2026-08-31-critical-review-remediation-design.md`

**Owned findings:** T1, T3, T4, C1, C2, C3, C4, C5, C6, C7, C8, C9, C10, and C11, plus normative/schema prerequisites for A2, A8, A9, B5, B6, E3, E5, E6, E11, and F2.

## Global Constraints

- Preserve version 1 wire compatibility unless the existing wire cannot express a safe result; incompatible changes use a separately versioned schema and capability.
- `count` is row count equivalent to SQL `COUNT(*)` and requires `value_field` to be null.
- Gap-fill keeps the generated domain on the left side of its join; normative semantics require strictly increasing, round-trippable bucket labels.
- Expected conformance outputs are vendored data and are never computed by the implementation under test during a conformance run.
- Existing v1 hash inputs are not silently redefined. A new canonical format requires empirical incompatibility evidence, fixtures, and a versioned identity.
- Compatibility records pin exact commits and a scoped manifest of normative files; tags do not replace commit pins.
- Provider evidence tiers are `unit`, `recording_stub`, `configured_live`, and `cross_implementation`.
- Work in red-green-refactor slices. Every task ends with focused tests, the owning suite, `git diff --check`, a ledger update, and one Conventional Commit.
- Run `uv sync --all-packages --group dev` before executing test commands in a fresh checkout.

---

## File Map

- `docs/reviews/2026-08-31-critical-review-remediation.md` — pinned evidence ledger and task/commit traceability.
- `specification/semantics/portable-temporal-plan-v1.md` — normative operation, ordering, duplicate, bucket, fill, COUNT, and null semantics.
- `packages/timeseries/src/open_table_connector/timeseries/plan.py` — Python enforcement of semantic invariants expressible at construction time.
- `specification/schemas/portable-temporal-plan-v1.schema.json` — matching structural constraints for v1 plans.
- `specification/fixtures/timeseries/v1/cases.json` — fixture inventory, source table, plan file, expected file, and logical comparison rules.
- `specification/fixtures/timeseries/v1/source/ticks.json` — canonical typed input rows.
- `specification/fixtures/timeseries/v1/expected/*.json` — pinned ordered columns, Arrow type strings, and expected rows.
- `packages/conformance/src/open_table_connector/conformance/timeseries.py` — fixture loader and logical Arrow comparisons.
- `specification/conformance/timeseries/conftest.py` — provider construction only; no expected-value computation or imports from package tests.
- `specification/schemas/connector-process-envelope-v1.schema.json` — closed v1 request/response envelope union.
- `specification/schemas/connector-process-payloads-v1.schema.json` — operation-specific request and response payload definitions.
- `specification/schemas/connector-error-v1.schema.json` — shared closed wire error vocabulary.
- `specification/schemas/shared-definitions-v1.schema.json` — one source for repeated receipt and hash definitions.
- `specification/conformance/cross-framework/local-files.json` — executable JSON manifest replacing the unread YAML declaration.
- `scripts/verify_compatibility.py` — deterministic scoped manifest and evidence verifier.
- `specification/compatibility/ots-otc-timeseries-v1.yaml` — generated values whose byte inputs are documented and checked.

### Task 1: Create the evidence ledger and publish normative v1 semantics

**Files:**
- Create: `docs/reviews/2026-08-31-critical-review-remediation.md`
- Create: `specification/semantics/portable-temporal-plan-v1.md`
- Modify: `packages/timeseries/src/open_table_connector/timeseries/plan.py:257-269`
- Modify: `packages/timeseries/tests/test_plan_wire.py:82-86`
- Modify: `specification/schemas/portable-temporal-plan-v1.schema.json`
- Test: `packages/timeseries/tests/test_plan_wire.py`
- Test: `specification/conformance/timeseries/test_schema_parity.py`

**Interfaces:**
- Consumes: review identifiers `T1`–`T5`, `A1`–`A15`, `B1`–`B6`, `C1`–`C11`, `D1`–`D7`, `E1`–`E12`, `F1`–`F4`, and `G1`–`G9`.
- Produces: ledger columns `Finding | Evidence | Priority | Plan task | Verification | Disposition | Commit`; normative `count == COUNT(*)` semantics; Python and schema rejection of `count` with a non-null `value_field`.

- [ ] **Step 1: Write the failing COUNT contract tests**

Add these cases to `test_plan_wire.py`:

```python
def test_count_is_row_count_and_rejects_value_field() -> None:
    assert AggregateMeasure("rows", AggregateFunction.COUNT, None).to_wire() == {
        "output_field": "rows",
        "function": "count",
        "value_field": None,
    }
    with pytest.raises(ValueError, match="count requires value_field to be null"):
        AggregateMeasure("non_null_price", AggregateFunction.COUNT, "price")
```

Add a schema parity case that changes the vendored COUNT measure to
`"value_field": "price"` and expects `jsonschema.ValidationError`.

- [ ] **Step 2: Run the focused tests and confirm the red phase**

Run:

```bash
uv run --frozen python -m pytest packages/timeseries/tests/test_plan_wire.py::test_count_is_row_count_and_rejects_value_field specification/conformance/timeseries/test_schema_parity.py -q
```

Expected: the constructor accepts the non-null COUNT field or the schema accepts the mutated document.

- [ ] **Step 3: Implement the semantic rule in Python and JSON Schema**

Change `AggregateMeasure.__post_init__` to enforce both branches explicitly:

```python
if self.function is AggregateFunction.COUNT:
    if self.value_field is not None:
        raise ValueError("count requires value_field to be null")
elif self.value_field is None:
    raise ValueError(f"{self.function.value} requires value_field")
```

In the aggregate-measure schema, use `if/then/else`: COUNT requires
`value_field` to be `null`; all other functions require it to be a non-empty
string.

- [ ] **Step 4: Write the normative semantics document and ledger**

The semantics document must state half-open range rules, projection and output
ordering, duplicate-policy tie breaking, fixed/calendar bucket labeling,
COUNT, null behavior for every aggregate, gap-fill domain construction, LOCF,
and positional linear interpolation. Use RFC 2119 terms only for requirements.

Seed every source-review identifier into the ledger. Record A2 as
`superseded` with the corrected COUNT wording; record the YAML “duplicate
keys” statement as `invalid`; record hash/version/performance/provider-limit
claims as `hypothesis` until their dedicated tasks run.

- [ ] **Step 5: Run contract and schema tests**

```bash
uv run --frozen python -m pytest packages/timeseries/tests/test_plan_wire.py specification/conformance/timeseries/test_schema_parity.py -q
git diff --check
```

Expected: both files pass and the ledger contains every review identifier.

- [ ] **Step 6: Commit**

```bash
git add docs/reviews/2026-08-31-critical-review-remediation.md specification/semantics/portable-temporal-plan-v1.md packages/timeseries/src/open_table_connector/timeseries/plan.py packages/timeseries/tests/test_plan_wire.py specification/schemas/portable-temporal-plan-v1.schema.json specification/conformance/timeseries/test_schema_parity.py
git commit -m "docs: define portable temporal v1 semantics"
```

### Task 2: Replace the self-referential oracle with pinned golden outputs

**Files:**
- Create: `specification/fixtures/timeseries/v1/cases.json`
- Create: `specification/fixtures/timeseries/v1/source/ticks.json`
- Create: `specification/fixtures/timeseries/v1/expected/scan-range.json`
- Create: `specification/fixtures/timeseries/v1/expected/latest.json`
- Create: `specification/fixtures/timeseries/v1/expected/as-of.json`
- Create: `specification/fixtures/timeseries/v1/expected/bucket-aggregate.json`
- Create: `specification/fixtures/timeseries/v1/expected/gap-fill.json`
- Modify: `packages/conformance/src/open_table_connector/conformance/timeseries.py`
- Modify: `packages/conformance/src/open_table_connector/conformance/__init__.py`
- Modify: `specification/conformance/timeseries/conftest.py:31-54`
- Modify: `specification/conformance/timeseries/test_semantic_matrix.py`
- Test: `packages/conformance/tests/test_reference_reader.py`
- Test: `specification/conformance/timeseries/test_semantic_matrix.py`

**Interfaces:**
- Produces: `load_temporal_cases(root: Path) -> tuple[TemporalSemanticCase, ...]`; `TemporalSemanticCase` gains `case_id: str`; expected tables are reconstructed from `schema` and `rows` in fixture JSON.
- Consumes: existing `TemporalExecutionRequest`, `plan_from_wire()`, `descriptor_from_wire()`, and provider executors.

- [ ] **Step 1: Write failing fixture-loader tests**

```python
def test_vendored_cases_supply_expected_rows_without_running_an_executor() -> None:
    cases = load_temporal_cases(ROOT / "specification/fixtures/timeseries/v1")
    assert [case.case_id for case in cases] == [
        "scan-range", "latest", "as-of", "bucket-aggregate", "gap-fill"
    ]
    assert cases[0].expected.to_pylist() == [
        {"ts": datetime(2026, 8, 29, tzinfo=UTC), "symbol": "AAPL", "price": 100.0}
    ]
```

Monkeypatch `PolarsTemporalExecutor.execute` to raise in this test so any
attempt to compute expected values fails immediately.

- [ ] **Step 2: Run the loader test and confirm the red phase**

```bash
uv run --frozen python -m pytest packages/conformance/tests/test_reference_reader.py::test_vendored_cases_supply_expected_rows_without_running_an_executor -q
```

Expected: import or attribute failure because `load_temporal_cases` does not exist.

- [ ] **Step 3: Add the manifest, canonical input, and expected documents**

Use this closed top-level manifest shape:

```json
{
  "schema_version": "otc.temporal-conformance-cases/v1",
  "source": "source/ticks.json",
  "cases": [
    {"id": "scan-range", "plan": "scan-range.json", "expected": "expected/scan-range.json"}
  ]
}
```

Each expected file contains ordered `schema` entries
`{"name": "price", "type": "double", "nullable": true}` and JSON rows in
wire form. Generate the initial values once with an independent manual
calculation script outside the test, inspect them against the normative prose,
then commit only the reviewed JSON.

- [ ] **Step 4: Implement the loader and decouple conformance fixtures**

`load_temporal_cases()` reads only files below the supplied root, rejects
unknown/missing keys, reconstructs Arrow fields from the closed supported type
map, and returns cases in manifest order. Remove imports from
`packages.*.tests`; provider fixtures may import production constructors and
shared conformance data only.

- [ ] **Step 5: Run semantic conformance without the reference oracle**

```bash
uv run --frozen python -m pytest packages/conformance/tests/test_reference_reader.py specification/conformance/timeseries/test_semantic_matrix.py -q
git diff --check
```

Expected: every provider is compared to vendored expected data and no import in
`specification/conformance/timeseries` matches `packages\..*\.tests`.

- [ ] **Step 6: Commit**

```bash
git add specification/fixtures/timeseries/v1/cases.json specification/fixtures/timeseries/v1/source/ticks.json specification/fixtures/timeseries/v1/expected/scan-range.json specification/fixtures/timeseries/v1/expected/latest.json specification/fixtures/timeseries/v1/expected/as-of.json specification/fixtures/timeseries/v1/expected/bucket-aggregate.json specification/fixtures/timeseries/v1/expected/gap-fill.json packages/conformance/src/open_table_connector/conformance/timeseries.py packages/conformance/src/open_table_connector/conformance/__init__.py packages/conformance/tests/test_reference_reader.py specification/conformance/timeseries/conftest.py specification/conformance/timeseries/test_semantic_matrix.py
git commit -m "test: pin temporal conformance outputs"
```

### Task 3: Close schema/Python gaps and share repeated definitions

**Files:**
- Create: `specification/schemas/shared-definitions-v1.schema.json`
- Create: `specification/fixtures/timeseries/v1/invalid/*.json`
- Modify: `specification/schemas/temporal-table-descriptor-v1.schema.json`
- Modify: `specification/schemas/portable-temporal-plan-v1.schema.json`
- Modify: `specification/schemas/temporal-receipt-v1.schema.json`
- Modify: `specification/schemas/managed-*-receipt-v1.schema.json`
- Modify: `specification/schemas/capability-manifest-v1.schema.json`
- Modify: `specification/schemas/connector-error-v1.schema.json`
- Modify: `packages/contract/src/open_table_connector/contract/errors.py`
- Modify: `packages/contract/tests/test_errors.py`
- Modify: `packages/timeseries/src/open_table_connector/timeseries/descriptor.py`
- Modify: `packages/timeseries/src/open_table_connector/timeseries/receipts.py`
- Modify: `packages/timeseries/src/open_table_connector/timeseries/storage.py`
- Modify: `packages/process/src/open_table_connector/process/server.py`
- Modify: `packages/process/src/open_table_connector/process/timeseries.py`
- Modify: `packages/process/tests/test_server.py`
- Test: `specification/conformance/timeseries/test_schema_parity.py`

**Interfaces:**
- Produces: shared `$defs` for `sha256`, `rfc3339Utc`, `resourceBounds`, and `neutralReceipt`; all public wire documents carry a `schema_version` const; one 14-value `ConnectorErrorCode` vocabulary used by neutral, temporal, and process errors.
- Consumes: Python `from_wire()` methods as the executable parity oracle for valid/invalid fixture agreement, not as the semantic expected-output oracle.

- [ ] **Step 1: Add a table-driven failing parity test**

```python
@pytest.mark.parametrize("fixture_name", sorted(INVALID_ROOT.glob("*.json")), ids=lambda p: p.stem)
def test_invalid_fixture_is_rejected_by_schema_and_python(fixture_name: Path) -> None:
    case = json.loads(fixture_name.read_text())
    with pytest.raises(jsonschema.ValidationError):
        validator(case["schema"]).validate(case["document"])
    with pytest.raises((TypeError, ValueError)):
        PYTHON_DECODERS[case["kind"]](case["document"])
```

Include invalid calendar dates, reversed ranges, returned rows above bounds,
unknown timezone, missing ingestion field for `replace-latest`, missing schema
version, bool-as-int values, and every unknown error code. Add a table-driven
test proving the schema enum equals `{item.value for item in ConnectorErrorCode}`.

- [ ] **Step 2: Run parity tests and record which side accepts each fixture**

```bash
uv run --frozen python -m pytest specification/conformance/timeseries/test_schema_parity.py -q
```

Expected: at least one schema accepts a document rejected by Python.

- [ ] **Step 3: Extract shared definitions and tighten schemas/code together**

Use file-relative `$ref` values such as
`"shared-definitions-v1.schema.json#/$defs/sha256"`. Add `schema_version` to
descriptor, capability-manifest, and connector-error wire models and schemas.
Expand `ConnectorErrorCode` to the closed union of the existing neutral values
and `protocol_invalid`, `protocol_version_unsupported`,
`resource_limit_exceeded`, `snapshot_unavailable`, `idempotency_conflict`, and
`visibility_incomplete`. Make `TemporalErrorCode` a compatibility alias of
that enum. Change `ProcessError` to normalize `str | ConnectorErrorCode`
through `ConnectorErrorCode(code)` at construction, migrate its call sites to
enum constants, and serialize `.value`; do not keep parallel string-only
vocabularies.
Relax the temporal receipt invariant so gap-fill may return more rows than it
examined while retaining independent `examined_* <= bounds` and
`returned_* <= bounds` checks.

- [ ] **Step 4: Run the complete schema suite**

```bash
uv run --frozen python -m pytest packages/contract/tests/test_errors.py packages/timeseries/tests/test_schema_fixtures.py packages/timeseries/tests/test_receipt_schema_fixtures.py packages/process/tests/test_server.py specification/conformance/timeseries/test_schema_parity.py -q
git diff --check
```

Expected: every valid fixture passes both validators and every invalid fixture
fails both validators.

- [ ] **Step 5: Commit**

```bash
git add specification/schemas/shared-definitions-v1.schema.json specification/schemas/temporal-table-descriptor-v1.schema.json specification/schemas/portable-temporal-plan-v1.schema.json specification/schemas/temporal-receipt-v1.schema.json specification/schemas/managed-*-receipt-v1.schema.json specification/schemas/capability-manifest-v1.schema.json specification/schemas/connector-error-v1.schema.json specification/fixtures/timeseries/v1/invalid packages/contract/src/open_table_connector/contract/errors.py packages/contract/tests/test_errors.py packages/timeseries/src/open_table_connector/timeseries/descriptor.py packages/timeseries/src/open_table_connector/timeseries/receipts.py packages/timeseries/src/open_table_connector/timeseries/storage.py packages/process/src/open_table_connector/process/server.py packages/process/src/open_table_connector/process/timeseries.py packages/process/tests/test_server.py specification/conformance/timeseries/test_schema_parity.py
git commit -m "fix: align temporal schemas and codecs"
```

### Task 4: Specify closed process request and response payloads

**Files:**
- Create: `specification/schemas/connector-process-payloads-v1.schema.json`
- Modify: `specification/schemas/connector-process-envelope-v1.schema.json`
- Create: `specification/fixtures/process/v1/*.json`
- Modify: `packages/process/tests/test_envelope.py`
- Modify: `specification/conformance/timeseries/test_process_e2e.py`
- Test: `specification/conformance/timeseries/test_schema_parity.py`

**Interfaces:**
- Produces: schema definitions `requestPayload`, `responsePayload`, and one request payload per operation; v1 wire fields remain unchanged.
- Consumes: `ProcessOperation` values and current response payload shape `{"ok": bool, "result"|"error": ...}`.

- [ ] **Step 1: Add failing schema fixtures for request/response ambiguity**

Add fixtures proving that an execute request containing `ok`, an execute
request missing `portable_plan`, a success response missing `result`, and an
error response with an unknown field are rejected.

```python
def test_execute_request_cannot_be_reclassified_by_an_ok_key(process_validator) -> None:
    wire = valid_execute_request()
    wire["payload"]["ok"] = True
    with pytest.raises(jsonschema.ValidationError):
        process_validator.validate(wire)
```

- [ ] **Step 2: Run schema and envelope tests to confirm the red phase**

```bash
uv run --frozen python -m pytest packages/process/tests/test_envelope.py specification/conformance/timeseries/test_schema_parity.py -q
```

Expected: the open payload schema accepts at least one invalid fixture.

- [ ] **Step 3: Define the closed payload union**

Keep the envelope fields unchanged. The payload schema uses a `oneOf` whose
request branches are selected by the envelope `operation` through envelope
`if/then` clauses; the response branch is selected by required boolean `ok`.
All result/error objects use closed definitions or explicitly named extension
objects. Do not add `direction` to v1.

- [ ] **Step 4: Validate fixtures and e2e frames**

```bash
uv run --frozen python -m pytest packages/process/tests/test_envelope.py specification/conformance/timeseries/test_schema_parity.py specification/conformance/timeseries/test_process_e2e.py -q
git diff --check
```

- [ ] **Step 5: Commit**

```bash
git add specification/schemas/connector-process-envelope-v1.schema.json specification/schemas/connector-process-payloads-v1.schema.json specification/fixtures/process packages/process/tests/test_envelope.py specification/conformance/timeseries/test_process_e2e.py specification/conformance/timeseries/test_schema_parity.py
git commit -m "docs: close process protocol v1 payloads"
```

### Task 5: Unify capability identity and evidence tiers

**Files:**
- Modify: `packages/contract/src/open_table_connector/contract/identity.py`
- Modify: `packages/contract/tests/test_identity.py`
- Modify: `packages/timeseries/src/open_table_connector/timeseries/capabilities.py`
- Modify: `packages/timeseries/src/open_table_connector/timeseries/plan.py`
- Modify: `packages/process/src/open_table_connector/process/timeseries.py`
- Modify: `specification/schemas/capability-manifest-v1.schema.json`
- Create: `specification/schemas/provider-evidence-v1.schema.json`
- Create: `specification/evidence/providers/*.json`
- Modify: `specification/conformance/timeseries/test_semantic_matrix.py`

**Interfaces:**
- Produces: `CapabilityIdentity.parse(value: str) -> CapabilityIdentity`; `CapabilityIdentity.to_reference() -> str`; evidence tier enum strings.
- Consumes: wire reference format `capability_id/capability_version`, for example `timeseries.scan.range/1.0`.

- [ ] **Step 1: Write failing identity and evidence tests**

```python
def test_capability_reference_has_one_round_trip() -> None:
    identity = CapabilityIdentity.parse("timeseries.scan.range/1.0")
    assert identity == CapabilityIdentity("timeseries.scan.range", "1.0")
    assert identity.to_reference() == "timeseries.scan.range/1.0"

def test_recording_stub_cannot_claim_configured_live(load_provider_evidence) -> None:
    evidence = load_provider_evidence("postgres")
    assert evidence["tier"] == "recording_stub"
    assert evidence["live_run"] is None
```

- [ ] **Step 2: Run focused tests and confirm the red phase**

```bash
uv run --frozen python -m pytest packages/contract/tests/test_identity.py specification/conformance/timeseries/test_semantic_matrix.py -q
```

- [ ] **Step 3: Implement the one identity conversion rule**

`parse()` splits at the final `/`, validates `major.minor`, and rejects empty
or ambiguous references. Capability constants become `CapabilityIdentity`
objects; wire models call `to_reference()` at their boundary. Process provider
maps use `capability_id` keys and compare versions with an explicit same-major,
requested-minor-at-most-supported rule.

- [ ] **Step 4: Add closed provider evidence documents**

Each evidence file contains `schema_version`, `provider`, `tier`, `commit`,
`commands`, `artifacts`, and nullable `live_run`. Label Postgres and
MaybeSheet `recording_stub` until their configured-live jobs produce an
artifact. CSV/JSON/JSONL/SQLite/Excel may use `unit` until a stronger tier is
actually run.

- [ ] **Step 5: Run identity, process, and schema suites**

```bash
uv run --frozen python -m pytest packages/contract/tests/test_identity.py packages/timeseries/tests/test_plan_wire.py packages/process/tests/test_server.py specification/conformance/timeseries -q
git diff --check
```

- [ ] **Step 6: Commit**

```bash
git add packages/contract/src/open_table_connector/contract/identity.py packages/contract/tests/test_identity.py packages/timeseries/src/open_table_connector/timeseries/capabilities.py packages/timeseries/src/open_table_connector/timeseries/plan.py packages/process/src/open_table_connector/process/timeseries.py specification/schemas/capability-manifest-v1.schema.json specification/schemas/provider-evidence-v1.schema.json specification/evidence/providers specification/conformance/timeseries/test_semantic_matrix.py
git commit -m "feat: unify capability and evidence identities"
```

### Task 6: Make the cross-framework suite manifest-driven

**Files:**
- Create: `specification/conformance/cross-framework/local-files.json`
- Delete: `specification/conformance/cross-framework/local-files.yaml`
- Modify: `specification/conformance/cross-framework/test_local_files.py`
- Create: `specification/conformance/cross-framework/expected/decimal-null-order.json`
- Test: `specification/conformance/cross-framework/test_local_files.py`

**Interfaces:**
- Produces: executable manifest cases with `id`, `source`, `expected`, `comparisons`, and expected connector/mode metadata.
- Consumes: `LocalFilesConnector.read_arrow()` and `read_polars()` only; no implementation-generated expected file.

- [ ] **Step 1: Write a failing manifest-consumption test**

```python
def test_every_manifest_case_is_executed() -> None:
    manifest = load_manifest(ROOT / "local-files.json")
    assert {case.id for case in collected_cases()} == {
        item["id"] for item in manifest["fixtures"]
    }
```

The expected decimal document records Arrow decimal precision/scale, nulls,
row order, coordinate convention, source revision, and content fingerprint.

- [ ] **Step 2: Run the test and confirm the manifest is currently ignored**

```bash
uv run --frozen python -m pytest specification/conformance/cross-framework/test_local_files.py -q
```

Expected: missing loader/collector failure.

- [ ] **Step 3: Implement a closed JSON manifest loader and parameterized cases**

Reject unknown keys, missing expected artifacts, duplicate IDs, and comparison
names outside the closed supported set. Assert typed decimal metadata rather
than comparing decimal-looking strings.

- [ ] **Step 4: Run cross-framework and universal local-file tests**

```bash
uv run --frozen python -m pytest specification/conformance/cross-framework specification/conformance/universal/test_table_connectors.py -q
git diff --check
```

- [ ] **Step 5: Commit**

```bash
git add specification/conformance/cross-framework/local-files.json specification/conformance/cross-framework/local-files.yaml specification/conformance/cross-framework/test_local_files.py specification/conformance/cross-framework/expected/decimal-null-order.json
git commit -m "test: drive cross-framework checks from manifest"
```

### Task 7: Define and verify compatibility hash inputs

**Files:**
- Create: `scripts/verify_compatibility.py`
- Create: `specification/compatibility/ots-otc-timeseries-v1.files`
- Modify: `specification/compatibility/ots-otc-timeseries-v1.yaml`
- Create: `specification/semantics/hash-identities-v1.md`
- Create: `specification/conformance/timeseries/test_compatibility_manifest.py`
- Create: `specification/conformance/timeseries/test_hash_interop.py`
- Modify: `docs/reviews/2026-08-31-critical-review-remediation.md`

**Interfaces:**
- Produces: `compute_manifest_hash(root: Path, entries: Sequence[str]) -> str`; `verify_compatibility(root: Path) -> list[str]`, returning error messages and an empty list on success; an exact byte-level definition of existing v1 plan, descriptor, corpus, and provider evidence hashes.
- Consumes: lexical UTF-8 path list in `.files`, raw bytes of each named file, exact surface commits, and provider evidence JSON.

- [ ] **Step 1: Write failing verifier tests**

```python
def test_manifest_hash_changes_only_for_declared_files(tmp_path: Path) -> None:
    root = copy_fixture_tree(tmp_path)
    before = compute_manifest_hash(root, ("schemas/a.json", "fixtures/b.json"))
    (root / "README.md").write_text("unrelated")
    assert compute_manifest_hash(root, ("schemas/a.json", "fixtures/b.json")) == before
    (root / "schemas/a.json").write_text("changed")
    assert compute_manifest_hash(root, ("schemas/a.json", "fixtures/b.json")) != before
```

Add a test that corrupts one provider evidence hash and expects a precise
`provider postgres evidence_hash mismatch` error.

- [ ] **Step 2: Run verifier tests and confirm the red phase**

```bash
uv run --frozen python -m pytest specification/conformance/timeseries/test_compatibility_manifest.py -q
```

- [ ] **Step 3: Implement deterministic hashing**

Hash each entry as `len(path):path + len(bytes):bytes` in lexical path order,
then prefix the lower-case digest with `sha256:`. Reject absolute paths,
duplicates, missing files, symlinks, and paths outside the repository.
Document the exact provider evidence bytes and keep commit SHA fields separate
from content hashes.

- [ ] **Step 4: Add empirical hash interoperability fixtures**

`test_hash_interop.py` writes logical schemas/tables with the supported local
PyArrow versions in CI and compares the stored results. It records differences
without changing v1 identity. The cross-language assertion is skipped only
when the checked-in Arrow Rust artifact is absent, with reason
`cross-implementation artifact not supplied`; the ledger remains `hypothesis`
until that artifact is committed.

Write `hash-identities-v1.md` from the audited implementations: name every
input field, encoding, JSON separator/sort/Unicode option, logical path order,
Arrow IPC operation, length prefix, and `sha256:` formatting rule. Clearly
label runtime-specific bytes as v1 compatibility facts, not portable ideals.
If empirical fixtures prove an incompatibility, keep v1 unchanged and open a
separately versioned canonical-JSON/logical-schema v2 design in the ledger;
do not repair v1 by changing its digest inputs in place.

- [ ] **Step 5: Verify the real compatibility record**

```bash
uv run --frozen python scripts/verify_compatibility.py
uv run --frozen python -m pytest specification/conformance/timeseries/test_compatibility_manifest.py specification/conformance/timeseries/test_hash_interop.py -q
git diff --check
```

Expected: verifier exits zero; unrelated files are outside the scoped manifest.

- [ ] **Step 6: Update the ledger and commit**

Record whether hash instability was reproduced. If not reproduced, mark the
original assertion `invalid` for the tested matrix and retain a separate
cross-language hypothesis.

```bash
git add scripts/verify_compatibility.py specification/compatibility/ots-otc-timeseries-v1.files specification/compatibility/ots-otc-timeseries-v1.yaml specification/semantics/hash-identities-v1.md specification/conformance/timeseries/test_compatibility_manifest.py specification/conformance/timeseries/test_hash_interop.py docs/reviews/2026-08-31-critical-review-remediation.md
git commit -m "test: verify compatibility evidence hashes"
```

## Plan Verification

After all seven tasks:

```bash
uv run --frozen python -m pytest packages/contract/tests packages/timeseries/tests packages/process/tests packages/conformance/tests specification/conformance/timeseries specification/conformance/cross-framework -q
uv run --frozen python scripts/verify_compatibility.py
git diff --check
```

Expected: all selected tests pass, the verifier exits zero, expected temporal
rows come only from vendored fixtures, and every T1/T4/C finding has a ledger
disposition and verification command.
