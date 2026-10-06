# OfficeCLI adapter

Optional physical adapter for native DOCX/PPTX table export and disposable
document views. It is never imported by ordinary table or XLSX commands.

Install with `pip install open-table-connector-officecli`; it registers the
`officecli` artifact adapter. The adapter accepts qualified CSV-to-DOCX/PPTX
table snapshots and reports content hashes plus native-table coverage. It does
not author XLSX; rich XLSX remains on the existing Excelize-backed local
provider and the capability-gated MaybeSheet sheet-mode contract.

The adapter exposes the neutral view modes `html`, `screenshot`, `text`,
`outline`, `stats`, and `issues`, plus disposable watch-session records. A
qualified OfficeCLI binary and renderer are required for live rendering. When
the runtime is absent, callers receive `unsupported_capability` instead of a
synthetic output. View/watch files are disposable snapshots and are never
published as authoritative workbook content.
