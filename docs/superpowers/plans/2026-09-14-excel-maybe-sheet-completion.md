# OTC Excel and Maybe Sheet Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete OTC shared sessions, verified local XLSX artifacts, general Excel editing and Maybe Sheet sheet-mode operations with CLI and release evidence.

**Architecture:** Neutral sessions buffer changes; provider adapters preflight and commit them. SDK resource views adapt neutral results to existing result conventions. Local artifact verification is independent of serialization; Maybe dispatch uses a tested canonical CLI contract.

**Tech Stack:** Python 3.11–3.14, uv workspace, pytest, Ruff/mypy, openpyxl, Pillow, bounded ZIP/XML parsing and existing process transport.

**Spec:** [Excel and Maybe Sheet completion](../specs/2026-09-14-excel-maybe-sheet-completion-design.md). Read it and its normative physical-profile references before execution.

## Global constraints

- Only OTC components; no FinClaw repository edits, financial semantics, replay or cutover.
- Google implementation and live acceptance are deferred; preserve existing behavior with regressions.
- Retain `client.workbook.create(uri)`, callable workbook/worksheet access, `write`, `verify`, and default-client `otc.workbook`; use `file://` local URIs.
- No public plan/expectation classes or new receipt family. `.with_results()` captures one immutable result without I/O.
- Buffer all new session mutations until write; closing never implicitly saves. Legacy Table/Formula contracts remain unchanged.
- Providers do not import SDK. Keep optional installation independent.
- Default atomicity; explicit partial opt-in; unknown effects freeze mutation and never trigger automatic retry.
- Literal profile is `literal-artifact/1.0`; no calcPr, formulas, calculation chain or external links. Generic quarantine is OTC-owned mechanics; application retention bookkeeping is not.
- Every advertised capability needs positive dispatch and negative preflight evidence. Required baseline gaps block the applicable provider gate.
- Do not declare completion or bypass failing checks because the foundation was merged.

## Baseline, files and sequence

Baseline inspected: `538338ee9289bbe24a1bef41bd996208b2896f52`. The new helpers and workbook methods already exist; inspect them and add failing behavioral regressions rather than assuming missing imports are the expected failure. Reuse passing implementation where it satisfies the spec.

Tasks 1–3 own neutral contracts/session state and SDK resource adaptation. Tasks 4–5 own `local_files/artifact/` parsing, verification and publishing. Task 6 owns general editing and preservation, including splitting the existing `spreadsheet_workbook.py` behind compatible entry points. Task 7 owns Maybe commands. Task 8 owns CLI/discovery/install coverage. Task 9 owns release evidence.

Dependency chain: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9.
Local artifact acceptance needs 1–5 and Task 8's local installation/discovery checks, which may execute before the Maybe portion. Maybe credentials never block local artifact acceptance. Each gate remains separately reported.

Before implementation inspect repository instructions, status and remote changes; use an isolated `codex/` checkout without resetting newer work. This document authorizes no source execution by itself.

```sh
uv sync --all-packages --group dev
uv run --all-packages --frozen python -m pytest -q
```

Record baseline failures and compare the same command/environment on the candidate. Test examples below are mandatory acceptance seeds, not the whole corpus. New named fixtures are created by their task. Every task follows regression -> failing run -> implementation -> passing focused checks -> review -> scoped commit.

## Task 1: Repair foundation contracts and define the internal provider seam

**Files:** modify `packages/spreadsheets/src/open_table_connector/spreadsheets/model.py`,
`capabilities.py`, `__init__.py`; create `_operations.py`, `_protocols.py`, `_limits.py`
in that directory; modify `packages/sdk/src/open_table_connector/sdk/formula.py`;
extend `packages/spreadsheets/tests/test_model.py` and SDK Formula tests.

**Produces:** internal `Change(operation_id, capability, target_key, arguments)`;
`WorkbookState` holding stable keys, ordered sheets, pending changes and limits;
`ProviderBinding` holding canonical URI, revision and per-operation capabilities;
`ProviderResult` with value/outcome/commit/verification/receipts/error;
`SpreadsheetProvider.bind(target)`, `preflight(binding, changes)`,
`commit(binding, changes, *, allow_partial, expected_revision, idempotency_key)`
and `observe(binding, selector)`. Neutral result enums serialize to existing SDK
enum values. No provider result imports SDK.

