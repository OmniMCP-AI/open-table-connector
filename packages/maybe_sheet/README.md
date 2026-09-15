# open-table-connector-maybe-sheet

MaybeSheet process bridge and table connector.

Install with `pip install open-table-connector-maybe-sheet`; import
`open_table_connector.maybe_sheet`.

## Grid formulas

Maybe sheet-mode participates in OTC's optional unified Spreadsheet interface.
The same workbook, worksheet, range, and style models are used for Maybe,
Excel, and Google Sheets; provider capabilities determine available operations.

Maybe Sheet supports bounded sheet-mode formula read, top-left copy-fill set,
provider-calculated values, and explicit recalculation in the `maybe-sheet-a1`
dialect:

```python
import open_table_connector.otc as otc

grid = client.formulas(
    otc.GridFormulaTarget(
        "https://www.maybe.ai/docs/spreadsheets/d/document",
        otc.WorksheetRef(name="Model"),
    )
).require_value()
grid.read("B2:C4")
grid.set("D2:F4", otc.FormulaExpression("=B2+$C$1", "maybe-sheet-a1"))
grid.read_values("D2:F4")
grid.recalculate(
    scope=otc.GridRecalculationScope.RANGE,
    cell_range="D2:F4",
)
```

`set()` copies the top-left expression across the bounded rectangle: relative
references translate per destination, while absolute and mixed `$` references
remain anchored. Formula text is read back independently. Value observations
are provider-dynamic (`dependency_scope=provider_dynamic`), not values computed
by OTC. A sheet formula may preserve a cross-mode reference such as
`='R_Revenue Base'!$C2*0.8`; OTC keeps that native text and does not bind or
read a separate Base target.

Maybe exposes exactly `formula.grid.read/1.0`, `formula.grid.set/1.0`,
`formula.grid.values.read/1.0`, and `formula.grid.recalculate/1.0`.
Recalculation supports `range`, `worksheet`, and `workbook` scopes. Ordinary
Table appends remain ordinary value writes; only an explicit Formula view
`FormulaExpression` activates a formula.

## Base-mode formula fields

Maybe base-mode formulas are customized computed columns, distinct from
sheet-mode cell formulas. They use the provider-native `maybe-base` language
and bind an existing formula field by stable field identity:

```python
from open_table_connector.formulas import FieldFormulaTarget, FieldRef, FormulaExpression

table = client.open(
    "https://www.maybe.ai/docs/spreadsheets/d/document?table_id=tbl-orders"
).require_value()
margin = client.formulas(
    FieldFormulaTarget(table, FieldRef(name="gross_margin"))
).require_value()
margin.set(FormulaExpression("revenue - cost", "maybe-base"))
```

Before binding, callers must create or convert `gross_margin` to a formula
field through Maybe's provider-native administration. That prerequisite is
outside this v1 API: the Formula Extension has no field-create or
field-convert operation. Formula `set()` changes only the expression and
performs a fresh metadata readback; it never writes calculated values into
records.

`read_values()` obtains fresh provider-calculated values and preserves Maybe's
stable record IDs, so IDs—not row positions—remain valid across pagination and
subsequent reads. Values have provider-dynamic dependencies: upstream fields,
linked data, or other provider state may change outside OTC, and OTC does not
evaluate or translate the native expression. Maybe is the only current field
provider with explicit recalculation:

```python
from open_table_connector.formulas import FieldRecalculationScope

margin.recalculate(scope=FieldRecalculationScope.FIELD)
```

Use a separate base-mode Table for ordinary record value writes; those writes
remain value-only and do not activate formulas.

The bound Formula view can infer Maybe's dialect for string expressions:
`grid.set("D2", "=B2+$C$1")`. Use an explicit `FormulaExpression` when sharing
plans or when a target supports more than one dialect.

## Buffered workbook editing

The provider's neutral `spreadsheet_provider()` binding uses the existing process
transport, explicitly requests mbs JSON contract 1.0, and accepts the bounded
compatibility envelopes still emitted by installed mbs 0.28.4. Workbook creation
and edits wait for `write()`. Opening and preflight may discover sheet identities.
A new remote workbook uses the requested document component as its title and
returns its actual document identity at commit; the backend creates an initial
`Sheet1`. Multi-command changes require `allow_partial=True`. Timeout and malformed
post-dispatch evidence retain known receipts and created IDs and require rebind.
There is no advertised CAS, retry, idempotency, or cross-command transaction.

Supported recorded surfaces are sheet list/create/rename/delete/move, bounded
range read/write/clear, patch style/format, merges, formulas, row heights in points,
column widths in pixels, and PNG/JPEG insertion/list/read/delete. The shared
`worksheet.config(row_heights={1: 24}, column_widths_pixels={"A": 150})` compiles
into separate native commands. Column widths in Excel character units and style
reset are rejected. Remote verification is an observation, not XLSX verification.

Current mbs RAW writes cannot preserve typed numbers, booleans, or literal empty
strings: live reads showed numeric input stored as text and empty input as blank.
The provider therefore rejects those inputs before mutation. Nonempty literal
strings (including `=text`) and blank `None` cells are accepted. Dates are rejected.
These required baseline gaps block full Maybe spreadsheet acceptance.

Sorting requires partial opt-in: it reads a bounded text rectangle, preserves equal
key order, optionally excludes a header, and places blanks last before one RAW
write. Typed cells and formulas are rejected because the provider cannot preserve
them through that path. Concurrent remote edits are not excluded. Merging rejects
observed nonempty interior values; external edits can still race that observation.

Recorded tests: `tests/test_spreadsheet.py`, including captured worksheet envelopes
in `tests/fixtures/spreadsheet-mbs-0.28.4.json`. The separate opt-in disposable live
gate is `OTC_TEST_MBS_ENABLED=1 uv run --all-packages python -m pytest
packages/maybe_sheet/tests/test_spreadsheet.py::test_live_disposable_sheet_contract
-q --tb=no`. It requires `MAYBEAI_API_TOKEN` and soft-deletes its owned workbook.
The readiness matrix records the actual live result; recorded success alone does
not establish backend acceptance.
