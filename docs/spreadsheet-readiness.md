# Spreadsheet readiness evidence

Status as of 2026-09-14: the shared contract and local Excel implementation
are usable; FinClaw cutover remains gated on the adapter parity and conformance
work listed below.

## Verified in this revision

- `client.workbook.create("file:///...xlsx")` uses the slim workbook,
  worksheet, range, formula, style, format, image, sort, write and verify
  operations.
- New literal workbooks are staged and create-exclusive. A failed literal
  verification removes the newly owned artifact; an existing workbook is
  updated through a verified temporary replacement.
- Literal text is forced to Excel text cells, formula activation is explicit,
  and literal-artifact verification rejects formulas.
- Verification checks decoded cells and raw ZIP/XML structure, including
  duplicate archive members, worksheet relationships, coordinates, sheet order,
  formula presence, limits, and image anchors/hashes.
- Google Sheets exposes worksheet discovery and raw range read/write through the
  same handle. Formula writes and calculated values continue through the
  provider Formula extension. Maybe Sheet exposes the same entry point and
  fails unsupported operations before dispatch.

## Validation evidence

```text
pytest packages/spreadsheets/tests packages/local_files/tests packages/sdk/tests \
       packages/google_sheets/tests packages/maybe_sheet/tests -q
431 passed, 1 skipped

pytest packages/google_sheets/tests packages/maybe_sheet/tests \
       packages/local_files/tests/test_spreadsheet_workbook.py \
       packages/spreadsheets/tests packages/sdk/tests -q
288 passed, 1 skipped
```

The focused workbook/model/Formula run passed 48 tests. Changed-file Ruff
checks pass. The repository-wide Ruff invocation still reports pre-existing
import-order findings in untouched legacy modules.

## FinClaw gate

The implementation does not yet claim R1–R16 parity. The remaining gate is an
adapter in FinClaw that translates authenticated sections to the slim workbook
session while retaining FinClaw's semantic verifier, plus golden/corruption,
collision, cleanup, receipt and offline replay tests. Until those run on the
pinned FinClaw candidate, FinClaw's existing `excel.py` remains authoritative.
