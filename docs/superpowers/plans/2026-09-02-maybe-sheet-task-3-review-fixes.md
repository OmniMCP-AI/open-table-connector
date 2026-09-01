# Maybe Sheet Task 3 Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the Maybe Sheet grid Formula extension against the five blocking review findings while preserving disabled capabilities and ordinary table behavior.

**Architecture:** Keep formula operations on canonical `mbs` commands and require a cached successful exact worksheet binding before any grid operation. Add closed-envelope error translation and explicit terminal idempotency handling at the process boundary, strengthen range/response validation, and make copy-fill translation aware of quoted sheet names, structured references, and external references.

**Tech Stack:** Python 3.11+, pytest, Ruff, the existing `open_table_connector.formulas` models, and the Maybe `ProcessClient` recording fakes.

**Spec:** `docs/superpowers/specs/2026-09-01-mode-aware-formula-extension-design.md`

## Global Constraints

- Formula operations use only canonical `mbs` commands; Base/cross-mode commands remain unavailable to formula dispatch.
- Static Maybe capabilities and modes remain unchanged; field formulas remain disabled.
- Ordinary Maybe table reads and writes remain unchanged.
- Provider errors never echo raw formula text, credentials, URLs, or arbitrary diagnostics.
- A dispatched mutation error, parse failure, or limit failure is terminal `UNKNOWN` and its idempotency key cannot be reused.
- Every regression is written first, observed failing, then implemented minimally and re-run.

### Task 1: Add failing regressions for validation, binding, envelopes, receipts, and copy-fill

**Files:**
- Modify: `packages/maybe_sheet/tests/test_grid_formula.py`
- Modify: `packages/maybe_sheet/tests/test_connector.py`

**Interfaces:**
- Exercise `MaybeSheetGridFormulaExtension` through its public bind/read/value/set/recalculate methods.
- Use recording process fakes to assert no process I/O for invalid or unbound requests and exact canonical argv for valid requests.

- [x] **Step 1: Add RED tests for all review findings**

Add tests that prove:

1. range recalculation rejects malformed ranges and ranges over `max_cells` before process I/O; non-range recalculation with a supplied range is rejected before process I/O;
2. recalculation with no value evidence returns outer `FormulaVerificationState.UNAVAILABLE`, not `PASSED`;
3. canonical `ok: false` envelopes map stale revision, invalid formula, provider rejection, resource, and protocol errors to typed Formula errors; a dispatched failed set returns `UNKNOWN`, and reusing its idempotency key makes no second process call;
4. read, value-read, recalculate, and set require a previously successful exact binding, with missing/ambiguous targets rejected before formula process I/O and no fabricated capabilities;
5. `formula_cells` must be a list of valid in-rectangle A1 addresses, malformed or out-of-range values fail closed, and over-returned matrix rows/columns fail closed;
6. value receipts omit `observation_sha256` when no formula observation was actually made;
7. all formula operations use `mbs formula`/`mbs excel-worksheet` only, with no `db-table`, Base, or ad hoc cross-mode command; and
8. copy-fill preserves literal text, structured references, external references, and quoted worksheet references while translating relative A1 references.

- [x] **Step 2: Run the focused regressions and verify RED**

Run:

```bash
uv run --frozen python -m pytest packages/maybe_sheet/tests/test_grid_formula.py packages/maybe_sheet/tests/test_connector.py -q
```

Expected: the newly added review regressions fail against the current implementation.

### Task 2: Implement validation, binding, envelope, and receipt fixes

**Files:**
- Modify: `packages/maybe_sheet/src/open_table_connector/maybe_sheet/grid_formula.py`
- Modify: `packages/formulas/src/open_table_connector/formulas/operations.py` only if recalculation limits must be carried by the request type

**Interfaces:**
- `_require_binding(target)` returns the exact cached binding details or a typed pre-dispatch rejection path.
- `_call(...)` accepts canonical success and failure envelopes and maps failures to a private typed provider error.
- `_validate_recalculation_request(...)` validates scope shape and effective cell limits before constructing argv.

