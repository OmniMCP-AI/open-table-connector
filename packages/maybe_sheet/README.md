# open-table-connector-maybe-sheet

MaybeSheet process bridge and table connector.

Install with `pip install open-table-connector-maybe-sheet`; import
`open_table_connector.maybe_sheet`.

## Grid formulas

Maybe Sheet supports bounded sheet-mode formula read, top-left copy-fill set,
provider-calculated values, and explicit recalculation in the `maybe-sheet-a1`
dialect:

```python
import open_table_connector.otc as otc

grid = client.formulas(
    otc.GridFormulaTarget(
        "maybe://document/Model",
        otc.WorksheetRef(name="Model"),
    )
)
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
