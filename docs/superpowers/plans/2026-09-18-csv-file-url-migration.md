# CSV File URL Connector Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire the public CSV-specific connector route and make local CSV operations use canonical `file://` URLs, while preserving CSV as a supported file format and preserving the already-landed MaybeSheet HTTPS and Excel file-URL behavior.

**Architecture:** `LocalFilesConnector` is the sole public local-file connector surface. CSV remains an internal codec/format implementation and continues to support CSV reads, writes, conversion, and managed `managed+csv://` snapshots. Explicit local CSV requests resolve through `file://`; the CSV-specific CLI adapter, plugin, and entry point are removed. Direct CSV temporal sources and SDK-created physical targets also use `file://`.

**Tech Stack:** Python, `TableURI`, connector capability manifests, setuptools entry points, pytest, Ruff, mypy, and the repository’s conformance suites.

**Spec:** [docs/superpowers/specs/2026-09-18-file-url-connector-surface-design.md](/Users/admin/Code/GitHub/open-table-connector/docs/superpowers/specs/2026-09-18-file-url-connector-surface-design.md)

## Global Constraints

- Start implementation from the fetched `origin/main` commit `a4dc909ce80a0a524aa12b105338a40fa822cae7`, or rebase the implementation branch onto it after protecting the user’s existing `.gitignore` edit. Do not discard the existing untracked files or unrelated changes.
- Keep `PROVIDER_CSV` as the format/codec identity and keep `managed+csv://` as an internal managed-snapshot namespace. Remove only the public direct CSV-specific route.
- `MaybeSheetCliAdapter` remains HTTPS-only with canonical `https://www.maybe.ai/docs/spreadsheets/d/<document>` URLs. Do not reintroduce MaybeSheet- or Excel-specific URI schemes or a CSV-specific public route.
- Preserve bare-path and format-based CSV CLI workflows, including `--from-format csv`, `--output-format csv`, stdin/stdout conversion, and local CSV reads/writes.
- Use test-first changes: add or update a regression test, run it and record the expected failure, then make the smallest implementation change and rerun it.
- Do not use a global replacement for the CSV-specific scheme literal; distinguish retired direct routes from intentional `managed+csv://` references.

## Remote Baseline

The remote refresh confirmed that commit `7306105` already removed `SCHEME_MAYBE`, the MaybeSheet opaque URI handling, and the Excel CLI adapter/entry point. The remaining direct provider-specific route is CSV. The work below is therefore intentionally limited to the CSV route and its affected contracts, temporal plumbing, tests, documentation, and project memory.

## File Map

- CSV connector and local routing: `packages/local_files/src/open_table_connector/local_files/csv_connector.py`, `local_files_connector.py`
- CLI surface and packaging: `packages/local_files/src/open_table_connector/local_files/cli_adapter.py`, `plugin.py`, `__init__.py`, `packages/local_files/pyproject.toml`, `packages/cli/src/open_table_connector/cli/adapters.py`
- URI and temporal plumbing: `packages/contract/src/open_table_connector/contract/adapters.py`, `packages/local_files/src/open_table_connector/local_files/temporal_csv.py`, `sdk_temporal.py`, `packages/process/src/open_table_connector/process/bootstrap.py`
- Tests and conformance: `packages/local_files/tests/`, `packages/cli/tests/`, `packages/contract/tests/`, `specification/conformance/universal/`
- Documentation and durable project guidance: `README.md`, `docs/`, `packages/cli/README.md`, `packages/sdk/README.md`, `AGENTS.md`

---

## Task 1: Make the CSV connector and local delegation file-URL based

**Files:**

- Modify `packages/local_files/src/open_table_connector/local_files/csv_connector.py`
- Modify `packages/local_files/src/open_table_connector/local_files/local_files_connector.py`
- Modify `packages/local_files/tests/test_csv_connector.py`
- Extend the relevant CSV/local connector tests in `packages/local_files/tests/test_csv_reader.py` and `packages/local_files/tests/test_local_files_connector.py`

