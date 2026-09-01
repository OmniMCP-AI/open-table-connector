# Task 1 Report

Date: 2026-09-02
Task: Grid Formula Providers, Task 1
Branch: `codex/formula-extension`

## Scope Delivered

- Added literal provider-specific Google Sheets, Maybe Sheet, and Excel grid documents covering single-cell text, 2x3 top-left copy-fill, relative/absolute/mixed references, quoted and cross-worksheet references, provider functions, external references, sparse formulas, blanks, provider errors, and value-observation state/trigger metadata.
- Added recording HTTP, process, and workbook-loader doubles that preserve request arguments, credentials, timeouts, payload copies, and independent workbook opens.
- Added the capability-selected grid matrix with Google read/set/value-read, Maybe read/set/value-read/recalculate, and Excel read/set expectations.
- Added typed failure simulations for timeout-before-dispatch, provider rejection, partial response, lost acknowledgement, readback mismatch, and unknown commit, including no-retry and raw-expression safety assertions.
- Left provider adapters, provider cases, and static capability advertisements unchanged. Provider cases intentionally remain empty so the matrix is the red handoff for Tasks 2–4.

## RED Evidence

Before the shared module existed, the brief's focused command failed during collection with:

```text
ModuleNotFoundError: No module named 'specification.conformance.formulas.grid_cases'
```

After the shared fixture layer was added, the same command reaches the intended red gate:

```text
2 failed, 17 passed
```

The two failures are the provider-case existence and capability-matrix assertions; they are expected until the later provider implementation tasks register adapters.

## Verification

```text
uv run --frozen python -m pytest specification/conformance/formulas/test_grid_providers.py specification/conformance/formulas/test_grid_copy_fill.py specification/conformance/formulas/test_grid_recovery.py -q
2 failed, 17 passed
```

```text
uv run --frozen python -m pytest specification/conformance/formulas -q
2 failed, 41 passed
```

```text
uv run --frozen ruff check specification/conformance/formulas
All checks passed!
```

```text
git diff --check
[no output]
```

## Concerns

- The focused grid suite is intentionally red because Task 1 must not implement or enable the Google, Maybe, or Excel adapters. Tasks 2–4 should turn the two matrix failures green by registering their provider cases; no fixture changes should be needed for the shared contract.