- [ ] Add regression tests before changing code:

```python
@pytest.mark.parametrize("address", ["B1:A2", "A2:B1", "XFE1", "A1048577"])
def test_reject_invalid_excel_rectangle(address):
    with pytest.raises(ValueError):
        RangeRef(address)

@pytest.mark.parametrize("size", [float("nan"), float("inf"), True, -1])
def test_reject_invalid_font_size(size):
    with pytest.raises(ValueError):
        CellStyle(font_size=size)
```

- [ ] Run `uv run --all-packages python -m pytest packages/spreadsheets/tests/test_model.py -q`; confirm the new cases expose current defects.
- [ ] Validate both rectangle axes and Excel bounds, strict scalar types, immutable nested values, MIME/hash/size inputs and closed internal wire records. Restore the Formula expression-size check currently stranded after `_coerce_expression`'s return; test both typed and shorthand requests above the bound limit before dispatch.
- [ ] Introduce the internal protocols above; all public method arguments remain ordinary values. Preserve existing public models compatibly while removing their use as mandatory caller inputs. Add the operation identities for the full catalog, without advertising unimplemented adapter support.
- [ ] Test closed-wire rejection, serialization, finite limits, hash validation and import independence. Run spreadsheet and SDK Formula tests plus Ruff on these files; commit `fix: harden spreadsheet contracts and define provider seam`.

## Task 2: Implement the shared session state machine and captured results

**Files:** create `packages/spreadsheets/src/open_table_connector/spreadsheets/_session.py`,
`_manifest.py`; create `packages/sdk/src/open_table_connector/sdk/spreadsheet_results.py`;
create `packages/spreadsheets/tests/test_session.py` and
`packages/sdk/tests/test_spreadsheet_results.py`.

**Consumes:** Task 1 provider seam. **Produces:** internal session states
`new`, `clean`, `dirty`, `writing`, `unknown`, `partial`, `sealed`, `closed`;
`queue(change)`, `preview(selector)`, `write(...)`, `reconcile()`, `close()`.
`capture(result)` in SDK returns an immutable operation summary exposing
`.with_results()`, accepting planned results for queued edits and raising OTCError
for failed/partial/unknown execution results. Creation/opening results contain
resource views with immutable binding evidence.

- [ ] Test queueing and failures with a recording provider fixture implementing Task 1's protocol:

```python
def test_queue_does_not_commit(recording_session, change):
    summary = recording_session.queue(change)
    assert summary.outcome == "planned"
    assert recording_session.provider.commits == []

def test_result_is_not_last_operation_result(success_result, another_result):
    first = capture(success_result)
    capture(another_result)
    assert first.with_results() is success_result
```

- [ ] Run those two new test files and confirm absent implementation failures.
- [ ] Implement bounded overlays, ordered changes, dirty-read labeling, immutable snapshots and normalized SHA-256 manifest hashing. Internal normalization excludes timestamps/paths and includes resolved cells/layout/images. Track base identity, expected revision and pending changes separately; never mutate captured receipts.
- [ ] Successful general writes transition to clean and permit more edits; strict artifact writes transition to sealed. Dry-run leaves pending edits intact. Unknown/partial commits reject further changes; reconciliation performs observations only and never retries writes. Close discards pending state without saving.
- [ ] Test every transition, including concurrent write rejection, post-commit verification failure, receipt serialization without cycles and unavailable overlay previews. Run focused tests and commit `feat: add bounded spreadsheet sessions and captured results`.

## Task 3: Expose the slim SDK API and queue formulas in unsaved workbooks

**Files:** create `packages/sdk/src/open_table_connector/sdk/workbook.py`,
`worksheet.py`, `spreadsheet_range.py`, `spreadsheet_formula.py`; modify `client.py`,
`registry.py`, `connector.py`, `sdk/__init__.py`, `otc/__init__.py`; create
`packages/sdk/tests/test_workbook.py`, `test_spreadsheet_formula.py`.

