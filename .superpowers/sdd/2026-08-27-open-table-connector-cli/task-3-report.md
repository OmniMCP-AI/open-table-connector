# Task 3 Report

Status: complete

## Changed files

- `packages/maybesheet/src/open_connectors/maybesheet/process.py`
  - Added optional stdin to `ProcessClient` transport and passed it to `subprocess.run` as input.
- `packages/maybesheet/src/open_connectors/maybesheet/connector.py`
  - Implemented append-only `TableWriteRequest` handling with compact JSONL stdin, the specified `mbs db-table write` argv, safe policy validation, process error mapping, and neutral write receipts.
- `packages/maybesheet/src/open_connectors/maybesheet/identity.py`
  - Added `TABLE_WRITE_CAPABILITY`.
- `packages/maybesheet/src/open_connectors/maybesheet/__init__.py`
  - Exported `TABLE_WRITE_CAPABILITY`.
- `packages/maybesheet/tests/test_connector.py`
  - Added writer, policy rejection, and stdin transport coverage; updated the process test double for the compatible stdin parameter.

## Commits

- `feat: add maybesheet table writes`

## Tests

- `uv run python -m pytest packages/maybesheet/tests -q` — 7 passed.
- `git diff --check` — passed.

## Concerns

- The first test command could not start because pytest was not installed in the isolated environment; workspace dependencies and pytest were then installed before the focused suite was run.

## Deviations

- Unknown `if_exists` values are rejected as `INVALID_URI`; the specified `replace` and `error` values are rejected as `UNSUPPORTED_CAPABILITY`, both before process invocation.
