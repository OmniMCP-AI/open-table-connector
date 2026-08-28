# Task 1 Report: Extract neutral Markdown codec and shared local format primitives

## Outcome

Implemented a neutral Markdown pipe-table codec in `packages/local_files`,
exported the shared primitives from the local-files package, taught local
format probing to detect Markdown payloads, and updated the CLI format layer to
delegate Markdown parsing and writing to the shared implementation.

## Files changed

- Created `packages/local_files/src/open_table_connector/local_files/markdown_reader.py`
- Modified `packages/local_files/src/open_table_connector/local_files/probe.py`
- Modified `packages/local_files/src/open_table_connector/local_files/__init__.py`
- Modified `packages/cli/src/open_table_connector/cli/formats.py`
- Created `packages/local_files/tests/test_markdown_reader.py`
- Modified `packages/local_files/tests/test_probe.py`

`packages/cli/tests/test_formats.py` was used as an existing behavior lock for
the CLI Markdown reader and writer and did not require changes.

## TDD log

### Red

Added the task-specified failing tests:

- `test_markdown_reader_round_trips_escaped_cells_and_hyphen_rows`
- `test_markdown_payload_requires_a_pipe_table_separator`
- `test_probe_detects_markdown`

Attempted the brief's exact command:

```bash
uv run pytest packages/local_files/tests/test_markdown_reader.py packages/local_files/tests/test_probe.py packages/cli/tests/test_formats.py -q
```

This environment failed before test execution because `uv run` could not spawn
the `pytest` executable:

```text
error: Failed to spawn: `pytest`
  Caused by: No such file or directory (os error 2)
```

Ran the equivalent command through the Python module entrypoint instead:

```bash
uv run python -m pytest packages/local_files/tests/test_markdown_reader.py packages/local_files/tests/test_probe.py packages/cli/tests/test_formats.py -q
```

Observed the expected red failure:

- `ModuleNotFoundError: No module named 'open_table_connector.local_files.markdown_reader'`

### Green

Implemented the neutral codec and probe updates:

- Moved Markdown row splitting, separator validation, unescaping, and writing
  into `markdown_reader.py`.
- Added `read_markdown_arrow(text: str, *, source: str) -> pyarrow.Table`.
- Added `write_markdown_table(headers, rows, stream)`.
- Added `is_markdown_payload(text: str) -> bool` with the required detection
  rules:
  - non-empty first row
  - valid separator second row
  - equal row widths
  - at least one pipe cell
- Added `LocalFormat.MARKDOWN = "md"`.
- Kept XLSX signature detection first and CSV delimiter detection second, then
  added Markdown probing afterward.
- Updated the CLI Markdown reader/writer to delegate to the shared local-files
  codec while preserving CLI error behavior and non-Markdown formats.

First focused green run exposed an unrelated regression caused by removing
`_normalize_table_cell`, which is still used by CSV reading. Restored that
helper and reran the focused suite.

## Verification

Focused suite:

```bash
uv run python -m pytest packages/local_files/tests/test_markdown_reader.py packages/local_files/tests/test_probe.py packages/cli/tests/test_formats.py -q
```

Result:

```text
22 passed in 0.61s
```

Full suite:

```bash
uv run python -m pytest -q
```

Result:

```text
438 passed in 9.75s
```

Additional diff hygiene:

```bash
git diff --check
```

Result: no whitespace or patch-format issues.

## Self-review

Reviewed the implementation diff after the full suite passed.

- The CLI no longer owns Markdown parsing or writing internals; it delegates to
  the neutral local-files codec.
- Local probing now recognizes Markdown without disturbing XLSX-first or
  CSV-before-Markdown detection order.
- Existing CLI Markdown behavior remains covered by the unchanged
  `packages/cli/tests/test_formats.py` cases, including escaped cells,
  separator-looking data rows, malformed widths, and empty cells.
- No additional concerns were found in the implementation diff.

## Notes

- The only deviation from the brief was using `uv run python -m pytest` instead
  of `uv run pytest` because the latter is not runnable in this environment.

## Fix Round 1

### What changed

- Tightened `is_markdown_payload()` so it now parses all non-empty rows and
  fails closed when any body row has a different column count than the header.
- Added a focused regression test for a valid header/separator followed by a
  short body row.

### Covering test files

- `packages/local_files/tests/test_markdown_reader.py`
- `packages/local_files/tests/test_probe.py`

### Exact command

```bash
uv run python -m pytest packages/local_files/tests/test_markdown_reader.py packages/local_files/tests/test_probe.py -q
```

### Output

Red:

```text
..F....                                                                  [100%]

=================================== FAILURES ===================================
_______ test_markdown_payload_rejects_body_rows_with_inconsistent_width ________

    def test_markdown_payload_rejects_body_rows_with_inconsistent_width() -> None:
>       assert is_markdown_payload("| id | note |\n| --- | --- |\n| 1 |\n") is False
E       AssertionError: assert True is False
E        +  where True = is_markdown_payload('| id | note |\n| --- | --- |\n| 1 |\n')

packages/local_files/tests/test_markdown_reader.py:27: AssertionError
=========================== short test summary info ============================
FAILED packages/local_files/tests/test_markdown_reader.py::test_markdown_payload_rejects_body_rows_with_inconsistent_width
1 failed, 6 passed in 1.27s
```

Green:

```text
.......                                                                  [100%]
7 passed in 0.46s
```
