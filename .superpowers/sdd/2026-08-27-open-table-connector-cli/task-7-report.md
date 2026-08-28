# Task 7 report

## Status

Complete. Added the executable argparse entrypoint, package exports, subprocess end-to-end coverage, and CLI documentation.

## Changed files

- `packages/cli/src/open_table_connector/cli/__main__.py`
  - Added `build_parser()` and `main(argv)`.
  - Added `list`, `inspect`, `read`, `convert`, and `import` subcommands.
  - Added explicit `--from`/`--to` destinations, all requested options, repeated `--field-name`, environment resolution through `build_default_registry`, parser exit handling, flushing, and the module guard.
- `packages/cli/src/open_table_connector/cli/__init__.py`
  - Exported `build_parser` and `main`.
- `packages/cli/tests/test_cli_e2e.py`
  - Added missing-endpoint parser, CSV-to-JSONL subprocess, and module/alias help tests.
- `packages/cli/README.md`
  - Added CLI examples and marked `open-connectors` as deprecated.
- `README.md`
  - Added CLI usage and compatibility-alias documentation.

## Commit

- `3a180dbfb14998b71f0f81d19c8772392c72f288` — `feat: expose otc command line interface`

## Tests and results

- `uv run python -m pytest packages/cli/tests -q` — 36 passed.
- `uv run python -m pytest packages/cli/tests/test_cli_e2e.py -q` — 3 passed.
- `uv run otc --help` — exit 0.
- `uv run open-table-connector --help` — exit 0.
- `uv run open-connectors --help` — exit 0.
- `git diff --check` — passed before commit.

## Concerns

- The prescribed `uv run pytest packages/cli/tests/test_cli_e2e.py -q` command could not spawn because this environment has pytest importable but no `pytest` executable. The equivalent `uv run python -m pytest` commands pass.

## Deviations

- The brief’s two sample tests were supplemented with one help-alias test covering module invocation and all three installed aliases.

## Fix round: JSONL read default

### Status

Complete. Changed the parser’s `--output-format` default from `None` to `jsonl`, so reads without an explicit output format produce JSONL rows followed by the completion summary.

### Changed files

- `packages/cli/src/open_table_connector/cli/__main__.py` — parser default is now `jsonl`.
- `packages/cli/tests/test_cli_e2e.py` — added module and `otc` subprocess regression coverage for default JSONL row and summary output.

### Commit

- `41f0cfca05d8ebf3cfb861909859a61bcd2ab0a9` — `fix: default cli reads to jsonl`

### Tests and results

- `uv run python -m pytest packages/cli/tests/test_cli_e2e.py -q` — 4 passed.
- `uv run python -m pytest packages/cli/tests -q` — 37 passed.
- `uv run otc --help` — exit 0.
- `uv run open-table-connector --help` — exit 0.
- `uv run open-connectors --help` — exit 0.
- `git diff --check` — passed before commit.

### Concerns

- The prescribed `uv run pytest ...` executable form remains unavailable in this environment; pytest is available and passing through `uv run python -m pytest`.

### Deviations

- None. Explicit output formats remain accepted; only the omitted read output format default changed.

## Fix round: list output-format compatibility

### Status

Complete. The `list` subparser now accepts `--output-format` with the standard format choices and defaults it to `jsonl`, without adding endpoint requirements or changing list output.

### Changed files

- `packages/cli/src/open_table_connector/cli/__main__.py` — added `list --output-format` with `_FORMATS` choices and a `jsonl` default.
- `packages/cli/tests/test_cli_e2e.py` — added an `otc list --output-format jsonl` subprocess regression asserting clean JSONL connector records.

### Commit

- `2acfecc4384e3b7f3677ba2bcb64d4cfc2511bb7` — `fix: accept list output format`

### Tests and results

- `uv run python -m pytest packages/cli/tests/test_cli_e2e.py -q` — 5 passed.
- `uv run python -m pytest packages/cli/tests -q` — 45 passed.
- `uv run otc list --output-format jsonl` — exit 0 with non-empty JSONL output and no stderr.
- `uv run otc --help` — exit 0.
- `uv run open-table-connector --help` — exit 0.
- `uv run open-connectors --help` — exit 0.
- `git diff --check` — passed before commit.

