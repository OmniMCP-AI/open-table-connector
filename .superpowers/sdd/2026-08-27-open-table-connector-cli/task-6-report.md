# Task 6 implementation report

## Status

Complete.

## Changed files

- `packages/cli/src/open_table_connector/cli/output.py`: structured JSONL/JSON/CSV/table read output, pipeline summaries, and credential-safe error output with plan exit-code mapping.
- `packages/cli/src/open_table_connector/cli/commands.py`: defensive `Namespace` handling, immutable `CliOptions` construction, and `list`/`inspect`/`read`/`convert`/`import` routing.
- `packages/cli/tests/test_commands.py`: focused JSONL read and safe authentication-error coverage.

## Commits

- `7074112 feat: add otc structured command output`

## Tests/results

- Focused: `2 passed` — `packages/cli/tests/test_commands.py`
- Existing CLI suite: `30 passed` — `packages/cli/tests`
- Python compilation: passed — `python -m compileall`
- `git diff --check`: passed

## Concerns

- The brief's sample authentication test asserts exit code 4, but the required global plan mapping assigns authentication exit code 3; implementation follows the required mapping.

## Deviations

- The prescribed `uv run pytest ...` command could not spawn `pytest` in this worktree environment. Equivalent checks ran successfully through `.venv/bin/python -m pytest` with the workspace package source paths on `PYTHONPATH`.

## Fix-round audit

### Status

Complete.

### Changes

- Corrected `EXIT_CODES` to the approved plan: invalid URI 2, unsupported capability 3, authentication 4, execution-family errors 5, and conflict 6.
- Mapped generic `OSError` and unexpected execution failures to exit 5 while retaining `ValueError` as exit 2.
- Updated authentication regression coverage to assert exit 4 and added focused execution/conflict safety coverage.

### Commit

- `b3489bd fix: align cli error exit codes`

### Tests/results

- Focused command tests: `5 passed` — `packages/cli/tests/test_commands.py`.
- Full CLI tests: `33 passed` — `packages/cli/tests`.
- `git diff --check`: passed.

### Concerns

- None beyond the environment deviation recorded above.

## Final-review fix round

### Status

Complete.

### Changes

- Convert-to-stdio now redirects pipeline codec writes to the supplied output stream and suppresses the completion summary, leaving JSON, JSONL, CSV, and table stdout valid.
- Added deterministic aligned Markdown-table rendering for `list`, `inspect`, and pipeline summaries when `--output-format table` is selected; read table output remains codec-backed.
- Preserved structured receipts in JSON/JSONL, stderr-only safe errors, approved exit codes, and JSONL row-event summaries for reads.
- Added focused coverage for all four convert-to-stdout codecs plus list, inspect, and conversion-summary table output.

### Commit

- `d6e5fab fix: keep cli streams codec-valid`

### Tests/results

- Focused command tests: `14 passed` — `packages/cli/tests/test_commands.py`.
- Command, pipeline, and e2e tests: `33 passed` when run with the worktree virtualenv on `PATH` (the e2e subprocess aliases require this).
- Full CLI suite: `60 passed`.
- `git diff --check`: passed.

### Concerns

- No implementation concerns. The prescribed `uv run pytest` environment still cannot spawn `pytest`; equivalent `.venv/bin/python -m pytest` verification was used, with `.venv/bin` added to `PATH` for alias-based e2e tests.

## Final re-review fix round

### Status

Complete.

### Changes

- Routed list, inspect, import summaries, and convert summaries through truthful JSONL, JSON, CSV, and table emitters.
- JSON list output is one array document; JSON inspect/summary output is one object document; CSV paths emit valid headers and rows.
- Preserved read row-event/summary semantics, aligned table output, codec-valid convert-to-stdio suppression, structured safe receipts, and safe stderr errors.
- Added focused validity tests for list/inspect/import JSON and CSV output, while retaining table and all convert-to-stdio codec tests.
- Added defensive JSONL defaults when focused command namespaces omit optional output-format fields.

### Commit

- `cf80a7e fix: honor cli output formats`

### Tests/results

- Focused command tests: `21 passed` — `packages/cli/tests/test_commands.py`.
- Command, pipeline, and e2e tests: `50 passed`.
- Full CLI suite: `85 passed`.
- `git diff --check`: passed.

### Concerns

- No implementation concerns. As in prior rounds, `uv run pytest` cannot spawn `pytest` in this environment; equivalent `.venv/bin/python -m pytest` verification was used, with `.venv/bin` on `PATH` for alias-based e2e tests.

## Strict JSON/JSONL serialization fix

### Status

Complete. CLI read output and local JSON/JSONL conversion now normalize
non-finite floats to `null`, serialize Arrow-derived dates, timestamps, and
decimals using contract-compatible strings, and recursively normalize nested
values. All machine-readable writers use `allow_nan=False` as a strict syntax
backstop.

### Changed files

- `packages/cli/src/open_table_connector/cli/output.py`
- `packages/cli/src/open_table_connector/cli/formats.py`
- `packages/cli/tests/test_commands.py`
- `packages/cli/tests/test_formats.py`

### Tests/results

- Red phase: focused JSON/JSONL regression selection failed **4 tests** for
  bare `NaN` output and unsupported Arrow-derived date serialization.
- Focused output/format tests: **34 passed**.
- Full workspace suite: **179 passed**.
- `git diff --check`: passed.
- `python -m compileall -q packages/cli/src`: passed.

### Commit

- This report is included with `fix: emit strict cli json`.

## Human-readable table escaping fix

### Status

Complete. Local table conversion and command table output now share one
aligned Markdown renderer. It escapes pipes and backslashes, renders embedded
line breaks as visible `\\n`, and calculates column widths after escaping.
CSV, JSON, JSONL, and existing headers are unchanged.

### Tests/results

- Red phase: both focused special-character regressions failed against the
  previous divergent renderers.
- Focused format/command tests: **36 passed**.
- Full CLI suite: **103 passed**.
- Full workspace suite: **181 passed**.
- `git diff --check` and CLI source compilation: passed.

### Commit

- This report is included with `fix: safely render cli tables`.