**Produces:** callable `WorkbookAccess` at `client.workbook` and `otc.workbook`,
with `create(uri=None, *, provider=None, container=None, title=None, profile=None,
limits=None, failure_directory=None)` and bounded `list(...)`.
Workbook provides callable `worksheet` access with `.create(name, ...)`,
`write(dry_run=False, allow_partial=False, expected_revision=None, idempotency_key=None)`,
`verify(expected=None)`, `reconcile()` and `close()`.
Worksheet exposes `range(address)`, `formulas()`, `images`, `config(**properties)`;
range exposes `read`, `write(values)`, `style(**properties)`, `format(**properties)`,
`merge` and the remaining catalog verbs in Task 6.

- [ ] Add this recording-provider integration test:

```python
def test_unsaved_formula_and_values_share_one_commit(client, recording_provider):
    book = client.workbook.create("file:///tmp/new.xlsx")
    sheet = book.worksheet.create("Model")
    sheet.range("A1:B1").write([[10, 20]])
    sheet.formulas().set("C1", "=A1+B1")
    assert recording_provider.commits == []
    book.write()
    assert len(recording_provider.commits) == 1
    assert recording_provider.commits[0].formula("Model", "C1") == "=A1+B1"
```

- [ ] Run new SDK tests to establish failure; implement resource accessors on Task 2 sessions. Route file paths/URIs through shared canonicalization, not filename-only provider guessing. Import the optional package lazily and return unsupported capability if missing.
- [ ] Normalize Formula strings using bound capability dialects before queueing. Reuse pure Formula validation/copy-fill helpers; do not invoke immediate Formula mutation on unsaved files. Literal-artifact sessions reject every formula operation. Recalculation requires a clean session and provider capability.
- [ ] Test target alias equivalence, nonexistent open, duplicate worksheet names, mixed Maybe Base rejection, string/type/dialect equivalence, closed client affinity and legacy Formula/Table return compatibility. Commit `feat: expose workbook resource sessions and formula shorthand`.

## Task 4: Implement bounded raw and decoded XLSX verification first

**Files:** create `packages/local_files/src/open_table_connector/local_files/artifact/`
with `__init__.py`, `archive.py`, `xml_checks.py`, `decoded.py`, `verify.py`,
`errors.py`; create `packages/local_files/tests/test_artifact_verify.py`,
`test_artifact_corruption.py` and `artifact_fixtures.py`.

**Consumes:** internal manifest/limits from Tasks 1–2.
**Produces:** `verify_snapshot(data: bytes, expected: Mapping, limits) -> ProviderResult`
with `xlsx-physical` evidence; `read_bounded_snapshot(path, limits) -> bytes`.
Expected state comes from caller intent, never the decoded workbook itself.

- [ ] Build a minimal independently authored XLSX fixture plus a helper that
  rewrites an archive member. Test corruption before building a writer:

```python
@pytest.mark.parametrize("damage", ["formula", "duplicate_member", "duplicate_cell",
    "merged_hidden_value", "external_drawing", "missing_image", "calcPr"])
def test_corruption_fails_closed(literal_fixture, damage):
    data, expected = literal_fixture
    result = verify_snapshot(corrupt(data, damage), expected, default_limits())
    assert result.verification == "failed"
```

- [ ] Run verifier tests to establish failure. Implement limits before parsing;
  stream decompression with actual-byte counters and disallow DTD/entities.
  Enforce the prior artifact spec section 13.3's exact part/content-type/relationship allowlist,
  raw cell bounds/types/shared-string references, merges, no calcPr/formulas,
  and drawing/media coverage. Use one immutable input snapshot for all checks.
- [ ] Implement independent openpyxl decoded comparisons after raw validation:
  strings including empty strings, `@`, sheet order, declared styles, all declared
  print/view properties and image anchors/EMU dimensions. Compare stored image
  bytes rather than re-encoded image data. Normalize only specified equivalents.
- [ ] Test every corruption class in the prior artifact spec section 12, including changed
  layout/borders, forged ZIP sizes and decompression limits, orphan media,
  duplicate relationship IDs and unsupported parts. Close resources on failure.
  Commit `feat: verify literal XLSX artifacts independently`.