- [x] **Step 1: Implement binding and scope validation minimally**

Require exact binding for all grid operations before formula process I/O. Validate RANGE with `A1Rectangle.parse`, ensure it is unbound and within the effective `max_cells`; reject any range on WORKSHEET/WORKBOOK. Remove the unknown-target full-capability fallback. Preserve the successful binding’s exact worksheet ID and provider details.

- [x] **Step 2: Implement canonical `ok:false` translation and terminal mutation behavior**

Parse safe provider error codes/status fields into `STALE_REVISION`, `INVALID_FORMULA`, `RESOURCE_LIMIT`, `PROTOCOL_FAILURE`, or `EXECUTION_FAILED` as appropriate. Keep safe details allowlisted. For a dispatched `formula.set`, convert provider error/parse/limit failure to terminal `UNKNOWN`, mark the ledger unknown, and prevent reuse; retain pre-dispatch timeout retry behavior.

- [x] **Step 3: Correct recalculation verification and value receipts**

Set `RecalculationObservation.verification` and the outer result verification consistently with the presence of actual value evidence. Do not synthesize an empty formula observation hash for value-only reads; pass `None` unless a real formula observation was obtained.

- [x] **Step 4: Fail closed on formula-cell addresses and matrix over-return**

Validate every declared `formula_cells` address as a single unbound A1 cell inside the requested rectangle, reject malformed/duplicate/out-of-range addresses, and reject any matrix row/column over-return before parsing.

- [x] **Step 5: Run focused tests and verify GREEN**

Run:

```bash
uv run --frozen python -m pytest packages/maybe_sheet/tests/test_grid_formula.py packages/maybe_sheet/tests/test_connector.py packages/maybe_sheet/tests/test_cli_adapter.py -q
```

Expected: all focused Maybe tests pass.

### Task 3: Strengthen copy-fill translation and preserve disabled paths

**Files:**
- Modify: `packages/maybe_sheet/src/open_table_connector/maybe_sheet/grid_formula.py`
- Modify: `packages/maybe_sheet/tests/test_grid_formula.py`
- Modify: `packages/maybe_sheet/tests/test_connector.py` only for explicit ordinary-table/base command assertions

**Interfaces:**
- `_translate_formula(expression, column_delta, row_delta)` translates only standalone A1 references while preserving quoted strings, structured references, external workbook references, and qualified worksheet references.
- Existing connector table paths remain untouched and continue using `db-table` only for ordinary Base table reads.

- [x] **Step 1: Add any remaining failing copy-fill and command-separation tests**
- [x] **Step 2: Implement the smallest parser/guard changes**
- [x] **Step 3: Run focused Maybe formula, connector, and CLI tests**

### Task 4: Report, full verification, and commit

**Files:**
- Modify: `.superpowers/sdd/2026-09-01-grid-formula-providers/task-3-report.md`

- [x] **Step 1: Run all requested verification**

```bash
uv run --frozen python -m pytest packages/maybe_sheet/tests/test_grid_formula.py packages/maybe_sheet/tests/test_connector.py packages/maybe_sheet/tests/test_cli_adapter.py packages/cli/tests/test_commands.py -q
uv run --frozen ruff check packages/maybe_sheet packages/formulas packages/cli
git diff --check
```

- [x] **Step 2: Update the Task 3 report**

Record RED/GREEN evidence, changed files, final commit ID, and any remaining concerns, including that static formula capabilities and ordinary table writes remain disabled/unchanged.

- [x] **Step 3: Commit with a Conventional Commit**

```bash
git add packages/maybe_sheet packages/formulas packages/cli .superpowers/sdd/2026-09-01-grid-formula-providers/task-3-report.md docs/superpowers/plans/2026-09-02-maybe-sheet-task-3-review-fixes.md
git commit -m "fix: harden Maybe Sheet formula review findings"
```
