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

- `open_table_connector_conformance-0.1.0`
- `open_table_connector_contract-0.1.0`
- `open_table_connector_dbt-0.1.0`
- `open_table_connector_feishu_bitable-0.1.0`
- `open_table_connector_google_sheets-0.1.0`
- `open_table_connector_local_files-0.1.0`
- `open_table_connector_maybesheet-0.1.0`
- `open_table_connector_postgres-0.1.0`
- `open_table_connector_sqlite-0.1.0`
- `open_table_connector-0.1.0`
- `open_table_connector_workspace-0.1.0`

Each package produced `.tar.gz` and `-py3-none-any.whl` artifacts. The
successful-build list above comes from this command's output; pre-existing
`dist/open_table_connector_workspace-0.1.0*` files were not reported by the final
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

## Final Review Fix Round 2

Date: 2026-08-28

Implementation commit:
`2922fb649b266f673a85761c5ea0fa1c09353a92` —
`fix: address final Feishu and CLI review findings`

### Scope and Root Causes

This separately authorized production round resolved all four Important final
review findings:

- `UrllibFeishuTransport` copied arbitrary `str(exc)` diagnostics into
  `safe_details["reason"]`. It now preserves the stable
  `execution_failed` code and `Feishu Bitable request failed` message while
  using the credential-safe reason `unexpected transport exception`.
- `_table_for_destination(...)` already honored an explicit destination-owned
  field policy, but the built-in `FeishuBitableAdapter` did not declare one.
  The adapter now declares `provider_owned_fields = ("_record_id",)`, so an
  exact Feishu-to-Feishu import POST omits only `_record_id` and retains user
  fields.
- Markdown parsing consumed an optional second-line separator correctly, then
  incorrectly filtered every separator-shaped body row. Body rows are now
  preserved after the optional separator position is handled.
- The universal README now requires `uv sync --all-packages --group dev` for a
  fresh checkout and uses `uv run --frozen` for collection and execution.

No URI grammar, provider payload mapping, write policy, receipt, or non-Feishu
pipeline behavior was changed.

### TDD Red/Green Evidence

Red command:

```bash
uv run --frozen python -m pytest \
  packages/feishu_bitable/tests/test_connector.py::test_feishu_transport_redacts_credentials_from_provider_errors \
  packages/cli/tests/test_pipeline.py::test_feishu_to_feishu_import_removes_destination_owned_record_id \
  packages/cli/tests/test_formats.py::test_markdown_table_writer_preserves_separator_looking_data_rows -q
```

Red result: exit `1`, `3 failed in 0.63s`. The diffs showed the injected
credential in Feishu `safe_details["reason"]`, `_record_id` in the destination
POST body, and an empty Markdown round trip instead of the literal
`{"a": "---", "b": "---"}` row.

The same command after the three minimal production changes returned exit `0`
with `3 passed in 0.40s`.

### Focused Regression Evidence

- Feishu connector plus CLI format/pipeline modules:
  `uv run --frozen python -m pytest packages/feishu_bitable/tests
  packages/cli/tests/test_pipeline.py packages/cli/tests/test_formats.py -q`
  — exit `0`, `46 passed in 0.73s`.
- Universal Feishu/CLI/count slice with all provider credential variables
  absent:

  ```bash
  env -u GOOGLE_SHEETS_ACCESS_TOKEN \
    -u FEISHU_TENANT_ACCESS_TOKEN \
    -u MAYBESHEET_ACCESS_TOKEN \
    uv run --frozen python -m pytest \
    specification/conformance/universal/test_table_connectors.py \
    specification/conformance/universal/test_cli_surface.py \
    specification/conformance/universal/test_suite_count.py -q
  ```

  Result: exit `0`, `109 passed in 2.50s`.
- Complete Feishu and CLI package tests:
  `uv run --frozen python -m pytest packages/feishu_bitable/tests
  packages/cli/tests -q` — exit `0`, `113 passed in 2.98s`.

### Fresh Setup and Final Verification

- `uv sync --all-packages --group dev` — exit `0`; `Resolved 28 packages in
  7ms`, `Checked 27 packages in 6ms`.
- `uv lock --check` — exit `0`; `Resolved 28 packages in 10ms`.
- Credential-isolated `uv run --frozen python -m pytest
  specification/conformance/universal --collect-only -q` — exit `0`; `245
  tests collected in 0.04s`, preserving the 120-test floor.
- Repeated ordered universal node-ID comparison — exit `0` with no diff.
- Credential-isolated `uv run --frozen python -m pytest
  specification/conformance/universal -q` — exit `0`; `245 passed in 3.84s`.
- Credential-isolated `uv run --frozen python -m pytest -q` — exit `0`; `435
  passed in 7.42s`.
- `python3 -m compileall -q packages specification/conformance/universal` —
  exit `0` with no output.
- `git diff --check` — exit `0` with no output before the implementation
  commit.
- `uv build --all-packages` — exit `0`; both sdist and wheel artifacts were
  successfully built for all 11 workspace packages listed in the prior build
  section.
- `uv run --frozen otc list --output-format jsonl` — exit `0` with exactly four
  records: `google_sheets`, `feishu_bitable`, `maybesheet`, and `local_files`.
- `uv run --frozen otc --help`, `uv run --frozen open-table-connector --help`,
  and `uv run --frozen open-connectors --help` — each exited `0` and began
  `usage: otc`.

### Concerns

- Arbitrary Feishu transport diagnostics are intentionally generic because
  provider exception text cannot be proven credential-free. Stable code and
  message details remain available, and normal Feishu provider response codes
  are unchanged.
- The successful build retains the pre-existing setuptools sdist warnings for
  workspace packages without package-level READMEs. Adding those READMEs is
  outside this round.
- Release artifacts/tags and owner-supplied live-provider evidence remain
  outside this offline review round.
- The pre-existing `.DS_Store` files and `tmp-review-universal/` remained
  untouched and untracked.
