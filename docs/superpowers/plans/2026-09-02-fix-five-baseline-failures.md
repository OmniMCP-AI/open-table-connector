# Fix Five Baseline Failures Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make OTC's full Python test suite pass by correcting the five pre-existing formula/provider-contract failures without changing the temporal/decimal behavior already implemented on `main`.

**Architecture:** Keep provider identity and route values sourced from the contract's canonical names module. Preserve MaybeSheet's current public base-plus-sheet capability surface, make the shared formula test double honor its requested broken behavior, and align the universal contract tests with the modern formula-extension-only connector surface.

**Tech Stack:** Python 3.11+, pytest, uv workspace, AST-based static checks, dataclass-backed provider adapters.

**Spec:** `specification/conformance/universal/README.md` and the formula fixtures under `specification/fixtures/formulas/v1/`.

## Global Constraints

- Preserve the provider-neutral formula extension API and its typed capability/error contracts.
- Keep canonical provider, scheme, and host identifiers centralized in `packages/contract/src/open_table_connector/contract/names.py`.
- MaybeSheet supports both `TableMode.BASE` and `TableMode.SHEET`, as represented by its discovery case and adapter metadata.
- Unsupported operations must raise `ConnectorErrorCode.UNSUPPORTED_CAPABILITY` with safe capability details and must not invoke provider I/O.

### Task 1: Canonical literal checker and provider formula sources

**Files:**
- Modify: `scripts/check_canonical_literals.py`
- Modify: `packages/feishu_bitable/src/open_table_connector/feishu_bitable/formula.py`
- Modify: `packages/google_sheets/src/open_table_connector/google_sheets/formula.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/excel_formula.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/manifest.py`
- Modify: `packages/maybe_sheet/src/open_table_connector/maybe_sheet/field_formula.py`
- Modify: `packages/maybe_sheet/src/open_table_connector/maybe_sheet/grid_formula.py`
- Test: `packages/cli/tests/test_provider_independence.py`

**Interfaces:** Production provider modules import canonical constants and use them for connector IDs, schemes, hosts, and process output formats. The checker scans only package `src` trees, excluding generated `build` and `dist` copies.

- [ ] **Step 1: Run the existing static-check test and capture the current repeated-literal failures.**
- [ ] **Step 2: Replace each flagged production literal with the matching canonical constant, importing only the constants needed by that module.**
- [ ] **Step 3: Restrict `check_canonical_literals` to `packages/*/src/**/*.py` so ignored build products cannot create production-source failures.**
- [ ] **Step 4: Run `uv run --frozen pytest packages/cli/tests/test_provider_independence.py::test_production_python_reuses_canonical_provider_and_route_constants -q` and confirm it passes.**

### Task 2: MaybeSheet registry metadata

**Files:**
- Modify: `packages/cli/tests/test_registry.py`

**Interfaces:** The registry continues to expose `MaybeSheetCliAdapter.modes == (TableMode.BASE, TableMode.SHEET)`; the test must assert the public metadata already required by the universal discovery case.

- [ ] **Step 1: Change the stale assertion from `(TableMode.BASE,)` to `(TableMode.BASE, TableMode.SHEET)`.**
- [ ] **Step 2: Run the focused registry test and confirm it passes.**

### Task 3: Formula conformance broken-behavior fixture

**Files:**
- Modify: `specification/conformance/formulas/support.py`
- Test: `packages/conformance/tests/test_formula_framework.py`

**Interfaces:** `BrokenBehavior(broadcast_copy_fill=True)` must cause the fake provider to return broadcast formula text even when the submitted expression matches the fixture's normal source expression, allowing `assert_grid_formula_conformance` to reject it.

- [ ] **Step 1: Run the parametrized broadcast-copy-fill test and confirm it currently passes unexpectedly.**
- [ ] **Step 2: Give the broken behavior precedence over the fixture shortcut in `FakeFormulaExtension.set_grid`.**
- [ ] **Step 3: Re-run only the broadcast parameter and confirm the expected assertion is raised.**

### Task 4: MaybeSheet unsupported legacy operations

**Files:**
- Test: `specification/conformance/universal/test_table_connectors.py`

**Interfaces:** `MaybeSheetConnector` exposes formula operations through `formula_extension_for()` only. The universal contract test must not call removed legacy aliases; the provider unit test continues to assert those aliases are absent.

- [ ] **Step 1: Replace the universal test's obsolete calls with assertions that the removed legacy aliases are absent.**
- [ ] **Step 2: Keep `MaybeSheetConnector` free of those aliases so the modern extension boundary remains explicit.**
- [ ] **Step 3: Run the focused MaybeSheet tests and universal contract test to confirm the current API boundary.**

### Task 5: Full verification

**Files:**
- No additional source files.

- [ ] **Step 1: Run all focused tests covering the five fixes.**
- [ ] **Step 2: Run `uv run --frozen pytest -q` and require zero failures.**
- [ ] **Step 3: Run `uv run --frozen ruff check` on changed Python files and inspect the final diff/status.**
