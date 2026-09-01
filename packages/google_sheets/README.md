# Google Sheets connector

Reads and writes Google Sheets values through the Google Sheets API v4. Supply
an OAuth access token and optionally an injected transport for testing.

Supported URIs are `gsheets://SPREADSHEET_ID/SHEET_NAME` and Google Sheets
URLs. Reads use the first row as column headers by default; writes use
`append` for append semantics and `replace`/`error` for range updates.

## Grid formulas

Google Sheets supports bounded sheet-mode formula read, top-left copy-fill set,
and calculated-value readback through the `google-sheets-a1` dialect:

```python
import open_table_connector.otc as otc

grid = client.formulas(
    otc.GridFormulaTarget(
        "gsheets://spreadsheet-id",
        otc.WorksheetRef(name="Model"),
    )
).require_value()
grid.read("B2:C4")
grid.set("D2:F4", otc.FormulaExpression("=B2+$C$1", "google-sheets-a1"))
grid.read_values("D2:F4")
```

`set()` copies the top-left expression across the bounded rectangle: relative
references move per destination, while absolute and mixed `$` references stay
anchored. Formula text is read back independently after the write. Values are
provider-calculated observations and may depend on provider-dynamic data; they
are not a portable OTC evaluation.

Google exposes exactly `formula.grid.read/1.0`, `formula.grid.set/1.0`, and
`formula.grid.values.read/1.0`. It does not expose Formula recalculation; a
provider-current value read is not an explicit recalculation guarantee.

Formula activation is explicit. Ordinary Table writes continue to use
`valueInputOption=RAW`, so a string beginning with `=` remains an ordinary
value and does not activate a formula. Supply a `FormulaExpression` through
the Formula view when activation is intended.
