# Task 4 Report: Integrate CLI adapters, routing, and Excel output

## Status

Complete.

## Summary

- Added concrete CLI adapters for `csv`, `excel`, and `md` and registered them before the `local_files` compatibility adapter.
- Added an explicit CLI dependency on `open-table-connector-local-files` and updated `uv.lock`.
- Added `FormatName.EXCEL`, parser support for `--from-format excel` and `--to-format excel`, `.xlsx` inference, and explicit `csv://`, `excel://`, and `md://` format inference.
- Preserved `file://`, bare-path, and stdio compatibility through the existing local facade path.
- Made conversion treat `csv://`, `excel://`, and `md://` destinations as local destinations while import continues to reject them.
- Added neutral `write_excel(table, path, sheet)` in `packages/local_files`, backed by `openpyxl`.
- Preserved the `open-connectors` executable compatibility alias.

## Tests Added

- `packages/cli/tests/test_local_format_adapters.py`
  - Default registry lists `local_files`, `csv`, `excel`, and `md`.
  - Explicit local schemes route to concrete adapters.
  - Bare paths still route to the `local_files` facade.
  - CSV converts to explicit `md://` and `excel://` destinations.
  - Explicit destination schemes take precedence over `--to-format`.
  - Import rejects explicit local destinations before reading.
- `packages/local_files/tests/test_excel_writer.py`
  - Excel writer emits headers and rows to a named sheet.
  - Excel writer maps file write failures to `ConnectorErrorCode.EXECUTION_FAILED`.

## TDD Evidence

- Initial CLI red run:
  - `uv run python -m pytest packages/cli/tests/test_local_format_adapters.py -q`
  - Result: 6 failed, 2 passed, with failures for missing concrete identities, missing explicit scheme routes, and explicit local conversion rejection.
- Initial Excel writer red run:
  - `uv run python -m pytest packages/cli/tests/test_local_format_adapters.py packages/local_files/tests/test_excel_writer.py -q`
  - Result: collection failed because `open_table_connector.local_files.excel_writer` did not exist.
- Regression red run after self-review found format override precedence:
  - `uv run python -m pytest packages/cli/tests/test_local_format_adapters.py::test_explicit_local_destination_scheme_takes_precedence_over_to_format -q`
  - Result: failed because `md://...` with `to_format=JSON` wrote JSON instead of Markdown.

## Verification

- Focused new tests:
  - `uv run python -m pytest packages/cli/tests/test_local_format_adapters.py packages/local_files/tests/test_excel_writer.py -q`
  - Result: 11 passed.
- Task CLI slice and smoke commands:
  - `uv run python -m pytest packages/cli/tests/test_local_format_adapters.py packages/cli/tests/test_registry.py packages/cli/tests/test_pipeline.py packages/cli/tests/test_commands.py packages/cli/tests/test_cli_e2e.py -q && uv run otc --help >/tmp/otc-task4-help.txt && uv run otc list --output-format jsonl >/tmp/otc-task4-list.jsonl`
  - Result: 87 passed; both smoke commands exited 0.
- Full workspace suite:
  - `uv run python -m pytest -q`
  - Result: 478 passed.
- Diff hygiene:
  - `git diff --check`
  - Result: exit 0.
- Lock check:
  - `uv lock --check`
  - Result: exit 0.

## Tooling Note

The brief's exact `uv run pytest ...` form could not spawn `pytest` in this shell:

```text
error: Failed to spawn: `pytest`
  Caused by: No such file or directory (os error 2)
```

The equivalent workspace invocation `uv run python -m pytest ...` worked and was used for all test verification.

## Self-Review

- Confirmed concrete adapters use neutral local-files connector classes and manifests.
- Confirmed concrete adapters are registered before the compatibility adapter.
- Confirmed list output contains `csv`, `excel`, `md`, and `local_files`.
- Confirmed the compatibility `local_files` adapter retains its previous CLI list metadata in the universal conformance bridge.
- Confirmed local import rejection covers explicit local destination schemes.
- Confirmed no network or credential behavior was added.
- Confirmed unrelated untracked files were left untouched.

## Concerns

- None about the implementation.
- The local shell cannot execute the bare `uv run pytest` command form even though `uv run python -m pytest` works.

## Fix Round 1: Default Excel Sheet Regression

The review finding was addressed by adding `test_excel_writer_uses_default_sheet_name_and_writes_data` to `packages/local_files/tests/test_excel_writer.py`. The test calls `write_excel(table, destination)` without a sheet argument and asserts that the workbook contains the `Sheet1` worksheet with the expected headers and row values.

Covering test command and output:

```text
$ uv run python -m pytest packages/cli/tests/test_local_format_adapters.py packages/local_files/tests/test_excel_writer.py -q
............                                                             [100%]
12 passed in 1.15s
exit_code=0
```

Directly affected local-files test command and output:

```text
$ uv run python -m pytest packages/local_files/tests -q
...................................................                      [100%]
51 passed in 0.62s
exit_code=0
```

Directly affected CLI test command and output:

```text
$ uv run python -m pytest packages/cli/tests/test_local_format_adapters.py packages/cli/tests/test_registry.py packages/cli/tests/test_pipeline.py packages/cli/tests/test_commands.py packages/cli/tests/test_cli_e2e.py -q
........................................................................ [ 82%]
...............                                                          [100%]
87 passed in 3.58s
exit_code=0
```