- [x] Add failing tests that require `CsvConnector`’s capability manifest to advertise `(SCHEME_FILE,)`, resolve a canonical `file://` URI, and preserve a `file://` URI in the resulting receipt or concrete request.
- [x] Add a regression test showing that `CsvConnector().resolve(...)` rejects a constructed retired CSV-scheme target as an unsupported/invalid public route rather than accepting it as CSV.
- [x] Run the focused connector tests and confirm the red failure is caused by the current CSV manifest/resolution scheme.
- [x] Change `CSV_CAPABILITY_MANIFEST` and `CsvConnector.resolve()` to use `SCHEME_FILE`; retain `CSV_CONNECTOR_IDENTITY` and `PROVIDER_CSV` for format identity and codec behavior.
- [x] Change `LocalFilesConnector`’s CSV concrete-request URI construction from `_explicit_uri(..., PROVIDER_CSV)` to a canonical `SCHEME_FILE` URI.
- [x] Rerun the focused tests and verify CSV inspection, reads, writes, projection, and error behavior still pass through the local-files implementation.
- [x] Commit the completed task as `refactor: route local csv through file urls`.

## Task 2: Remove the public CSV CLI adapter and endpoint while retaining CSV format workflows

**Files:**

- Modify `packages/local_files/src/open_table_connector/local_files/cli_adapter.py`
- Modify `packages/local_files/src/open_table_connector/local_files/plugin.py`
- Modify `packages/local_files/src/open_table_connector/local_files/__init__.py`
- Modify `packages/local_files/pyproject.toml`
- Modify `packages/cli/src/open_table_connector/cli/adapters.py`
- Modify `packages/local_files/tests/test_cli_adapter.py`, `packages/local_files/tests/test_cli_plugin.py`, `packages/cli/tests/test_local_format_adapters.py`, and `packages/cli/tests/test_formats.py`

- [x] Add or update failing CLI tests to assert that discovery has `local_files` and Markdown but no public `csv` adapter, that the CSV-specific scheme is not a registered endpoint, and that a `file://` CSV source still reads through `local_files`.
- [x] Add a format-workflow regression covering CSV conversion via a bare path or `file://` path so removing the endpoint does not remove `FormatName.CSV` support.
- [x] Run the CLI/local-files tests and confirm the expected failures expose the registered `CsvCliAdapter`, `csv_cli_plugin`, and CSV entry point.
- [x] Extract the shared generic text/codec CLI behavior currently supplied by `CsvCliAdapter` into a private local adapter base used by `MarkdownCliAdapter`; do not leave Markdown dependent on a public CSV adapter class.
- [x] Remove `CsvCliAdapter` and `csv_cli_plugin` from the public module exports, plugin registration, and `[project.entry-points."open_table_connector.cli_adapters"]` metadata. Keep the CSV process handler entry point because CSV remains a supported format and managed snapshot type.
- [x] Remove the legacy `CsvAdapter` compatibility mapping from `packages/cli/src/open_table_connector/cli/adapters.py`.
- [x] Remove `PROVIDER_CSV` from URI-to-CLI-adapter scheme dispatch while retaining CSV in the format-name map used by bare paths, stdin/stdout, and explicit format conversion.
- [x] Rerun the CLI tests and verify that `file://...csv` routes to `local_files`, Markdown remains discoverable, and CSV format conversion remains functional.
- [x] Commit the completed task as `refactor: remove csv cli route`.

## Task 3: Move direct temporal CSV sources and SDK targets to `file://`

**Files:**

- Modify `packages/local_files/src/open_table_connector/local_files/temporal_csv.py`
- Modify `packages/local_files/src/open_table_connector/local_files/sdk_temporal.py`
- Modify `packages/process/src/open_table_connector/process/bootstrap.py`
- Modify/add tests in `packages/local_files/tests/test_temporal_csv.py`, `packages/local_files/tests/test_sdk_temporal.py`, and `packages/process/tests/test_bootstrap_process.py`

