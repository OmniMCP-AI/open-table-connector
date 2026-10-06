# open-table-connector-artifacts

Neutral document-artifact contracts for optional Open Table Connector adapters.

Install with `pip install open-table-connector-artifacts`; import
`open_table_connector.artifacts`.

The package defines closed contracts for native export and disposable views:
`ExportRequest`, `ViewRequest`, `WatchRequest`, `ArtifactValue`, `ViewValue`,
and `WatchValue`. Supported export destinations are qualified DOCX/PPTX
snapshots; legacy Office binary extensions and OfficeCLI XLSX authorship are
rejected. View modes are `html`, `screenshot`, `text`, `outline`, `stats`, and
`issues`. Renderer availability is reported as an explicit capability result;
view and watch outputs are disposable and never become the source workbook.

Install `open-table-connector-officecli` to register the optional physical
adapter. The neutral package itself has no OfficeCLI or browser dependency and
can be imported by the core SDK without activating an external process.

See the [components manual](../../docs/user-guide/components.md) for adapter
ownership and the [SDK manual](../../docs/user-guide/sdk-manual.md) for view and
watch lifecycle examples.
