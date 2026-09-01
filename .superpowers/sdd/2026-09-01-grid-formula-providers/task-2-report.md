# Task 2 Report

Date: 2026-09-02
Task: Grid Formula Providers, Task 2 — Google Sheets
Branch: `codex/formula-extension`

## Scope Delivered

- Added `GoogleSheetsFormulaExtension` over the configured `SheetsTransport`.
- Added exact spreadsheet metadata binding by worksheet name or numeric `sheetId`, with bound worksheet identity, Google A1 dialect, capability details, worksheet limits, and hashed metadata revision.
- Added bounded native grid reads using `userEnteredValue.formulaValue`, `effectiveValue`, and `effectiveFormat.numberFormat`; rendered or formula-looking string values are never treated as formulas.
- Added provider-current calculated-value observations with native number, string, boolean, logical date/time, null, and sanitized provider-error values.
- Added pre-I/O A1/cell/expression validation, response-size enforcement, response coordinate checks, malformed-branch rejection, and safe typed errors.
- Added native `RepeatCellRequest` grid mutation, checked revisions, top-left copy-fill validation, independent formula-text readback, readback mismatch handling, partial results, uncertain acknowledgement reconciliation, and no blind POST retries.
- Added ledger-backed idempotency replay/conflict/unknown handling with concurrency-safe access and hashed target/range/dialect/expression/revision bindings.
- Added CLI adapter forwarding that reuses the configured connector and leaves static capabilities and manifest enablement unchanged.
- Added the Formula package dependency and workspace source entry; ordinary Google table writes remain `valueInputOption=RAW`.

## RED Evidence

The first focused test run failed during collection as expected:

```text
ModuleNotFoundError: No module named 'open_table_connector.google_sheets.formula'
```

## Verification

```text
uv lock
Resolved 38 packages in 5.30s
```

```text
uv run --frozen python -m pytest packages/google_sheets/tests/test_formula.py packages/google_sheets/tests/test_connector.py packages/google_sheets/tests/test_cli_adapter.py -q
26 passed
```

```text
uv run --frozen ruff check packages/google_sheets
All checks passed!
```

```text
git diff --check
[no output]
```

## Concerns

- Static Google capability tuples and `manifest.json` remain unchanged by design; capability discovery remains disabled until the later enablement task.
- The shared grid-provider matrix remains intentionally red until Tasks 3–5 register and enable all providers.