- [x] Add failing temporal tests for a direct `TableURI(path.as_uri())` CSV source, rejection of the retired direct CSV scheme, and continued acceptance of `managed+csv://` snapshots.
- [x] Add a failing SDK test proving the physical CSV target produced by `_csv_uri()` is the canonical file URI and does not rewrite `file://` to the retired CSV scheme.
- [x] Add a failing process-bootstrap test proving configured direct CSV targets use `SCHEME_FILE` while the managed CSV scheme remains accepted.
- [x] Run the temporal/SDK/process tests and confirm the failures identify the direct-scheme branches and target map.
- [x] Change the direct branch in `CsvTemporalExecutor` to `SCHEME_FILE`; retain the managed branch and CSV format checks. Update the rejection message to name `file` and `managed+csv` targets.
- [x] Change `_csv_uri(path)` to return `TableURI(path.absolute().as_uri())`, retaining `PROVIDER_CSV` only for the resource format identity.
- [x] Change the process target-scheme map from `{PROVIDER_CSV, SCHEME_MANAGED_CSV}` to `{SCHEME_FILE, SCHEME_MANAGED_CSV}` and import `SCHEME_FILE`.
- [x] Rerun the focused tests, including path validation and recovery behavior, and verify no managed snapshot scheme was changed.
- [x] Commit the completed task as `refactor: use file urls for temporal csv`.

## Task 4: Align URI parsing, conformance, and regression coverage

**Files:**

- Modify `packages/contract/src/open_table_connector/contract/adapters.py`
- Modify `packages/contract/tests/test_adapters.py`, `packages/contract/tests/test_uri.py`, and `packages/local_files/tests/test_bounded_reader.py`
- Modify `specification/conformance/universal/cases.py`, `fixtures.py`, `test_cli_surface.py`, and `test_discovery.py` where direct CSV endpoint examples or expectations occur
- Update any remaining direct-CSV references in `packages/local_files/tests/` and `packages/cli/tests/` found by exhaustive search

- [x] Write failing parser/registry tests that treat the CSV-specific scheme as retired, while still recognizing `csv` as a format and `managed+csv://` as an internal managed target.
- [x] Convert direct CSV conformance fixtures and examples to `Path.as_uri()`/`file://` and update expected connector identities to `local_files` where discovery is testing the public route.
- [x] Preserve connector-level CSV cases where they test the internal CSV implementation, but give them canonical `file://` targets and a file-scheme capability manifest.
- [x] Run contract, local-files, CLI, and universal conformance tests; use each failure to close a specific stale direct-route expectation.
- [x] Remove `PROVIDER_CSV` only from the URI-specific fallback/endpoint parsing set in `contract/adapters.py`; do not remove the `AdapterFormat.CSV` enum or format parsing.
- [x] Add an exhaustive repository check that direct CSV-specific scheme references are gone from code, tests, user-facing docs, and conformance examples, allowing only intentional `managed+csv://` references and the explicit forbidden-scheme policy sentence in `AGENTS.md`. Also verify MaybeSheet- and Excel-specific scheme literals remain absent outside that policy sentence.
- [x] Commit the completed task as `test: enforce file url csv surface`.

## Task 5: Update documentation and durable project guidance

**Files:**

- Modify user-facing examples in `README.md`, `docs/getting-started/first-timeseries.md`, `docs/getting-started/quickstart.md`, `docs/reference/python-api.md`, `docs/user-guide/projects-and-config.md`, `docs/user-guide/resolution.md`, `docs/user-guide/use-cases.md`, `packages/cli/README.md`, `packages/sdk/README.md`, and `specification/conformance/universal/README.md`
- Update stale historical/specification/report references in `docs/superpowers/plans/2026-08-28-local-connector-types.md`, `2026-08-29-portable-time-series-storage.md`, `2026-08-31-config-driven-cli-adapters.md`, `docs/superpowers/specs/2026-08-28-local-connector-types-design.md`, `docs/superpowers/specs/2026-08-31-python-sdk-design.md`, and `task-6-report.md` when they contain direct retired CSV-scheme examples
- Append the exact project URL policy accepted by `scripts/check_url_literals.py` to the existing user-owned `AGENTS.md` without overwriting its current content.

