# Grid Formula Providers — Task 4 Report

Date: 2026-09-02
Branch: `codex/formula-extension`

## Delivered

- Added a direct `.xlsx` `ExcelFormulaExtension` for exact worksheet-bound A1 formula reads and copy-filled formula writes.
- Preserved workbook objects through editable `openpyxl` loading with links retained, and published changes through a locked, fsynced temporary file and atomic replacement.
- Enforced pre-parse cell/response limits and post-parse formula-expression limits.
- Added revision checks, idempotency-ledger handling, post-publication formula readback, and safe known-failure/unknown-outcome reporting.
- Rejected symlinks, non-`.xlsx` inputs, malformed/unsafe ZIPs, ambiguous worksheet bindings, value reads, and recalculation requests.
- Wired the extension only through the disabled Excel adapter identity. No static capability or manifest enablement was added; managed temporal rejection remains unchanged.

## Test-first evidence

- RED: the new Excel formula test module initially failed collection because `ExcelFormulaExtension` was not yet available.
- GREEN: focused Excel formula tests: `11 passed`.
- Excel, preservation, connector, adapter, and temporal regression tests: `37 passed`.
- Local-files plus formulas test suites: `204 passed`.

## Static checks

- Ruff passed for the new Task 4 implementation and tests.
- Ruff format check passed for the new Task 4 implementation and tests; the touched adapter also contains pre-existing unformatted lines outside the Task 4 change.
- `git diff --check` passed.
- Package-wide local-files Ruff still reports pre-existing findings in untouched files; Task 4 changed files are clean.

## Concerns

Excel intentionally does not advertise calculated-value reads or recalculation. Formula writes request Excel recalculation metadata but do not claim that a calculation service executed or verified values.
