# Task 6 Report

Date: 2026-08-28

## Implementation Commit

`12bd8c00ce1d98d55a12861bd0f6c33e59533479` —
`test: add universal cli and security matrix`

## Files Changed

- `specification/conformance/universal/test_cli_surface.py`
- `specification/conformance/universal/fixtures.py`
- `specification/conformance/universal/assertions.py`

No production CLI or connector implementation was changed.

## TDD Evidence

### Red

Command:

```bash
uv run python -m pytest specification/conformance/universal/test_cli_surface.py -q
```

Result:

```text
ERROR specification/conformance/universal/test_cli_surface.py
ImportError: cannot import name 'parse_csv_records' from
'specification.conformance.universal.assertions'
1 error in 0.56s
```

The expected collection failure demonstrated that the new matrix depended on
missing strict output parsers and case-to-CLI bridges before any helper
implementation was added.

The first post-bridge run produced `6 failed, 35 passed in 1.60s`. Those six
failures exposed incorrect test assumptions about closed `TableURI` wire
serialization, the intentionally base-only MaybeSheet CLI surface, and
deterministic JSONL key sorting. Expectations were corrected to the existing
public contracts without changing production code.

### Green

Command:

```bash
uv run python -m pytest specification/conformance/universal/test_cli_surface.py -q
```

Result:

```text
41 passed in 1.52s
```

## Coverage Added

- Registry discovery for every injected CLI adapter, including safe schemes,
  capabilities, and modes.
- `inspect --from` and default JSONL `read --from` behavior across local,
  Google Sheets, Feishu Bitable, and MaybeSheet case bridges.
- CSV, JSON, JSONL, and Markdown-table local conversion round trips, local
  inference, and explicit format overrides.
- Import source and destination receipts with exact source/destination adapter
  boundaries.
- Exact propagation of limit, timeout, conflict policy, sheet, range, selected
  fields, and target options into the owning recording transport/process or
  adapter.
- Provider format override rejection before I/O and stable unsupported scheme
  and capability exit codes.
- Strict JSON, JSONL, CSV, and aligned escaped Markdown parsing for truthful
  output assertions.
- Malformed input, authentication, conflict, and raw provider exception token
  redaction.
- Stdout codec ownership and repeated JSONL/table determinism.
- Two offline `uv run otc` subprocess checks for parser and entry-point
  behavior; all other coverage calls `run_command` with in-memory streams.

## Verification

- Baseline universal and CLI tests before changes:
  `uv run python -m pytest specification/conformance/universal packages/cli/tests -q`
  — `297 passed in 4.94s`.
- Focused Task 6 tests:
  `uv run python -m pytest specification/conformance/universal/test_cli_surface.py -q`
  — `41 passed in 1.52s`.
- All universal tests:
  `uv run python -m pytest specification/conformance/universal -q`
  — `232 passed in 2.89s`.
- CLI, format, import, parser, registry, and model regressions:
  `uv run python -m pytest packages/cli/tests/test_commands.py packages/cli/tests/test_formats.py packages/cli/tests/test_pipeline.py packages/cli/tests/test_cli_e2e.py packages/cli/tests/test_registry.py packages/cli/tests/test_model.py -q`
  — `106 passed in 3.18s`.
- Full workspace suite: `uv run python -m pytest -q`
  — `419 passed in 6.93s`.
- `uv run python -m compileall -q packages specification/conformance/universal`
  — passed.
- `git diff --check` — passed.

## Concerns

- The production CLI registry currently has adapters for local files, Google
  Sheets, Feishu Bitable, and MaybeSheet. SQLite, Postgres, and dbt remain
  covered by their universal connector suites but are not asserted as CLI
  discoveries because Task 6 explicitly forbids adding production adapters.
- JSONL output sorts object keys for deterministic bytes. JSONL conversion
  round trips therefore preserve the complete column set and row values, but
  not the original source column order; CSV, JSON, and table retain that order.
- CSV and Markdown tables represent null cells as empty text, so those codecs
  cannot distinguish a source null from a source empty string under current
  production behavior.
- The optional `uv run ruff check` command could not run because `ruff` is not
  installed in the workspace environment. All required focused, regression,
  workspace, compile, and diff gates completed successfully.
- Pre-existing untracked `.DS_Store` files and `tmp-review-universal/` were
  left untouched.
