# Changelog

All notable changes to this project are documented here.

## [Unreleased]

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
