# Grid Formula Providers — Task 6 Report

Date: 2026-09-02
Task: Grid Formula Providers, Task 6
Branch: `codex/formula-extension`

## Scope Delivered

- Documented the exact certified grid capability matrix for Google Sheets,
  Maybe Sheet, and direct Excel `.xlsx`.
- Added concise bounded read/set examples using the provider-native dialects:
  `google-sheets-a1`, `maybe-sheet-a1`, and `excel-a1`.
- Documented top-left copy-fill semantics, independent formula-text readback,
  Maybe cross-mode worksheet references, and `dependency_scope=provider_dynamic`
  value observations for Google and Maybe.
- Documented that direct Excel exposes no Formula calculated-value read or
  recalculation capability, and that workbook calculation-on-open flags are not
  execution evidence.
- Documented ordinary-write safety: Formula activation requires an explicit
  `FormulaExpression`; Google Table writes remain `valueInputOption=RAW`, and
  ordinary Excel writes preserve formula-prefixed strings as text.
- Corrected the root Formula section so it no longer claims all real-provider
  Formula capabilities are disabled.
- No implementation behavior, field capability, or provider capability was
  changed. No configured-live evidence record was added because no configured
  live provider run was available; recording tests are not live evidence.

## Changed Files

- `README.md`
- `packages/google_sheets/README.md`
- `packages/maybe_sheet/README.md`
- `packages/local_files/README.md`
- `.superpowers/sdd/2026-09-01-grid-formula-providers/task-6-report.md`

## Verification Gate

The exact Task 6 gate was run in the order listed by the brief:

```text
uv lock --check
EXIT 0
Resolved 38 packages in 21ms
```

```text
uv run --frozen python -m pytest packages/formulas/tests packages/sdk/tests/test_formula.py packages/google_sheets/tests packages/maybe_sheet/tests packages/local_files/tests specification/conformance/formulas specification/conformance/universal -q
EXIT 1
716 passed, 1 skipped, 2 failed in 4.35s
```

The two failures are the existing universal legacy-alias checks:

```text
specification/conformance/universal/test_table_connectors.py::test_maybe_sheet_formula_operations_fail_closed[formula-calculate-unsupported]
specification/conformance/universal/test_table_connectors.py::test_maybe_sheet_formula_operations_fail_closed[formula-readback-unsupported]
```

They still call the intentionally removed `MaybeSheetConnector.calculate_formulas`
and `MaybeSheetConnector.read_formula_values`; the current connector tests
explicitly verify those attributes are absent. This is pre-existing at Task 6
and unrelated to the documentation diff.

```text
uv run --frozen mypy packages/formulas/src packages/sdk/src packages/google_sheets/src packages/maybe_sheet/src packages/local_files/src
EXIT 1
Found 307 errors in 55 files (checked 66 source files)
```

The mypy diagnostics are pre-existing and outside the changed files. They
include missing local workspace imports/stubs for `open_table_connector`
packages, untyped `pyarrow`/`openpyxl`, and existing SDK/local-files typing
errors involving Polars unions, dataclass/result types, and invalid imported
type aliases.

```text
uv run --frozen ruff check .
EXIT 1
Found 115 errors.
[*] 106 fixable with the `--fix` option (9 hidden fixes can be enabled with the `--unsafe-fixes` option).
```

The Ruff diagnostics are pre-existing and outside the changed files; they are
primarily import ordering, unused imports, `UP035`, and `E731` findings in the
existing Python/conformance sources. Markdown files are not analyzed by this
Ruff invocation.

```text
uv run --frozen python scripts/check_package_boundaries.py
EXIT 0
[no output]
```

```text
uv run --frozen python scripts/check_package_metadata.py
EXIT 0
[no output]
```

```text
git diff --check
EXIT 0
[no output]
```

## Safety Scans and Manual Review

```text
rg -n "valueInputOption=" packages/google_sheets
EXIT 0
```

Matches were limited to the expected ordinary-write implementation and test
(`packages/google_sheets/src/open_table_connector/google_sheets/connector.py:296`,
`packages/google_sheets/tests/test_connector.py:158`) plus the new documentation
example.

```text
rg -n "data_type = \"f\"|formula.*recalculate|formula.*values" packages/local_files packages/maybe_sheet
EXIT 0
```

Matches were limited to the expected Maybe Formula adapter/tests, Excel writer
safety test, and documentation. Manual source review additionally confirmed:

- Google ordinary writes use `valueInputOption=RAW` at
  `packages/google_sheets/src/open_table_connector/google_sheets/connector.py:294-298`.
- The ordinary Excel writer forces string cells to `data_type="s"` at
  `packages/local_files/src/open_table_connector/local_files/excel_writer.py:50-54`.
- Direct Excel formula reads select native formula cells only at
  `packages/local_files/src/open_table_connector/local_files/excel_formula.py:543-562`;
  `read_grid_values()` and `recalculate_grid()` reject as unsupported at
  `packages/local_files/src/open_table_connector/local_files/excel_formula.py:193-203`.
- Excel top-left copy-fill uses the provider translator at
  `packages/local_files/src/open_table_connector/local_files/excel_formula.py:578-591`.
- Governed temporal Excel still rejects formulas at
  `packages/local_files/src/open_table_connector/local_files/temporal_excel.py:278-283`.
- Maybe’s provider Formula routing remains a grid-only composite with no field
  delegate at `packages/maybe_sheet/src/open_table_connector/maybe_sheet/connector.py:132-140`.

## Focused Safety Regression Tests

```text
uv run --frozen python -m pytest packages/google_sheets/tests/test_connector.py::test_google_sheets_uses_credentials_and_writes_values packages/maybe_sheet/tests/test_connector.py::test_maybe_sheet_connector_does_not_expose_legacy_formula_aliases packages/local_files/tests/test_excel_writer.py::test_excel_writer_round_trips_formula_prefixed_headers_and_values_as_text packages/local_files/tests/test_temporal_excel.py::test_direct_excel_rejects_formula_in_governed_worksheet packages/local_files/tests/test_temporal_excel.py::test_excel_advertises_no_formula_calculation_or_evidence -q
EXIT 0
5 passed in 0.32s
```

## Commit

Commit: `docs: describe grid formula providers`