- [x] Replace direct local CSV examples with canonical `file:///...` URLs or bare local paths according to the surrounding API, and explicitly label `managed+csv://` examples as internal managed storage where they remain.
- [x] Document that CSV is still a supported format/codec and conversion option even though its format-specific URI scheme is no longer a public connector endpoint.
- [x] Add or update the MaybeSheet wording to use canonical HTTPS URLs and avoid implying that a scheme-specific local connector is available.
- [x] Run the documentation/reference search and confirm no direct retired route is presented as supported.
- [x] Commit the completed task as `docs: document file url connector policy`.

## Task 6: Full verification and graph refresh

- [x] Run focused tests:

  ```bash
  uv run --frozen python -m pytest packages/local_files/tests/test_csv_connector.py packages/local_files/tests/test_csv_reader.py packages/local_files/tests/test_local_files_connector.py packages/local_files/tests/test_cli_plugin.py packages/cli/tests/test_local_format_adapters.py packages/contract/tests/test_adapters.py packages/contract/tests/test_uri.py -q
  ```

- [x] Run temporal and process coverage:

  ```bash
  uv run --frozen python -m pytest packages/local_files/tests/test_temporal_csv.py packages/local_files/tests/test_sdk_temporal.py packages/process/tests/test_bootstrap_process.py -q
  ```

- [x] Run the complete test suite with `uv run --frozen python -m pytest -q`.
- [x] Run the CI quality and package checks exactly as configured:

  ```bash
  uv run --frozen ruff check scripts specification/conformance/universal/test_package_boundaries.py
  uv run --frozen mypy scripts
  uv run --frozen python scripts/check_package_metadata.py
  uv run --frozen python scripts/check_package_boundaries.py
  uv run --frozen python scripts/check_canonical_literals.py
  uv run --frozen python scripts/check_package_independence.py --build
  uv run --frozen python -m pytest specification/conformance/timeseries/test_schema_parity.py -q
  uv run --frozen python -m pytest packages/cli/tests/test_provider_independence.py -q
  git diff --check
  ```
- [x] Run an exhaustive final search and inspect every match:

  ```bash
  rg -n --hidden --glob '!*.lock' --glob '!AGENTS.md' '(^|[^A-Za-z0-9_+])(csv|excel|xlsx|maybe)://' .
  rg -n 'Project URL policy:.*(csv|excel|xlsx|maybe)://' AGENTS.md
  ```

  The first command must show only intentional `managed+csv://`/`managed+xlsx://` internal-storage references; direct CSV-, Excel-, and MaybeSheet-specific public scheme literals must be absent. The second command should show only the one explicit policy line. Preserve any remote-baseline internal managed schemes unless a test proves they are public routes.
- [x] Run `graft build` to refresh the repository context graph after the implementation changes.
- [x] Review `git diff`, `git status`, and the final test output. Confirm the pre-existing `.gitignore` edit and unrelated untracked user files remain untouched.
- [x] Before claiming completion, apply `superpowers:verification-before-completion` and report the exact verification results.

## Completion Criteria

- A CSV-specific URI scheme is not accepted, advertised, registered, documented, or emitted as a public direct local route.
- Canonical `file://` CSV sources resolve through `LocalFilesConnector` and work for reads, writes, inspection, temporal execution, and SDK physical targets.
- CSV remains available as a format and codec, and `managed+csv://` snapshot behavior remains intact.
- MaybeSheet continues to use canonical HTTPS document URLs, and the remote-main Excel changes remain intact.
- Focused tests, full tests, lint/type checks, package checks, exhaustive scheme search, and `graft build` all complete successfully.
