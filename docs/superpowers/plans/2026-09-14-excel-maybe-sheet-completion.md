# OTC Excel and Maybe Sheet Completion Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans; complete the checkboxes task-by-task.

**Goal:** Complete Excel/Maybe workbook operations by consolidating existing code.
**Architecture:** One SDK facade, one private shared session, existing provider storage, one independent XLSX verifier.
**Tech stack:** Python 3.11–3.14, uv, pytest, existing SDK/Formula/process contracts, openpyxl and Pillow.
**Spec:** [Excel and Maybe completion](../specs/2026-09-14-excel-maybe-sheet-completion-design.md). Its behavior and physical-profile requirements are normative; this plan replaces the previous file decomposition.

## Execution rules

- OTC only. Google implementation is deferred; preserve its current behavior.
- Retain slim resource calls, file URIs, existing results and legacy Table/Formula contracts.
- Reuse current code/tests. Delete replaced wrappers; no public plan classes, second result hierarchy, per-resource module tree or generic grid engine.
- Preserve independent verification, bounded resources, partial/unknown evidence and all R1–R16 gates. A shorter implementation does not weaken acceptance.
- Inspect instructions/status; execute in an isolated `codex/` checkout. Baseline code is `538338e`; never reset newer work.
- Before changing behavior, add a failing behavioral test; after implementation run focused regressions and make a scoped commit. The examples below are acceptance seeds, not the entire required corpus.

Baseline: `uv sync --all-packages --group dev`, then `uv run --all-packages --frozen python -m pytest -q`. Record actual environment/results. Compare identical commands before labeling failures pre-existing.

## 1. Consolidate the workbook session and result path

**Files:** modify `packages/sdk/src/open_table_connector/sdk/{workbook,result,formula}.py`; extend existing `packages/spreadsheets/src/open_table_connector/spreadsheets/{_operations,_protocols,_limits,model}.py`; create only `_session.py` there. Update provider bindings/imports and existing workbook/model/Formula tests; add `packages/spreadsheets/tests/test_session.py`.

**Seam:** existing `bind`, `preflight`, `commit`, `observe` protocol; private session queues existing Change values. SDK resource views adapt neutral results once. `write`, `verify(expected=None)`, `close`, `reconcile` and `.with_results()` retain the spec's behavior.

- [ ] Test nested input freezing, A1/finite limits, Formula byte bounds, canonical aliases, mixed-mode rejection and optional imports. Add lifecycle cases for queue/no-dispatch, captured results, dry-run, closed/sealed sessions, concurrent writes and unresolved effects.

```python
# Recording fixture is defined in test_session.py and implements the existing protocol.
def test_queued_changes_do_not_commit(recording_book, provider):
    first = recording_book.worksheet.create("Report").range("A1").write([["x"]])
    captured = first.with_results()
    assert provider.commits == []
    recording_book.write()
    assert len(provider.commits) == 1
    assert first.with_results() is captured
```

- [ ] Run `uv run --all-packages python -m pytest packages/spreadsheets/tests packages/sdk/tests -q` and confirm the new behavior fails before the fix.
- [ ] Consolidate current local/remote Excel/Maybe wrappers through the shared session; use existing result adaptation in `sdk/result.py`. Freeze records rather than introducing new result classes. Keep expectation normalization as private helpers in `_session.py`.
- [ ] Queue explicit formulas with values; infer the bound dialect and reuse Formula validation. Literal profile rejects formulas. Keep current creation defaults; editable creation selects `general/1.0` explicitly.
- [ ] Make state behavior private and minimal: track pending changes, closure/sealing and unresolved commit result; reject unsafe retries. Observe-only reconciliation either establishes known state or requires rebind. Remove provider SDK imports for this path, and remove replaced wrappers without changing deferred Google behavior.
- [ ] Run focused suites plus legacy Formula tests, inspect dependency direction and commit `refactor: consolidate workbook sessions and results`.

## 2. Complete local artifacts behind one independent verifier

**Files:** keep writer/staging in `packages/local_files/src/open_table_connector/local_files/spreadsheet_workbook.py`; create `spreadsheet_verify.py` beside it. Extend `packages/local_files/tests/test_spreadsheet_workbook.py`; create `test_spreadsheet_verify.py` for independent archive fixtures/corruption. Reuse existing limits, image/style helpers and result types.

**Seam:** `verify_snapshot(data: bytes, expected: Mapping, limits) -> Mapping` in the verifier consumes trusted intent and returns neutral evidence. It must not import/call the writer. Session-held intent supports immediate verify; reopened strict verification needs explicit retained expectation. No separate artifact package, publish/layout/image modules or public expectation class.

- [ ] Add an independently authored literal XLSX fixture and corruption helper in the verifier test module. Parameterize every R1–R16 case plus formulas/calcPr, duplicate ZIP/relationship/cell identities, shared strings, hidden merge values, changed styles/layout, missing/changed/orphan media, DTD, external/escaping targets and decompression bounds.

```python
@pytest.mark.parametrize("damage", ["formula", "calcPr", "duplicate_member",
                                    "hidden_merged_value", "orphan_media"])
def test_corruption_is_rejected(literal_fixture, corrupt):
    data, expected, limits = literal_fixture
    with pytest.raises(ConnectorError):
        verify_snapshot(corrupt(data, damage), expected, limits)
```