## Task 5: Implement create-exclusive literal artifacts and failure retention

**Files:** create `artifact/write.py`, `artifact/publish.py`, `artifact/layout.py`,
`artifact/images.py` beside Task 4 files; modify local-files provider registration,
manifest and `pyproject.toml`; add `test_artifact_write.py`,
`test_artifact_lifecycle.py`, `test_artifact_receipts.py`.

**Consumes:** Task 2 session intent and Task 4 verifier.
**Produces:** local provider commit of a literal artifact; existing Receipt.details
contain expected manifest, content/semantic hashes, limits and resolved names.

- [ ] Add end-to-end acceptance against Task 3 API:

```python
def test_literal_artifact_is_exclusive(client, tmp_path):
    path = tmp_path / "report.xlsx"
    book = client.workbook.create(path.as_uri(), profile="literal-artifact/1.0")
    sheet = book.worksheet.create("Report")
    sheet.range("A1").write([["=SUM(B1:B3)"]])
    assert not path.exists()
    book.write()
    assert book.verify().with_results().verification.value == "passed"
    before = path.read_bytes()
    other = client.workbook.create(path.as_uri(), profile="literal-artifact/1.0")
    other.worksheet.create("Report")
    with pytest.raises(OTCError):
        other.write()
    assert path.read_bytes() == before
```

- [ ] Run red; build workbook/layout/images in an owned sibling temporary file,
  verify its closed bytes with Task 4, then publish via no-clobber link or an
  equivalently tested primitive. Capture image bytes/hash at queueing so a changed
  source file cannot alter the saved artifact. Preserve caller-supplied resolved naming and native
  dimensions exactly; do not infer application layout.
- [ ] Implement `failure_directory` quarantine with exclusive unique evidence
  filenames and bounded content hashes. On post-commit failure retain the destination
  and honest commit state. No exception may delete pre-existing paths or another
  writer's output. Test race winners/losers, symlinks, injected save/verify/publish/
  cleanup/retention failures and resource closure.
- [ ] Test literal/profile limits, deterministic manifest hashes, complete receipt
  round-trips and generic declared-layout corpus. Declare Pillow and provider-local
  dependencies; enable profile discovery only with full write/verify availability.
  Commit `feat: create verified literal workbook artifacts exclusively`.

## Task 6: Implement general editing semantics and local preservation

**Files:** create `packages/spreadsheets/src/open_table_connector/spreadsheets/_grid.py`,
`_styles.py`, `_objects.py`; create `packages/local_files/src/open_table_connector/local_files/spreadsheet.py`,
`spreadsheet_preservation.py`; modify `excel_formula.py` to reuse local coordination;
create `packages/local_files/tests/test_spreadsheet_edit.py`,
`test_spreadsheet_preservation.py` and neutral grid semantic tests.

**Produces:** full resource operation argument schemas and local adapter implementations
for sheet lifecycle, finite cells, dimensions, merges, sorting, format/style,
formulas, native tables, names, hyperlinks, notes, validations, conditional formats,
filters, image operations, supported charts, pivot inspection/preservation and
protection/visibility. Unsupported native pivot creation must remain a recorded
gap if no engine can perform it without loss; do not call the catalog complete.

- [ ] Add edit/save/reopen preservation tests:

```python
def test_edit_preserves_unrelated_content(client, workbook_with_objects):
    path, before = workbook_with_objects
    book = client.workbook(path.as_uri())
    book.worksheet("Inputs").range("B2").write([[42]])
    assert path.read_bytes() == before.bytes
    book.write()
    assert inspect_objects(path) == before.objects
```

- [ ] Run red; implement strict matrix typing, blanks, dates/epochs/serial-60
  rejection for date objects, numeric precision, patch/reset rules, tagged native
  dimensions and structural reference policy. Date serial 60 may remain a raw
  numeric value but cannot silently become a nonexistent date. Sort uses explicit
  keys/header exclusion/blank placement and stable ties. Validate before mutation.
