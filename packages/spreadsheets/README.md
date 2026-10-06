# open-table-connector-spreadsheets

Provider-neutral contracts for workbook, worksheet, range, format, style,
rich-object, snapshot, and layout-recipe operations. Provider adapters remain
optional and are not imported by this package.

The closed rich surface includes `RichObjectRequest`, `ObjectObservation`, and
`RichQualification`. Qualification is evidence-backed per provider: local
Excelize currently qualifies PNG/JPEG image workflows, while MaybeSheet
sheet-mode remains live-evidence gated. Unsupported object families are
capability-blocked rather than inferred from a local binding's method names.

`LayoutRecipe` uses the `otc.spreadsheet-recipe/1.0` envelope. Recipes capture
observed layout operations and requirements; they never carry cell values,
formulas, or image bytes and they reject unsupported properties before
dispatch. OfficeCLI is not a spreadsheet backend for this package.

The [SDK manual](../../docs/user-guide/sdk-manual.md) contains session examples;
the generated [spreadsheet schemas](../../docs/reference/spreadsheet-schemas.md)
are the exhaustive operation reference.