The fixture/helper live in `test_spreadsheet_verify.py`; import existing ConnectorError and the new verifier there. The full corruption list is the spec's physical-profile contract.
- [ ] Run `uv run --all-packages python -m pytest packages/local_files/tests/test_spreadsheet_verify.py -q` to establish failure, then extract and harden existing raw/decoded checks. Check one immutable bounded snapshot with actual expansion counters, exact allowed parts/relationships and complete intent comparison; never repair it.
- [ ] Keep deterministic manifest helpers in the shared session and byte hashing in the verifier. Capture original image bytes at queueing. Verify all declared text/layout/merge/image properties using the spec's exact units and normalization.
- [ ] In the current writer, validate -> stage -> close -> independently verify -> no-clobber publish. Test creator races, existing files/directories/symlinks, and injected save/verify/publish/cleanup/retention failures. Preserve committed destinations and report honest unknown/partial state.
- [ ] Add generic `failure_directory` support using existing errors/receipt details. Keep primary/retention failures distinct and diagnostic bytes unverified. Reuse the same staging helpers for general replacement where guarantees match.
- [ ] Run all local-files tests and SDK workbook regressions; commit `feat: complete verified local workbook artifacts`.

## 3. Complete Excel and Maybe operations using existing adapters

**Files:** extend local `spreadsheet_workbook.py` and existing `excel_formula.py` coordination; add at most `packages/maybe_sheet/src/open_table_connector/maybe_sheet/spreadsheet.py` for batch compilation. Reuse `connector.py`, `cli_adapter.py`, Formula helpers and process transport. Extend local workbook tests and Maybe connector tests; add `packages/maybe_sheet/tests/test_spreadsheet.py` for recorded/live cases.

**Seam:** both adapters implement the existing neutral provider protocol from Task 1; resource verbs remain in the SDK facade. No new styles/grid/objects framework and no duplicate process client.

- [ ] Add edit/save/reopen cases for the spec's required baseline: sheets, ranges, dimensions, style/format, merges, stable sorting, formulas and image placement/readback. Cover blank/empty strings, epoch/serial-60, precision, patch/reset, naming and reference changes.
- [ ] Add preservation fixtures containing unrelated formulas, names/tables, charts/pivots, images, hidden/protected sheets and unsupported parts. Supported objects survive exactly; unsafe operations fail before save. Reuse legacy Formula file coordination and reject stale source revisions.
- [ ] Inspect/pin the actual Maybe CLI contract and record command evidence. Test canonical targets, sheet-mode gids and mixed Base preservation before dispatch; use existing command construction/JSON validation instead of inventing commands.

```python
def test_maybe_rejects_unsafe_atomic_batch(maybe_book, process):
    sheet = maybe_book.worksheet("Report")
    sheet.range("A1").write([["x"]])
    sheet.range("A1").style(bold=True)
    with pytest.raises(OTCError):
        maybe_book.write()
    assert process.mutation_calls == []
```

The fixture models a CLI version without an atomic value-plus-style batch. Add explicit partial-opt-in success and timeout-after-each-dispatch cases; retain created IDs and every known effect.
- [ ] Run `uv run --all-packages python -m pytest packages/local_files/tests packages/maybe_sheet/tests -q` to establish gaps. Implement only operations supported by tested storage/CLI behavior; document unsupported catalog rows separately from required baseline failures.
- [ ] Reuse native units, Formula translation and observation. Default non-atomic batches reject before dispatch; no fallback after unknown mutation. General verification must not claim XLSX physical verification for remote state.
- [ ] Run preservation and recorded transport suites. Run opt-in authorized disposable Maybe live cases when credentials exist; otherwise leave live gate pending. Commit `feat: complete Excel and Maybe workbook operations`.

## 4. Finish CLI/discovery, remove duplication and record evidence

**Files:** extend `packages/cli/src/open_table_connector/cli/commands.py`, with one `spreadsheet_commands.py` if needed; provider manifests/READMEs and package metadata; add `specification/conformance/spreadsheets/test_operations.py`; update `docs/spreadsheet-readiness.md` and create `docs/user-guide/spreadsheet-operations.md`.

**Seam:** CLI uses SDK operations and existing result JSON. Its versioned command file decodes to existing Change arguments, not a second schema/model hierarchy. One readiness matrix links all tests and gates; avoid a parallel evidence-document tree.

- [ ] Add conformance cases for each advertised Excel/Maybe operation and unsupported preflight; standalone CLI mutations commit once, batches support dry-run/partial opt-in. Keep Google legacy regressions only.
- [ ] Implement routing/discovery and update provider dependency manifests/lockfile. Verify core-only imports, each optional wheel independently, file URI equivalence and image artifact round-trips. Enable capabilities only with positive dispatch evidence.
- [ ] Delete replaced wrappers, helpers and obsolete tests that merely mirror them. Keep independent corruption/preservation tests. Review resulting imports and public signatures for accidental compatibility changes.
- [ ] Run full supported-Python tests, repository lint/type/package jobs, CLI and wheel tests. Record exact revision, command, environment and pass/fail/skip counts in the readiness document. Compare failures against the baseline rather than waive them.
- [ ] Publish R1–R16 and per-operation implemented/unsupported/deferred rows. Report separate local artifact, general Excel, Maybe recorded/live and distribution gates; required baseline gaps block the applicable release. Never claim FinClaw cutover.
- [ ] Run `git diff --check`; mark only proven checks complete; commit `feat: expose and validate consolidated spreadsheet operations`.

## Coverage and order

1 -> 2 -> 3 -> 4. Task 4's local packaging checks may run after Task 2 so Maybe
credentials do not block local artifact acceptance. Spec sections 2–4 map to Task 1;
physical R1–R16 to 2/4; editing/Maybe to 3/4; distribution and KISS deletion review
to 4. This replaces the nine-task plan without dropping its acceptance obligations.