- [ ] Preflight existing XLSX parts against the preservation matrix. Use bounded
  staging plus source-revision checks and the same file lock as immediate Formula
  writes. Declare cooperating-writer enforcement accurately; atomic replace alone
  is not compare-and-set against external applications.
- [ ] Implement safe transformations of supported references; reject cases the
  engine cannot preserve. Test hidden/very-hidden sheets, named/table references,
  images, charts/pivots and unsupported archive objects during unrelated edits.
  Run existing Excel Table/Formula/temporal tests. Commit `feat: edit existing XLSX workbooks with preservation checks`.

## Task 7: Implement Maybe sheet-mode sessions and conformance

**Files:** create `packages/maybe_sheet/src/open_table_connector/maybe_sheet/spreadsheet.py`,
`spreadsheet_commands.py`; modify `connector.py`, `plugin.py`, `pyproject.toml`;
create `packages/maybe_sheet/tests/test_spreadsheet.py`,
`test_spreadsheet_recording.py`, `test_spreadsheet_live.py`.

**Consumes:** Tasks 1–3 and 6; existing credential-safe ProcessClient.
**Produces:** Maybe provider with bounded workbook/worksheet binding, tested
canonical command mapping and per-operation support matrix.

- [ ] Add injected-process tests proving preflight rejects unsafe atomic batches:

```python
def test_nonatomic_remote_write_requires_opt_in(maybe_book, process):
    maybe_book.worksheet("Report").range("A1").write([["x"]])
    maybe_book.worksheet("Report").range("A1").style(bold=True)
    with pytest.raises(OTCError):
        maybe_book.write()
    assert process.mutation_calls == []
    maybe_book.write(allow_partial=True)
    assert len(process.mutation_calls) == 2
```

- [ ] Run red; pin/negotiate the tested canonical CLI contract. Map workbook,
  worksheet, range, row/column, style, formula and image operations to actual
  `mbs` commands, using `--target` and validated JSON envelopes. Never invent a
  range-format command. Normalize format through supported resource-local style.
- [ ] Bind only sheet-mode gids; preserve Base worksheets and stable identities.
  Translate provider argument units, notes' single-cell restriction, native chart/
  pivot subsets, reference changes and recalculation scopes explicitly. Every catalog
  operation needs either verified implementation or an explicit matrix gap.
- [ ] Test timeout after each dispatch, partial results, created URI retention,
  idempotency conflicts and stale bindings. Add opt-in live tests on disposable
  authorized documents; missing credentials leave live gate pending. Commit
  `feat: add Maybe sheet-mode spreadsheet sessions`.

## Task 8: CLI, discovery, builds and two-provider operation matrix

**Files:** create `packages/cli/src/open_table_connector/cli/spreadsheet_commands.py`;
modify `commands.py`, provider registrations, both provider READMEs,
`docs/package-boundaries.md`, workspace/dependency manifests and `uv.lock`;
extend `scripts/check_package_metadata.py`, `check_package_independence.py`,
`check_package_boundaries.py`, `smoke_wheels.py` as needed; create
`specification/conformance/spreadsheets/test_operations.py`,
`test_capabilities.py`, `test_optional_install.py`; create
`docs/user-guide/spreadsheet-operations.md`.

**Produces:** `otc spreadsheet` command tree over the same SDK; versioned
operation command-file decoder with no public plan class; per-provider matrix.

- [ ] Parameterize baseline tests over `excel` and `maybe_sheet`:

```python
@pytest.mark.parametrize("provider", ["excel", "maybe_sheet"])
def test_capabilities_match_dispatch(provider, provider_fixture):
    book = provider_fixture(provider)
    for operation in book.capabilities:
        assert provider_fixture.has_positive_case(provider, operation)
```

- [ ] Run red; expose resource commands. Standalone mutations explicitly commit
  once; multi-command workbook write supports dry-run and partial opt-in. Decode
  operations through existing schemas and report existing result JSON envelopes.
- [ ] Verify ordinary core imports without the new extension and each optional
  provider, standard file URI routing through SDK/CLI, clean wheel artifact/image
  round-trips and no upward dependencies. Fix falsely present-tense docs. Matrix
  rows cover every catalog operation, with named tests/evidence or stated gaps.
