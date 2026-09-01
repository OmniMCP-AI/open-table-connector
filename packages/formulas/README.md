# Open Table Connector Formulas

`open-table-connector-formulas` contains the provider-neutral Formula
Extension contract. It defines immutable targets and expressions, closed
capability identities, typed observations and values, safe Receipt details,
bounded A1 rectangles, and the provider extension protocol. It performs no
provider I/O and does not parse, translate, or evaluate formula text.

## Targets and activation

Formula targets are mode-specific:

- `GridFormulaTarget` identifies a physical grid URI and one `WorksheetRef`.
  Grid operations use bounded, closed A1 rectangles and belong to the
  sheet-mode grid surface.
- `FieldFormulaTarget` identifies an already opened base-mode `Table` and one
  `FieldRef`. It never creates a field, converts a field, or writes record
  values.

The SDK binds these targets through `Client.formulas(...)`. A formula is
activated only when a caller explicitly passes a `FormulaExpression` to a
bound Formula view's `set()` method. Ordinary `Table.insert()`, `update()`,
and other value-only operations retain their existing behavior.

Expressions are provider-native and opaque. The required dialect must match
the provider's effective capability, for example `google-sheets-a1`,
`maybe-sheet-a1`, `excel-a1`, `maybe-base`, or `feishu-bitable`. OTC preserves
the text and never translates it between dialects.

## Public facade examples

The SDK is the application-facing facade. A grid binding has a worksheet and
returns a `GridFormulaView`:

```python
import open_table_connector.sdk as otc

grid = client.formulas(
    otc.GridFormulaTarget(
        grid="gsheets://spreadsheet-id",
        worksheet=otc.WorksheetRef(name="Model"),
    )
).require_value()

grid.set(
    "A1:B2",
    otc.FormulaExpression("=A1+1", "google-sheets-a1"),
).require_value()
```

A field binding uses an opened base-mode table and returns a
`FieldFormulaView`:

```python
orders = client.open("feishu://app/table").require_value()
field = client.formulas(
    otc.FieldFormulaTarget(
        table=orders,
        field=otc.FieldRef(name="gross_margin"),
    )
).require_value()

field.set(
    otc.FormulaExpression("=revenue-cost", "feishu-bitable"),
).require_value()
```

Both examples describe the typed API; they do not imply that the referenced
provider currently advertises Formula support.

## Disabled core checkpoint

This package publishes the core contract only. At this checkpoint no real
provider advertises a Formula capability identity. The grid-provider and
field-provider plans must each install, exercise, and pass their focused
conformance gate before enabling the identities for that provider. A missing
or unproven capability remains unsupported rather than falling back to a
normal Table write.
