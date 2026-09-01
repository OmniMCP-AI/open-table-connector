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
