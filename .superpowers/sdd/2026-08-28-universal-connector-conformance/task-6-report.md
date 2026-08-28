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

This was collection/infrastructure red only: `parse_csv_records` was imported
before that assertion helper existed. It did not demonstrate a failing
production behavior or independently prove that the case-to-CLI bridges were
missing.

The first post-bridge run produced `6 failed, 35 passed in 1.60s`. Those six
failures exposed incorrect test assumptions about closed `TableURI` wire
serialization, the intentionally base-only MaybeSheet CLI surface, and
deterministic JSONL key sorting. They were expectation-calibration failures,
not behavioral red evidence. Expectations were corrected to the existing public
contracts without changing production code.

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

## Fix Round 1

Date: 2026-08-28

### Implementation Commit

`33ab76c` — `test: tighten universal cli conformance`

No production CLI or connector implementation was changed.

### Review Findings Addressed

- Every `inspect` case now runs through a four-adapter injected registry. The
  Google Sheets case uses a `docs.google.com` HTTPS URI while MaybeSheet uses a
  `www.maybe.ai` HTTPS URI; distinct provider facts and recording boundaries
  prove which adapter handled each request and that the other shared-HTTPS
  adapter did not run.
- Import output now asserts every public source and destination receipt field,
  including contract, connector and capability versions, operation and safe
  URI, mode, revision, schema/content fingerprints, coordinate convention,
  row/batch counts, and distinct non-null vendor receipt references. The
  summary's complete safe field set and source-receipt alias are also asserted.
- List discovery now compares complete ordered capability wire entries,
  including `capability_version`, and explicitly checks connector, capability,
  scheme, and mode uniqueness.
- Google `--sheet` and `--range` coverage now compares the exact two recorded
  requests, including method, full URL, authorization header, absent body,
  rounded timeout, and credential redaction from CLI output.
- `parse_csv_records` now rejects short rows whose missing cells are represented
  by `csv.DictReader` as `None`, while preserving the existing empty-text
  normalization.

### TDD Evidence

The first strengthened test-only run produced `18 failed, 24 passed`; 16 were
cascading setup failures because the new optional receipt-reference argument was
forwarded to every existing recording adapter. The test setup was narrowed
before implementation so only the intended gaps remained.

Red command:

```bash
uv run python -m pytest specification/conformance/universal/test_cli_surface.py -q
```

Actionable red result:

```text
2 failed, 40 passed in 1.40s
```

The failures were precise test-harness evidence: `RecordingCliAdapter` rejected
the new `vendor_receipt_ref` fixture input, and `parse_csv_records` did not raise
for a row shorter than its header. The strengthened shared-HTTPS dispatch,
discovery, and Google request-boundary assertions already passed against the
unchanged production CLI, so they did not provide behavioral red evidence.

Green result for the same command:

```text
42 passed in 1.18s
```

### Verification

- Focused Task 6 tests: `42 passed in 1.18s`.
- All universal tests: `237 passed in 4.11s`.
- CLI, format, import, parser, registry, and model regressions:
  `106 passed in 3.75s`.
- Full workspace suite: `424 passed in 6.93s`.
- `uv run python -m compileall -q packages specification/conformance/universal`
  — passed.
- `git diff --check` — passed.

### Fix-Round Concerns

- Concurrent unrelated changes to the universal-suite plan and table tests,
  plus untracked Task 7 files, `.DS_Store` files, and
  `tmp-review-universal/`, were left untouched and excluded from the
  implementation commit.