- [ ] Run provider-independence, package scripts and CLI/conformance tests; commit
  `feat: expose spreadsheet commands and capability conformance`.

## Task 9: Audit two-provider release evidence

**Files:** modify `docs/spreadsheet-readiness.md`, `docs/user-guide/spreadsheet-operations.md`, this plan and the new spec's implementation-status note; create `docs/research/spreadsheet-completion/acceptance.md`.

**Consumes:** Tasks 1–8 and their test/operation matrices. **Produces:** separately auditable shared, local-artifact, general-Excel, Maybe-recorded, Maybe-live and distribution gates.

- [ ] Create one evidence row for each R1–R16 requirement and every Excel/Maybe catalog operation, separating read/create/update/delete. Record named test, revision, environment and pass/fail/deferred status; missing required baseline rows block the provider gate.
- [ ] Add a capability-matrix regression to `specification/conformance/spreadsheets/test_capabilities.py` requiring a positive dispatch fixture for every advertised operation. Confirm it fails on a deliberately advertised unsupported operation, then remove that unsupported advertisement.
- [ ] Run `uv run --all-packages --frozen python -m pytest -q` on Python 3.11–3.14, changed-file Ruff/type checks and the repository package jobs. Run `uv run --frozen python scripts/check_package_metadata.py` and `uv run --frozen python scripts/check_package_independence.py`. Record exact commands and results; investigate differences from baseline.
- [ ] Execute authorized disposable Maybe live fixtures from Task 7. Missing credentials leave that gate pending, not passed. Keep existing Google tests as compatibility checks only.
- [ ] Check local collision/cleanup/corruption fixtures and independent wheel image round-trips; ensure no raw verifier expectation is derived from the workbook under test.
- [ ] Publish supported/unsupported/deferred rows, preservation limits and cooperating-writer limitations. Link the separately owned FinClaw spec only as downstream work; do not claim cutover readiness.
- [ ] Run `git diff --check`, review evidence and mark only proven checklist items complete. Commit `docs: record Excel and Maybe completion evidence` with the exact evidence/doc paths; leave unmet gates open.

## Additional acceptance seeds and fixture ownership

Task 1 creates strict-wire cases in `packages/spreadsheets/tests/test_model.py` and tests Formula typed/shorthand byte bounds. Task 2 creates its recording-provider fixture in `packages/spreadsheets/tests/conftest.py`; the fixture exposes committed calls and injectable partial/unknown outcomes. SDK fixtures adapt that same neutral contract without importing SDK from providers.

```python
# Task 3, packages/sdk/tests/test_workbook.py
# client is the existing configured SDK fixture; tmp_path is supplied by pytest.
def test_reopened_artifact_needs_independent_expectation(client, tmp_path):
    uri = (tmp_path / "report.xlsx").as_uri()
    book = client.workbook.create(uri, profile="literal-artifact/1.0")
    book.worksheet.create("Report").range("A1").write([["=literal"]])
    book.write()
    reopened = client.workbook(uri, profile="literal-artifact/1.0")
    with pytest.raises(OTCError):
        reopened.verify()
```

Task 3 exposes optional strict-profile binding consistently. The explicit independent expectation form is `verify(expected=manifest)`.

Task 4 creates the independent fixture and archive mutation helper in `packages/local_files/tests/artifact_fixtures.py`; never generate the only corruption oracle with the writer being tested. Task 5 injects cleanup and quarantine failures independently. Task 6 creates object-preservation fixtures before refactoring storage. Task 7 creates isolated process fixtures and command/version evidence before implementing any unsupported command.

## Spec coverage

| Spec sections | Tasks |
| --- | --- |
| 1–2 Scope, neutral dependencies and existing foundation | 1, 8, 9 |
| 3–4 Slim API, captured results, lifecycle and Formula | 1–3, 6–7 |
| 5 General editing and preservation | 6–8 |
| 6 R1–R16, independent verification and quarantine | 1–5, 8–9 |
| 7 Maybe sheet-mode and mixed Base preservation | 7–9 |
| 8 CLI, packaging and release gates | 8–9 |
