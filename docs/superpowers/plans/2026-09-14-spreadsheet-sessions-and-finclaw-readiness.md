# Spreadsheet Sessions and FinClaw Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the simple workbook resource API with verified local artifacts for FinClaw and independently tested general editing for Excel, Maybe sheet-mode and Google Sheets.

**Architecture:** SDK resource views queue changes in a bounded workbook session. Neutral internal records and provider protocols describe those changes; provider adapters commit them only on `book.write()`. The local literal-artifact profile adds independent ZIP/XML and decoded verification, while FinClaw retains semantic verification and publication authority.

**Tech Stack:** Python 3.11–3.14, uv workspace, existing OTC contract/Formula/result machinery, openpyxl, Pillow, bounded XML/ZIP readers, injected Maybe process and Google HTTP transports, pytest and Ruff.

**Specs:**
- [Unified spreadsheet operations](../specs/2026-09-13-unified-spreadsheet-operations-design.md), especially section 13.
- [FinClaw artifact readiness](../specs/2026-09-14-finclaw-excel-artifact-readiness-design.md), including critical-review closure requirements.

## Global constraints

- Use `client.workbook.create(uri)` / `client.workbook(uri)`, `book.worksheet.create(name)`, `book.write()` and `book.verify()`; default-client `otc.workbook` mirrors them.
- No public WorkbookPlan, SheetPlan, WorkbookExpectation or new artifact receipt classes. Internal records are not public imports.
- New workbook session edits are buffered on all providers. Legacy Table and `client.formulas(...)` contracts remain unchanged.
- Local targets use `file:///...xlsx`; aliases share canonical identity and coordination.
- Reuse existing OperationResult/Receipt/OTCError conventions. `.with_results()` observes its own captured result without I/O.
- Provider implementations do not import SDK. Optional integrations do not break ordinary Table/Formula imports.
- Artifact profile is `literal-artifact/1.0`; write and verify identities are `spreadsheet.workbook.write/1.0` and `spreadsheet.workbook.verify/1.0`.
- Default writes require atomicity. `allow_partial=True` is explicit; partial/unknown effects freeze the session until reconciliation.
- No formula evaluation inside OTC. Unsaved formula changes share the session overlay and storage commit with value changes.
- R1–R16, failure retention and authenticated replay are mandatory for FinClaw cutover.
- A remote capability is enabled only after its adapter passes conformance; unsupported features are documented gaps, not evidence of full coverage.
- Do not force merge failing checks or automatically fall back after uncertain mutations.

## Scope, sequence and gates

This plan replaces the foundation-only execution scope. All tasks below belong
to this delivery; completing Tasks 1–3 is not completion of the request.

Dependency order: `1 -> 2 -> 3 -> 4 -> 5 -> 6`. Task 7 depends on 3 and 6;
Task 8 depends on 3 and 6; Task 9 depends on 5–8. Task 10 depends on 5 and 9's
local install/dispatch checks. Task 11 requires all applicable preceding tasks.
Remote live credentials may block remote release evidence without blocking local
FinClaw adapter development. Report those gates separately.

| Gate | Required tasks | Meaning |
| --- | --- | --- |
| Local artifact | 1–5 plus local packaging in 9 | R1–R16 and physical corruption/cleanup tests pass |
| General editing per provider | 1–3, 6, applicable adapter task, 9 | Required editing baseline passes for that provider |
| FinClaw cutover | Local artifact gate plus 10 | Semantic parity, failed-attempt retention and offline replay pass |
| Release | 11 | Actual capability matrix and exact revision evidence published |

Use an isolated `codex/` feature checkout when execution starts. First inspect
AGENTS.md, current status and remote changes. The planning baseline is local
`664b475`; do not reset newer work to that revision. The referenced FinClaw
worktree is a read-only source baseline until its adapter task is executed in
an appropriately isolated FinClaw checkout.

## Verification setup

Run from the implementation checkout:

```sh
uv sync --all-packages --group dev
uv run --all-packages --frozen python -m pytest -q
```

Use `python -m pytest` to avoid the earlier console-script launcher issue.
Record actual failures and compare with the base revision before labeling them
pre-existing. Do not accept the earlier blanket assertion that all failures were
unrelated. Every task follows red -> minimal implementation -> green -> focused
review -> commit. The examples below are concrete regression tests to include,
not the entirety of the required test cases.

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
  Enforce readiness section 13.3's exact part/content-type/relationship allowlist,
  raw cell bounds/types/shared-string references, merges, no calcPr/formulas,
  and drawing/media coverage. Use one immutable input snapshot for all checks.