### Concerns

- The prescribed `uv run pytest ...` executable form remains unavailable in this environment; equivalent `uv run python -m pytest` commands pass.

### Deviations

- None. No workspace metadata or lockfiles were modified.

## Final-review fix round: output format choices

### Status

Complete. Restricted `--output-format` to `csv`, `json`, `jsonl`, and `table` for list, inspect, read, convert, and import. Input format flags continue to accept `auto`; JSONL remains the default output, and list still requires no endpoints.

### Changed files

- `packages/cli/src/open_table_connector/cli/__main__.py` — added separate output-format choices and applied them to list and the shared operation options.
- `packages/cli/tests/test_cli_e2e.py` — added subprocess coverage asserting `--output-format auto` is rejected with exit code 2; retained list JSONL smoke coverage.

### Commit

- `552767d57f5d57db8141b6d11a2e7e6f37c964d7` — `fix: restrict cli output formats`

### Tests and results

- `uv run python -m pytest packages/cli/tests/test_cli_e2e.py -q` — 6 passed.
- `uv run python -m pytest packages/cli/tests -q` — 72 passed.
- `uv run otc list --output-format jsonl` — exit 0 with non-empty JSONL output.
- `uv run otc --help` — exit 0.
- `uv run open-table-connector --help` — exit 0.
- `uv run open-connectors --help` — exit 0.
- `git diff --check` — passed before commit.

### Concerns

- The prescribed `uv run pytest ...` executable form remains unavailable in this environment; equivalent `uv run python -m pytest` commands pass.

### Deviations

- None. No final workspace metadata or lockfile was modified.

## Final-review fix round: machine-readable parser errors

### Status

Complete. Added a custom argparse error seam so parser failures return exit code 2 and emit exactly one sanitized JSON error object on stderr. Safe diagnostics retain recognized flags and known values such as missing `--to` and invalid output format `auto`; arbitrary input values are not serialized. Normal help remains successful, and list JSONL behavior is unchanged.

### Changed files

- `packages/cli/src/open_table_connector/cli/__main__.py` — added custom parser errors, allowlisted parser context extraction, and one-line JSON usage diagnostics.
- `packages/cli/tests/test_cli_e2e.py` — updated missing-destination and invalid-output-format subprocess tests to validate JSON shape, single-line stderr, safe context, and token redaction.

### Commit

- `41e67950602f6b344ea5d1b2fd172fa28566eb30` — `fix: emit json parser diagnostics`

### Tests and results

- `uv run python -m pytest packages/cli/tests/test_cli_e2e.py -q` — 6 passed.
- `uv run python -m pytest packages/cli/tests -q` — 79 passed.
- `uv run otc list --output-format jsonl` — exit 0 with non-empty JSONL output.
- `uv run otc --help` — exit 0.
- `uv run open-table-connector --help` — exit 0.
- `uv run open-connectors --help` — exit 0.
- `git diff --check` — passed before commit.

### Concerns

- The prescribed `uv run pytest ...` executable form remains unavailable in this environment; equivalent `uv run python -m pytest` commands pass.

### Deviations

- None. No workspace metadata, final metadata, or lockfile was modified.

## Follow-up fix: MaybeSheet row-limit enforcement

### Status

Complete. MaybeSheet now slices over-returned process payloads to the requested row limit before receipt fingerprints and counts are calculated, so direct reads and imports stay limited with truthful receipts. Other provider, endpoint, and output behavior is unchanged.

### Tests and results

- TDD regression check before the fix — 2 expected failures for direct read and import over-returning-process cases.
- `uv run python -m pytest packages/maybesheet/tests packages/cli/tests packages/contract/tests -q` — 125 passed.
- `uv run python -m pytest -q` — 167 passed.
- `uv run python -m compileall -q packages` — passed.
- `git diff --check` — passed.

### Workspace note

- A later full-suite rerun encountered four failures from concurrent, unstaged JSON-formatting tests in `test_commands.py` and `test_formats.py`; those files are outside this fix and remain uncommitted. With those two unrelated files excluded, the fresh workspace run passed 137 tests, including all focused MaybeSheet/import regressions.
