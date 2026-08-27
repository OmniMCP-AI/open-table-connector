# Task 2 Report

## Changed Files

- `packages/cli/src/open_connectors/cli/formats.py`
- `packages/cli/src/open_connectors/cli/__init__.py`
- `packages/cli/tests/test_formats.py`

## Commit

- `e47c065` - `feat: add otc table format codecs`

## Tests

- Command:
  `PYTHONPATH=packages/cli/src:packages/contract/src uv run --with pytest --with pyarrow --with polars python3 -m pytest packages/cli/tests/test_formats.py -q`
- Output:
  `7 passed in 0.39s`

## Concerns

- The test environment needed explicit `PYTHONPATH` plus on-demand `pytest`, `pyarrow`, and `polars` provisioning for the focused run; the code itself passed once those pieces were present.
- `infer_format` is suffix-based for local paths and intentionally leaves connector URIs and non-matching paths unchanged when `explicit` is `auto`.

## Fix Round

### Findings

- `read_local` accepted a malformed Markdown separator row with the wrong column count because the optional separator row was stripped before width validation.
- Separator detection was too broad and treated some colon/dash-only rows as separator rows even when they did not match the intended `:?-+:?` grammar.
- The Task 2 suite lacked focused malformed Markdown regression coverage for both the width mismatch and the invalid separator grammar path.

### Changed Files

- `packages/cli/src/open_connectors/cli/formats.py`
- `packages/cli/tests/test_formats.py`

### Commit

- `b8f4597` - `fix: tighten markdown table separator parsing`

### Tests

- Command:
  `PYTHONPATH=packages/cli/src:packages/contract/src uv run --with pytest --with pyarrow --with polars python3 -m pytest packages/cli/tests/test_formats.py -q`
- Output:
  `9 passed in 0.38s`

### Concerns

- The focused verification still relies on the ad hoc `PYTHONPATH` plus transient `pytest`/`pyarrow`/`polars` provisioning in this workspace.

## Markdown table round-trip fix

### Changes

- Made Markdown row splitting escape-aware and decoded the writer's `\|`, `\\`, and `\n` cell representations.
- Added writer-to-reader regression cases for pipes, backslashes, and embedded newlines while retaining separator/header parsing and column-count diagnostics.

### Tests/results

- Red phase: all **3** new round-trip cases failed against the raw pipe splitter.
- Focused format tests: **15 passed**.
- Full CLI suite: **106 passed**.
- Full workspace suite: **186 passed**.
- CLI source compilation and `git diff --check`: passed.

### Commit

- This report is included with `fix: round-trip markdown table escapes`.
