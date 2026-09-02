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

table = client.open("maybe://document/R_orders").require_value()
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
