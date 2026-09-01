# Task 3 Report

Date: 2026-09-02
Task: Grid Formula Providers, Task 3 — Maybe Sheet
Branch: `codex/formula-extension`

## Scope Delivered

- Added `MaybeSheetGridFormulaExtension` over the existing `ProcessClient`, using canonical JSON-output `mbs` commands and passing credentials only through `ProcessClient.run`.
- Added strict result-envelope validation, configured timeout/response limits, bounded A1 ranges, expression limits, provider error values, formula text observations, and `provider_dynamic` calculated-value observations.
- Bound exact sheet worksheet names and stable gids, rejected missing/ambiguous/non-sheet matches, and retained worksheet titles only as display metadata.
- Implemented provider-reported recalculation scopes, atomicity, revision enforcement, and idempotency details without changing static capability advertisement.
- Implemented top-left copy-fill verification through a separate formula read after every verified set, including stale-revision forwarding, idempotency replay/conflict/uncertain handling, and safe pre-dispatch retry behavior.
- Added explicit range/worksheet/workbook recalculation forwarding with requested/effective scope and optional value evidence; acknowledgements without values report verification unavailable.
- Added the adapter composite seam with an optional `field_formula_extension` delegate, removed the legacy connector formula aliases, and added the formulas package dependency.
- Left Maybe static capabilities, modes, manifests, ordinary table reads/writes, and field formula implementation unchanged.

## RED Evidence

```text
uv run --frozen python -m pytest packages/maybe_sheet/tests/test_grid_formula.py -q
13 failed
```

The initial failures were the expected missing `grid_formula` module/import seam.

## GREEN Verification

```text
uv lock
Resolved 38 packages in 323ms
```

```text
uv run --frozen python -m pytest packages/maybe_sheet/tests/test_grid_formula.py packages/maybe_sheet/tests/test_connector.py packages/maybe_sheet/tests/test_cli_adapter.py -q
37 passed in 0.45s
```

```text
uv run --frozen ruff check packages/maybe_sheet
All checks passed!
```

```text
git diff --check
[no output]
```

## Concerns

- The report includes mechanical Ruff import/lambda cleanup in existing Maybe temporal/test files because the requested package-wide `ruff check packages/maybe_sheet` gate otherwise remained red; no temporal behavior was changed.
- Formula capabilities remain runtime extension metadata only; static Maybe discovery stays base-read/inspect/table-write and base mode as required until the later enablement task.

## Task 3 Review-Fix Remediation

### RED Evidence

After adding the review regressions, the pre-fix implementation produced:

```text
uv run --frozen python -m pytest packages/maybe_sheet/tests/test_grid_formula.py packages/maybe_sheet/tests/test_connector.py -q
17 failed, 35 passed in 0.32s
```

The failures covered binding fallback, fabricated value receipts, recalculation verification, canonical provider errors, terminal idempotency, formula-cell bounds, and copy-fill reference handling.

### GREEN Verification

```text
uv run --frozen python -m pytest packages/maybe_sheet/tests/test_grid_formula.py packages/maybe_sheet/tests/test_connector.py packages/maybe_sheet/tests/test_cli_adapter.py packages/cli/tests/test_commands.py packages/formulas/tests -q
150 passed in 0.56s
```

```text
uv run --frozen ruff check <all changed formula/Maybe/SDK files>
All checks passed!
```

```text
git diff --check
[no output]
```

The requested package-wide Ruff command still reports pre-existing findings in untouched `packages/cli/tests` files (`I001`, `UP017`, and `F401`).

### Changed Files

- `packages/maybe_sheet/src/open_table_connector/maybe_sheet/grid_formula.py`
- `packages/maybe_sheet/tests/test_grid_formula.py`
- `packages/formulas/src/open_table_connector/formulas/errors.py`
- `packages/formulas/src/open_table_connector/formulas/operations.py`
- `packages/formulas/src/open_table_connector/formulas/receipts.py`
- `packages/formulas/tests/test_operations.py`
- `packages/sdk/src/open_table_connector/sdk/formula.py`
- `docs/superpowers/plans/2026-09-02-maybe-sheet-task-3-review-fixes.md`
- `.superpowers/sdd/2026-09-01-grid-formula-providers/task-3-report.md`

Commit: `fix: harden Maybe Sheet formula review findings` (hash reported by final VCS status)

### Remaining Concerns

- Static Maybe capabilities and Base/field formula paths remain disabled; ordinary table reads and writes are unchanged.
- Full package Ruff remains blocked only by the pre-existing CLI test lint findings noted above.

## Task 3 Review-Fix Round 2

### RED Evidence

Added focused regressions for recalculation evidence target/range validation, worksheet/workbook matrix ranges, malformed evidence, standalone identifier handling, and doubled-apostrophe worksheet names. Before the implementation fix:

```text
uv run --frozen python -m pytest packages/maybe_sheet/tests/test_grid_formula.py -q
5 failed, 39 passed
```

### GREEN Verification

```text
uv run --frozen python -m pytest packages/maybe_sheet/tests/test_grid_formula.py packages/maybe_sheet/tests/test_connector.py packages/maybe_sheet/tests/test_cli_adapter.py packages/cli/tests/test_commands.py packages/formulas/tests -q
157 passed in 0.47s
```

```text
uv run --frozen ruff check packages/maybe_sheet/src/open_table_connector/maybe_sheet/grid_formula.py packages/maybe_sheet/tests/test_grid_formula.py
All checks passed!
```

```text
git diff --check
[no output]
```

The requested broader `uv run --frozen ruff check packages/maybe_sheet packages/formulas packages/cli` command remains red only on pre-existing untouched `packages/cli/tests` findings (`I001`, `UP017`, and `F401`).

### Changed Files

- `packages/maybe_sheet/src/open_table_connector/maybe_sheet/grid_formula.py`
- `packages/maybe_sheet/tests/test_grid_formula.py`
- `.superpowers/sdd/2026-09-01-grid-formula-providers/task-3-report.md`

Commit: `fix: harden Maybe recalculation evidence and copy-fill`

### Concerns

- Recalculation acknowledgements without value evidence remain successful with verification `unavailable`.
- Static Maybe formula capabilities and ordinary table paths remain unchanged.
- Broader package Ruff still has the pre-existing CLI test lint findings listed above; focused changed-file Ruff is clean.
