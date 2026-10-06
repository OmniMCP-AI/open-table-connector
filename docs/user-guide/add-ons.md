# Add-ons

Use this page for the short add-on overview. The [components manual](components.md)
has the complete package/dependency matrix, and the [SDK manual](sdk-manual.md)
has end-to-end examples for formulas, workbooks, artifacts, and MCP.

OTC add-ons are independently released provider packages. They contribute a
connector descriptor, URI schemes, table modes, capabilities, and optional
provider-specific operations. The neutral contract, time-series, and formula
packages do not depend on application frameworks.

## Discover installed providers

```console
otc list --output-format json
```

The output is capability-based. A provider may be installed but disabled, or
may support ordinary table operations without supporting portable temporal
storage or formulas.

## Formula Extension

Formula operations are separate from value-only `Table` writes. Formula text is
provider-native and opaque; OTC does not translate or evaluate it.

```python
import open_table_connector.sdk as otc

grid = client.formulas(
    otc.GridFormulaTarget(
        "gsheets://SPREADSHEET_ID",
        otc.WorksheetRef(name="Model"),
    )
).require_value()
grid.set(
    "D2:F4",
    otc.FormulaExpression("=B2+$C$1", "google-sheets-a1"),
).require_value()
```

Activation requires an explicit `FormulaExpression`. Ordinary writes remain
values. A successful formula mutation is verified by independent metadata or
formula-text readback; calculated values, where supported, are provider-
dynamic observations.

## Provider boundaries

Google Sheets, Feishu Bitable, Maybe Sheet, and direct Excel expose different
capability sets. Check the provider README and `otc list` before relying on
calculated-value reads, recalculation, field formulas, or temporal lifecycle
operations.

## Optional artifact and MCP add-ons

Install `open-table-connector-artifacts` with
`open-table-connector-officecli` when a workflow needs native DOCX/PPTX table
snapshots. OfficeCLI is isolated from XLSX authoring: rich local XLSX uses the
existing Excelize provider and MaybeSheet sheet-mode is advertised only when
its operation and evidence gates pass.

Install `open-table-connector-mcp` separately to run the typed MCP stdio
adapter. It exposes `otc_discover`, `otc_inspect`, and `otc_execute` under the
fail-closed `OTC_MCP_CONFIG` policy. The adapter does not accept shell commands,
arbitrary imports, or credential values in requests.
