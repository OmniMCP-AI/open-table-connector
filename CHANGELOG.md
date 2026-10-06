# Changelog

All notable changes to this project are documented here.

## [Unreleased]

- Added the P0-P2 CLI and artifact surface: progressive `help`/`capabilities`
  discovery, typed spreadsheet shortcuts, bounded batch input, and explicit
  error/exit contracts.
- Added buffered workbook operations, observed layout recipes, workbook
  snapshots, and rich XLSX image operations backed by existing Excelize
  capabilities. Rich authoring is provider-qualified; OfficeCLI never authors
  XLSX.
- Added optional neutral artifact contracts and the OfficeCLI adapter for native
  DOCX/PPTX table snapshots. HTML/PNG/view/watch paths remain capability-gated
  until a qualified renderer runtime is configured.
- Added the optional `open-table-connector-mcp` package with the typed
  `otc_discover`, `otc_inspect`, and `otc_execute` stdio tools and fail-closed
  deployment policy.
- Added `spreadsheet.workbook.copy/1.0`: `Client.copy_workbook` opens a session on a provider copy of a source workbook, rebinds to the document the provider allocates, and fails closed when the copy capability is not advertised.
- Completed critical-review correctness, safety, conformance, and packaging remediation.
- Finalized the OTC Python SDK architecture around `Client`, physical `Table`,
  `Query`, and Polars `DataFrame`, with normalized `base-mode` and
  `sheet-mode` terminology.
- Documented the three SQL lanes: relational SQL lite, temporal SQL lite, and
  explicit provider-native SQL, with SQLGlot as the policy layer and DuckDB
  kept as a future-only local executor option.
- Clarified that the `otc` CLI is a thin SDK wrapper and that the Rust/OTS
  bridge is deferred behind a separate adapter seam.

## [0.1.0] - 2026-08-31

- Initial workspace distribution surfaces and connector contracts.
