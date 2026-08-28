# Task 8 Report

Date: 2026-08-28

## Scope

Final review fix round 1 changed only universal tests, test fixtures, and SDD
documentation. It did not change production CLI or connector code. The round:

- added a hand-written literal metadata matrix for all seven connectors and
  compared connector ID/version, contract version, capability ID/version,
  modes, and schemes field by field;
- removed known Google Sheets, Feishu, and MaybeSheet credentials from the
  universal test environment and passed explicit sanitized environments to
  every real universal subprocess;
- made the MaybeSheet timeout test inspect the subprocess boundary, injected
  secret-bearing timeout diagnostics, and asserted the exact safe public error;
- asserted exact two-record MaybeSheet JSONL stdin bytes, including key order,
  compact separators, and the trailing newline;
- preserved and committed the two formula-negative tests supplied in the
  shared worktree; and
- corrected the Task 7 collection-determinism wording and final plan status.

## TDD Evidence

The focused red run seeded all three known provider credential variables in
the parent environment:

```bash
env GOOGLE_SHEETS_ACCESS_TOKEN=ambient-google \
  FEISHU_TENANT_ACCESS_TOKEN=ambient-feishu \
  MAYBESHEET_ACCESS_TOKEN=ambient-maybe \
  uv run python -m pytest \
  specification/conformance/universal/test_discovery.py::test_public_identity_and_manifest_match_literal_expectations \
  specification/conformance/universal/test_table_connectors.py::test_maybesheet_write_records_stdin_jsonl_argv_and_credential_locality \
  specification/conformance/universal/test_table_connectors.py::test_maybesheet_formula_operations_fail_closed \
  specification/conformance/universal/test_table_connectors.py::test_maybesheet_process_timeouts_map_to_safe_stable_errors -q
```

Result: exit 1, `1 failed, 10 passed in 0.27s`. The timeout test observed
`GOOGLE_SHEETS_ACCESS_TOKEN=ambient-google` and
`FEISHU_TENANT_ACCESS_TOKEN=ambient-feishu` in the subprocess environment,
in addition to its explicitly supplied MaybeSheet fixture token.

After adding test-side sanitization and explicit subprocess environments, the
seeded-ambient focused command, expanded to include both CLI subprocess tests
and the count guard, returned exit 0 with `14 passed in 1.49s`.

The complete affected-module command was:

```bash
uv run python -m pytest \
  specification/conformance/universal/test_discovery.py \
  specification/conformance/universal/test_table_connectors.py \
  specification/conformance/universal/test_cli_surface.py \
  specification/conformance/universal/test_suite_count.py -q
```

Result: exit 0, `154 passed in 2.61s`.

The literal metadata and exact JSONL assertions passed against existing
production behavior. They are field-level literal comparisons, so connector,
contract, capability, mode, scheme, key-order, separator, or trailing-newline
mutations fail without consulting the manifests/constants under test for the
expected values.

## Final Committed-Snapshot Verification

All commands below were run fresh from the final committed snapshot. Commands
that invoke a CLI subprocess used an environment with
`GOOGLE_SHEETS_ACCESS_TOKEN`, `FEISHU_TENANT_ACCESS_TOKEN`, and
`MAYBESHEET_ACCESS_TOKEN` explicitly absent.

- `uv sync --all-packages --group dev` — exit 0; `Resolved 28 packages`
  and `Checked 27 packages`.
- `uv lock --check` — exit 0; `Resolved 28 packages`.
- `uv run python -m pytest specification/conformance/universal --collect-only -q`
  — exit 0; `245 tests collected`.
- Repeated ordered-node-ID comparison using the same collect-only command —
  exit 0 with no diff.
- `uv run python -m pytest specification/conformance/universal -q` — exit 0;
  `245 passed`.
- `uv run python -m pytest -q` — exit 0; `432 passed`.
- `python3 -m compileall -q packages specification/conformance/universal` —
  exit 0 with no output.
- `git diff --check` — exit 0 with no output before commit.
- `uv build --all-packages` — exit 0. The final post-commit run built both
  sdist and wheel artifacts for all 11 workspace packages listed below.
- `uv run otc list --output-format jsonl` — exit 0 with four records:
  `google_sheets`, `feishu_bitable`, `maybesheet`, and `local_files`.
- `uv run otc --help` — exit 0; output begins `usage: otc`.
- `uv run open-table-connector --help` — exit 0; output begins
  `usage: otc`.
- `uv run open-connectors --help` — exit 0; output begins `usage: otc`.

## Build Artifacts

`uv build --all-packages` reported successful sdist and wheel builds for:

- `open_connectors_conformance-0.1.0`
- `open_connectors_contract-0.1.0`
- `open_connectors_dbt-0.1.0`
- `open_connectors_feishu_bitable-0.1.0`
- `open_connectors_google_sheets-0.1.0`
- `open_connectors_local_files-0.1.0`
- `open_connectors_maybesheet-0.1.0`
- `open_connectors_postgres-0.1.0`
- `open_connectors_sqlite-0.1.0`
- `open_table_connector-0.1.0`
- `open_table_connector_workspace-0.1.0`

Each package produced `.tar.gz` and `-py3-none-any.whl` artifacts. The
successful-build list above comes from this command's output; pre-existing
`dist/open_connectors_workspace-0.1.0*` files were not reported by the final
build and are not counted as final build evidence.

## Concerns

- The successful all-package build emits setuptools sdist warnings for the
  conformance, contract, dbt, local-files, MaybeSheet, Postgres, and SQLite
  packages because those package directories do not contain a standard README.
  Adding package READMEs is outside this test-only fix round.
- Release artifacts/tags and owner-supplied live-provider evidence remain
  outside this offline conformance plan.
- The pre-existing `.DS_Store` files and `tmp-review-universal/` remain
  untouched and untracked.
