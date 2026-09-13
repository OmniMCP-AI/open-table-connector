# open-table-connector-local-files

CSV, JSON, JSONL, and Excel local-file connectors and managed snapshots.

Install with `pip install open-table-connector-local-files`; import
`open_table_connector.local_files`.

## Direct Excel grid formulas

Excel workbooks use standard local file targets such as
`file:///absolute/path/model.xlsx`. The unified Spreadsheet interface and the
existing Formula view resolve that target to the same local adapter. Legacy
`excel://`/`xlsx://` aliases remain compatibility inputs where registered.

The direct `excel` provider supports bounded sheet-mode formula read and
top-left copy-fill set for existing `.xlsx` workbooks in the `excel-a1`
dialect:

```python
import open_table_connector.otc as otc

grid = client.formulas(
    otc.GridFormulaTarget(
        "file:///absolute/path/model.xlsx#sheet=Model",
        otc.WorksheetRef(name="Model"),
    )
).require_value()
grid.read("B2:C4")
grid.set("D2:F4", otc.FormulaExpression("=B2+$C$1", "excel-a1"))
```

`set()` copies the top-left expression across the bounded rectangle: relative
references translate per destination, while absolute and mixed `$` references
remain anchored. The provider reopens the published workbook and verifies
formula text after the write. It exposes exactly `formula.grid.read/1.0` and
`formula.grid.set/1.0` for direct `.xlsx` files.

Excel has no `formula.grid.values.read/1.0` and no
`formula.grid.recalculate/1.0`: openpyxl preserves formula text and can set
workbook calculation-on-open flags, but it does not execute Excel’s calculation
engine. Managed temporal Excel remains formula-rejecting.

Ordinary Table writes remain value-only. The ordinary Excel writer forces
formula-prefixed strings to text; use an explicit Formula view and
`FormulaExpression` when formula activation is intended.

The Formula view also accepts a string and infers the bound Excel dialect:
`grid.set("D2", "=B2+$C$1")`. This is formula intent; a Table write containing
the same string remains literal. Table writes create or replace a whole
workbook, so use Spreadsheet range operations for in-place edits that preserve
existing formulas and layout.

## Unified workbook sessions

`client.workbook.create("file:///absolute/path/report.xlsx")` creates an
exclusive `literal-artifact/1.0` session. Select sheets with
`book.worksheet.create("Report")`, write literal ranges with
`sheet.range("A1:B2").write(...)`, and finish with `book.write()` or
`book.verify()`. `client.workbook(uri)` opens an existing workbook for edits;
its `write()` uses a verified temporary replacement. Formula cells are only
created through `sheet.formulas().set(...)` and are rejected by the literal
artifact verifier, while formula evaluation remains provider-owned.
