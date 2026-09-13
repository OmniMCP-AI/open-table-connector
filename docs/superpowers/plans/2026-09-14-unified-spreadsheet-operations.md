# Unified Spreadsheet Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver the first shippable slice of the unified spreadsheet architecture: shared provider-neutral contracts, target-aware formula shorthand, and one-call result inspection.

**Architecture:** Add an optional `open-table-connector-spreadsheets` package containing immutable request models and capability identities. Keep provider adapters separate and reuse the existing Formula extension. Extend SDK results and Formula views additively so existing Table and Formula callers remain compatible.

**Tech Stack:** Python 3.11+, dataclasses, `CapabilityIdentity`, existing SDK `OperationResult`, pytest, uv workspace.

**Spec:** `docs/superpowers/specs/2026-09-13-unified-spreadsheet-operations-design.md`

## Global Constraints

- Local Excel targets use `file:///absolute/path/model.xlsx`; no new Excel URI scheme.
- New spreadsheet operations use `CapabilityIdentity(name, "1.0")` and are optional.
- Formula strings are literal through Table and range writes; Formula view methods explicitly activate formulas.
- A bound grid target infers `excel-a1`, `maybe-sheet-a1`, or `google-sheets-a1` only when unambiguous; no dialect translation.
- Existing FormulaExpression wire payloads keep their required `dialect` field.
- Existing Table and `client.formulas(...)` return contracts remain unchanged.
- Missing optional spreadsheet dependencies must not prevent core SDK imports.
- All new failures use existing `OTCError`/`ErrorCode` semantics and credential-free details.

---

### Task 1: Add provider-neutral spreadsheet contracts

**Files:**
- Create: `packages/spreadsheets/pyproject.toml`
- Create: `packages/spreadsheets/src/open_table_connector/spreadsheets/__init__.py`
- Create: `packages/spreadsheets/src/open_table_connector/spreadsheets/capabilities.py`
- Create: `packages/spreadsheets/src/open_table_connector/spreadsheets/model.py`
- Test: `packages/spreadsheets/tests/test_model.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces `SpreadsheetTarget`, `WorksheetRef`, `RangeRef`, `CellFormat`, `CellStyle`, `ImageSpec`, `SPREADSHEET_WORKBOOK_INSPECT`, `SPREADSHEET_WORKSHEET_LIST`, `SPREADSHEET_RANGE_READ`, `SPREADSHEET_RANGE_WRITE`, `SPREADSHEET_RANGE_STYLE`, and `SPREADSHEET_IMAGE_INSERT`.
- Models are frozen, validate on construction, and expose `to_wire()`/`from_wire()` with closed keys.

- [ ] **Step 1: Write failing model tests** for file URI normalization, finite A1 ranges, style validation, image SHA-256 validation, closed wire keys, and capability references.
- [ ] **Step 2: Run** `uv run pytest packages/spreadsheets/tests/test_model.py -q`; expect import failures.
- [ ] **Step 3: Implement** the package and add it to workspace members with only the contract dependency.
- [ ] **Step 4: Run** the focused tests and `uv run ruff check packages/spreadsheets`; expect green.
- [ ] **Step 5: Commit** with `git commit -m "feat: add unified spreadsheet contracts"`.

### Task 2: Add one-call result inspection

**Files:**
- Modify: `packages/sdk/src/open_table_connector/sdk/result.py`
- Modify: `packages/sdk/src/open_table_connector/sdk/__init__.py`
- Test: `packages/sdk/tests/test_result.py`

**Interfaces:**
- Produces `OperationResult.with_results() -> OperationResult[T]`, returning the same immutable result object without I/O.
- Existing `require_value()` remains unchanged.

- [ ] **Step 1: Add tests** proving `.with_results()` is identity-preserving, performs no callback/I/O, and retains failed commit/verification evidence.
- [ ] **Step 2: Run** `uv run pytest packages/sdk/tests/test_result.py -q`; expect the method-missing failure.
- [ ] **Step 3: Implement** the method with a docstring stating it is a post-operation accessor.
- [ ] **Step 4: Run** focused SDK tests and `uv run ruff check packages/sdk/src/open_table_connector/sdk/result.py`.
- [ ] **Step 5: Commit** with `git commit -m "feat: expose operation results after execution"`.

### Task 3: Infer Formula dialect for string expressions

**Files:**
- Modify: `packages/sdk/src/open_table_connector/sdk/formula.py`
- Modify: `packages/sdk/src/open_table_connector/sdk/__init__.py`
- Test: `packages/sdk/tests/test_formula.py`

**Interfaces:**
- `GridFormulaView.set(cell_range, expression: FormulaExpression | str, *, dialect: str | None = None, ...)`.
- String expressions resolve the bound capability's sole dialect; explicit `dialect` is validated against advertised dialects.
- `FormulaExpression` remains explicit and unchanged on the wire.

- [ ] **Step 1: Add tests** with a fake grid extension for one dialect, asserting string shorthand constructs the same request as `FormulaExpression`; test ambiguous dialect rejection and explicit unsupported dialect rejection.
- [ ] **Step 2: Run** `uv run pytest packages/sdk/tests/test_formula.py -q`; expect signature/validation failures.
- [ ] **Step 3: Implement** `_coerce_expression` in the SDK view and route both shorthand and typed expressions through existing validation and hashing.
- [ ] **Step 4: Run** formula tests plus `uv run ruff check packages/sdk/src/open_table_connector/sdk/formula.py`.
- [ ] **Step 5: Commit** with `git commit -m "feat: infer bound formula dialects"`.

### Task 4: Document the first implementation slice and verify the workspace

**Files:**
- Modify: `packages/spreadsheets/README.md`
- Modify: `packages/local_files/README.md`
- Modify: `packages/maybe_sheet/README.md`
- Modify: `packages/google_sheets/README.md`
- Modify: `docs/package-boundaries.md`
- Test: existing package suites

**Interfaces:**
- Documents the shared model package, standard `file://` Excel targets, Formula shorthand, and current provider capability gaps.

- [ ] **Step 1: Add concise examples** and state that Table writes remain value-only and current Excel Table writes are whole-workbook replacement.
- [ ] **Step 2: Run** `uv run pytest` and `uv run ruff check .`; record any unavailable dependency or pre-existing failure without claiming a green suite.
- [ ] **Step 3: Run** `git diff --check` and inspect `git status --short`.
- [ ] **Step 4: Commit** with `git commit -m "docs: describe unified spreadsheet slice"`.

## Verification checklist

- [ ] Shared models reject malformed targets, ranges, styles, images, and wire payloads.
- [ ] `.with_results()` never repeats an operation and leaves legacy result APIs intact.
- [ ] Formula shorthand is normalized before provider dispatch, hashing, and idempotency.
- [ ] Formula strings through Table remain literal.
- [ ] Optional package import does not make SDK imports require provider dependencies.
- [ ] Focused tests and available repository checks have fresh output.
