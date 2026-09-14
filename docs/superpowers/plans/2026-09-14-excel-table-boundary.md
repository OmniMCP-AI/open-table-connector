# Excel table boundary implementation plan

> Use superpowers:executing-plans to execute task-by-task. User authorized implementation, commit and push in this session.

**Goal:** Let consumers use OTC tables for Excel data without building workbook codecs.
**Architecture:** A shared private lexical codec feeds existing range operations and local materialization; the existing workbook provider owns persistence.
**Tech Stack:** Python >=3.11,<3.15; Polars >=1,<2; existing OTC workbook provider.
**Spec:** ../specs/2026-09-14-excel-table-boundary-design.md

## Constraints

Preserve lexical RAW semantics and existing workbook effect evidence. No template engine, hidden schema, numeric inference, overwrite/append fallback or full-suite run.

## Task 1: Bounded workbook table operations

Files: `packages/sdk/src/open_table_connector/sdk/_excel_table.py`, `workbook.py`; `packages/local_files/tests/test_excel_table_materialize.py`.

- [x] Add regression tests for `sheet.range("A1:B3").write_table(frame)` and `.read_table().require_value()`; assert lexical DataFrame equality, literal formula text, exact shape rejection and preserved nulls.
- [x] Run `uv run --all-packages pytest packages/local_files/tests/test_excel_table_materialize.py -q` and observe missing API failure.
- [x] Implement private `table_matrix(frame, header=True)` / `matrix_table(values, header=True)` helpers and range methods using existing read/write results. Reject unsupported scalars and out-of-bounds shape before queueing.
- [x] Run targeted tests and lint; record results.

## Task 2: Local Excel materialization

Files: `packages/local_files/src/open_table_connector/local_files/sdk_excel_table.py`, `sdk_temporal.py`, `excel_reader.py`, `cli_adapter.py`; SDK `client.py`, `registry.py`; same tests. Route explicit worksheet file selectors and expose the existing native local SDK under plugin discovery. Preserve empty inline strings in the existing reader.

- [x] Add tests using `client.materialize(frame, to=f"file://{path}#sheet=Base")` and `result.require_value().read()`; cover create, add worksheet, case-insensitive conflict, unchanged unrelated content, invalid destination/value rejection and failed persisted readback.
- [x] Observe existing unsupported materialization failure.
- [x] Dispatch Excel DirectDestination to a private helper. Validate first, use workbook session to create/write table and commit, then use the connector's table reader to compare exact lexical DataFrame and return binding with combined receipts. Propagate failure effects after commit. Keep unsupported formats rejected.
- [x] Run new tests plus existing workbook/local Excel reader tests and lint. Review diff for conflict, precision and receipt regressions.

## Task 3: Documentation and delivery

- [x] Document both public APIs, lexical/null semantics and destination restrictions in SDK README; record targeted verification and check off only completed work here.
- [ ] Commit implementation/spec/plan/docs on `codex/excel-table-boundary`; push to origin. Do not merge without request.
- [ ] Return to FinClaw and write updated integration spec/plan referencing pushed OTC revision and remaining consumer work.

## Execution evidence — 2026-09-14

Baseline: `uv run --all-packages pytest packages/local_files/tests/test_spreadsheet_workbook.py packages/local_files/tests/test_excel_connector.py -q` — 11 passed.
Red: new table tests failed for missing Range table methods and absent materialization/routing.
Green: `uv run --all-packages pytest packages/local_files/tests/test_excel_table_materialize.py packages/local_files/tests/test_spreadsheet_workbook.py packages/local_files/tests/test_excel_connector.py packages/local_files/tests/test_excel_reader.py packages/local_files/tests/test_sdk_temporal.py packages/sdk/tests/test_registry.py packages/sdk/tests/test_client.py packages/sdk/tests/test_workbook_session.py -q` — 55 passed.
Provider regressions: `uv run --all-packages pytest packages/local_files/tests/test_spreadsheet_provider.py packages/local_files/tests/test_spreadsheet_verify.py packages/local_files/tests/test_cli_plugin.py -q` — 61 passed; expected duplicate-ZIP-member warning from corruption fixture.
Changed implementation/new test lint and `git diff --check` passed. Python 3.14.4. Repository-wide and other-Python suites were not run, per scoped verification instruction.

Self-review: default plugin discovery also needed native SDK selection, and string-form `Client.open` needed worksheet URI routing; both are included and exercised. Safe integers remain numeric for Excel aggregations; oversized integers stay exact text. Empty inline strings are preserved by the canonical reader. Literal-artifact profile restrictions are unchanged. No consumer-specific template or financial schema was added.