- [ ] Implement independent openpyxl decoded comparisons after raw validation:
  strings including empty strings, `@`, sheet order, declared styles, all FinClaw
  print/view properties and image anchors/EMU dimensions. Compare stored image
  bytes rather than re-encoded image data. Normalize only specified equivalents.
- [ ] Test every corruption class in readiness section 12, including changed
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
  source file cannot alter the saved artifact. Preserve FinClaw naming and native
  dimensions exactly; do not infer financial layout.
- [ ] Implement `failure_directory` quarantine with exclusive unique evidence
  filenames and bounded content hashes. On post-commit failure retain the destination
  and honest commit state. No exception may delete pre-existing paths or another
  writer's output. Test race winners/losers, symlinks, injected save/verify/publish/
  cleanup/retention failures and resource closure.
- [ ] Test literal/profile limits, deterministic manifest hashes, complete receipt
  round-trips and FinClaw-specific layout corpus. Declare Pillow and provider-local
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

## Task 8: Implement Google Sheets sessions and conformance

**Files:** create `packages/google_sheets/src/open_table_connector/google_sheets/spreadsheet.py`,
`spreadsheet_requests.py`; modify `connector.py`, `plugin.py`, `manifest.json`,
`pyproject.toml`; add `tests/test_spreadsheet.py`, `test_spreadsheet_recording.py`,
`test_spreadsheet_live.py` in that package.

**Produces:** Google provider using existing SheetsTransport; capability-scoped
batchUpdate compilation and independent get/readback projections.

- [ ] Test the default one-request boundary:

```python
def test_values_and_style_share_batch_update(google_book, transport):
    sheet = google_book.worksheet("Report")
    sheet.range("A1").write([["=literal"]])
    sheet.range("A1").style(bold=True)
    google_book.write()
    assert len(transport.mutation_calls) == 1
    requests = transport.mutation_calls[0].body["requests"]
    assert requests[0]["updateCells"]["rows"][0]["values"][0]["userEnteredValue"] == {"stringValue": "=literal"}
```

- [ ] Run red; verify current official API request schemas before implementing.
  Compile compatible pending operations into ordered batchUpdate requests and
  perform independent field-masked readback. Preserve typed literal strings versus
  formulaValue. Native sheet IDs, copy semantics, dimensions and unit conversions
  stay provider-local. Do not describe observation hashes as CAS tokens.
- [ ] Create-plus-populate and multi-request writes reject atomic policy unless
  an actual single boundary exists; partial opt-in returns known created IDs and
  each effect. Preserve concurrency uncertainty. Leave embedded-image upload/byte
  verification and explicit recalculation absent without a separately validated
  transport. Do not silently use IMAGE formulas or public asset hosting.
- [ ] Cover the required general baseline and native object subsets; record
  protection/table/pivot/print differences explicitly. Test live behavior with
  scoped disposable documents when credentials exist. Commit
  `feat: add Google Sheets spreadsheet sessions`.

## Task 9: CLI, discovery, builds and three-provider operation matrix

**Files:** create `packages/cli/src/open_table_connector/cli/spreadsheet_commands.py`;
modify `commands.py`, provider registrations, all three provider READMEs,
`docs/package-boundaries.md`, workspace/dependency manifests and `uv.lock`;
extend `scripts/check_package_metadata.py`, `check_package_independence.py`,
`check_package_boundaries.py`, `smoke_wheels.py` as needed; create
`specification/conformance/spreadsheets/test_operations.py`,
`test_capabilities.py`, `test_optional_install.py`; create
`docs/user-guide/spreadsheet-operations.md`.

**Produces:** `otc spreadsheet` command tree over the same SDK; versioned
operation command-file decoder with no public plan class; per-provider matrix.

- [ ] Parameterize baseline tests over `excel`, `maybe_sheet`, `google_sheets`:

```python
@pytest.mark.parametrize("provider", ["excel", "maybe_sheet", "google_sheets"])
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

## Task 10: FinClaw adapter, independent semantic parity and replay

**Files in the selected FinClaw checkout:** modify `src/finc/analysis/excel.py`;
create `src/finc/analysis/excel_otc.py`, `excel_legacy.py`; extend
`tests/test_analysis_excel.py`; create `tests/test_analysis_excel_otc.py`; update
`pyproject.toml` and its lockfile with one verified OTC revision.
**Reference:** `/Users/admin/Code/GitHub/finclaw-ng/.worktrees/plotly-static-renderer`.
Do not edit that worktree blindly; inspect its instructions and ownership first.

**Consumes:** local artifact gate and clean install evidence.
**Produces:** existing `render_excel(sections, destination)` and
`verify_excel(path, expected)` signatures, resource-operation translation, versioned
physical-manifest retention separate from unchanged legacy semantic dictionaries.

- [ ] Capture the existing expected-dictionary and hash behavior as oracle fixtures
  before replacing mechanics. Use existing `section()` and chart/ranking fixtures:

```python
def test_otc_matches_existing_semantic_contract(tmp_path):
    sections = [section()]
    legacy = legacy_render(sections, destination=tmp_path / "legacy.xlsx")
    actual = render_excel(sections, destination=tmp_path / "otc.xlsx")
    assert canonical_document(actual) == canonical_document(legacy)
    assert verify_excel(tmp_path / "otc.xlsx", actual)["status"] == "verified"
```

- [ ] Run red; move only workbook mechanics to the OTC adapter. Keep `_text`,
  placements, exact operands, report layout calculations, mapping checks and financial
  semantics in FinClaw. Preserve strict naming and exact/evidence sheet order.
  Pass the attempt quarantine directory to OTC and map errors to existing callers.
- [ ] Store the new physical manifest in versioned attempt metadata, without adding
  fields to the canonical legacy expected dictionary. During replay authenticate
  saved inputs, rederive semantic placements and cross-check the physical manifest.
  Legacy envelopes use the retained legacy verifier; do not rerender or recalculate.
- [ ] Run all existing analysis Excel tests plus multi-section chart/pivot/ranking
  corpus, coordinated workbook+manifest tampering, failure retention and offline
  replay. Inspect representative rendered workbook properties and retained records.
  Remove direct openpyxl usage from the active adapter only after parity passes;
  retain the explicitly versioned legacy verification path. Commit in FinClaw
  `feat: delegate verified Excel artifact mechanics to OTC`.

## Task 11: Audit readiness, run full checks and record release evidence

**Files:** create `docs/spreadsheet-readiness.md`; update the two specs' actual
implementation status and this plan's completed checkboxes; record FinClaw evidence
in its repository without claiming unrun checks.

- [ ] Run the complete OTC suite on the final candidate with Python 3.11–3.14,
  changed-file Ruff/type checks and the repository's package/independence jobs.
  Run FinClaw's required suite on its pinned candidate. Record command, environment,
  revision, passed/failed/skipped counts and fixture hashes.
- [ ] Require a row for each R1–R16 requirement, each FinClaw retention/replay case,
  and each three-provider operation. For every unsupported/deferred row state
  the reason and effect on baseline/full-feature claims. No image or recalculation
  capability is inferred from another provider's tests.
- [ ] Verify that FinClaw physical verification, semantic verification and publication
  form one tested gate; failed/unknown results never acquire published identities.
  Record rollback pin and retained legacy envelope support.
- [ ] Inspect diffs and commit evidence. Do not declare the entire delivery ready
  if any required baseline or live provider gate is missing. No automatic merge
  or deployment is part of this planning request.

## Coverage audit

| Spec requirement group | Tasks |
| --- | --- |
| Slim consistent API, no public plans, direct returns/results | 1–3, 9 |
| Unified buffered lifecycle, revisions, concurrency, partial effects | 2–3, 5–8 |
| Unsaved formulas and legacy Formula/Table compatibility | 1, 3, 6–8 |
| FinClaw R1–R6 | 1, 4–5, 10 |
| R7–R10 lifecycle, hashes and retention | 2, 5, 10 |
| R11–R13 raw/decoded fail-closed verification | 4–5 |
| R14–R16 errors, discovery, installs and compatibility | 1–3, 5, 9, 11 |
| General editing, sort, links, objects, protection, visibility | 6–9 |
| Maybe sheet-mode, mixed Base preservation | 7, 9, 11 |
| Google Sheets batching, native features and honest gaps | 8–9, 11 |
| FinClaw authenticated semantic replay and old artifacts | 10–11 |
| Per-provider matrix and independent release gates | 9, 11 |

Execution has not begun. No checkbox or gate is complete merely because this
plan exists. If provider limitations prevent an intended operation, retain it
as an explicit blocked feature instead of silently narrowing the accepted scope.
