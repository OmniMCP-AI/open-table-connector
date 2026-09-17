# CSV File URL Scope Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep CSV format/codec support while moving every CSV connector and managed-temporal target from retired scheme-specific URLs to canonical `file://` URLs.

**Architecture:** Preserve the existing CSV provider identity and codec boundaries. Make `file://` the only accepted URI scheme at the CSV connector and temporal executor boundaries, and make the managed CSV store use `file://` for both logical and physical targets while retaining `.csv` snapshot encoding.

**Tech Stack:** Python 3.14, pytest, pyarrow, polars, uv, graft.

**Spec:** `docs/superpowers/specs/2026-09-18-csv-file-url-scope-correction.md`

## Global Constraints

- `PROVIDER_CSV`, `AdapterFormat.CSV`, CSV parsing, CSV CLI format selection, CSV receipts, and `.csv` managed snapshot encoding remain supported.
- The `csv` scheme is not a supported connector URI; CSV connector and temporal execution accept canonical `file://` URIs only.
- The `managed+csv` scheme is removed; managed CSV logical and physical targets are canonical `file://` URIs.
- MaybeSheet remains HTTPS-only and no MaybeSheet-specific URI route is introduced.
- Retired schemes must be rejected before file I/O with the repository's normal error types.

---

### Task 1: Normalize CSV connector and temporal target schemes

**Files:**
- Modify: `packages/contract/src/open_table_connector/contract/names.py` and `packages/contract/src/open_table_connector/contract/__init__.py` to remove the retired managed-CSV scheme export while retaining `PROVIDER_CSV`.
- Modify: `packages/local_files/src/open_table_connector/local_files/temporal_csv.py` to configure managed snapshots with `SCHEME_FILE`, emit file targets, and reject every temporal target whose scheme is not `file`.
- Modify: `packages/local_files/src/open_table_connector/local_files/sdk_temporal.py` to replace the managed-CSV URI helper with canonical file URI construction and retain CSV format validation.
- Modify: `packages/process/src/open_table_connector/process/bootstrap.py` to allow only `file` targets for the CSV provider.
- Test: `packages/contract/tests/test_adapters.py`, `packages/local_files/tests/test_temporal_csv.py`, `packages/local_files/tests/test_sdk_temporal.py`, and `packages/process/tests/test_bootstrap_process.py`.

**Interfaces:**
- Consumes: Existing `CsvConnector`, `CsvTemporalExecutor`, `CsvManagedTemporalStore`, `LocalFilesSdkTemporalExtension`, and process bootstrap interfaces.
- Produces: CSV requests and managed temporal receipts whose URI values use `file://`; no public `SCHEME_MANAGED_CSV` symbol.

- [x] **Step 1: Write failing tests** asserting that managed CSV store targets, SDK logical/physical targets, and process bootstrap use `file://`, while both retired CSV schemes are rejected before I/O.
- [x] **Step 2: Run the focused tests** with `uv run pytest packages/contract/tests/test_adapters.py packages/local_files/tests/test_temporal_csv.py packages/local_files/tests/test_sdk_temporal.py packages/process/tests/test_bootstrap_process.py -q`; confirm the new assertions fail against the old managed scheme behavior.
- [x] **Step 3: Implement the minimal scheme normalization**: remove only the managed-scheme constant/export, set the managed snapshot target scheme to `SCHEME_FILE`, make both SDK URI helpers return `Path.absolute().as_uri()`, and narrow CSV temporal/bootstrap target checks to `SCHEME_FILE`.
- [x] **Step 4: Re-run the focused tests** and confirm all pass without changing CSV parsing, codec, receipt, or snapshot-extension behavior.
- [x] **Step 5: Commit** with `git add` on the contract/local-files/process files and tests, then `git commit -m "fix: use file URLs for managed CSV targets"`.

### Task 2: Align conformance, policy, and static URL checks

**Files:**
- Modify: `specification/conformance/timeseries/conftest.py`, `specification/conformance/timeseries/test_lifecycle_matrix.py`, and `specification/conformance/timeseries/test_process_e2e.py` to construct managed CSV targets with canonical file URLs and keep CSV lifecycle coverage.
- Modify: `scripts/check_url_literals.py` and its tests to remove the retired managed-CSV allowlist while retaining the existing exact project-policy exception for documenting retired public schemes.
- Modify: `AGENTS.md`, `docs/superpowers/specs/2026-09-18-file-url-connector-surface-design.md`, and `docs/superpowers/plans/2026-09-18-csv-file-url-migration.md` so they no longer claim that scheme-specific CSV URLs are preserved; state that CSV format/codec remains while both URI schemes are retired.
- Test: affected conformance and URL-literal test modules.

**Interfaces:**
- Consumes: Task 1's file-only CSV temporal boundary and retained CSV provider identity.
- Produces: Documentation, conformance fixtures, and static checks that agree on canonical file URLs.

- [x] **Step 1: Write failing assertions** for the absence of the managed-CSV scheme from conformance configuration and checker allowlists, and for retained CSV format coverage through file URLs.
- [x] **Step 2: Run the focused conformance/checker tests** and confirm failures identify the stale scheme-specific assumptions.
- [x] **Step 3: Update fixtures, checker rules, project policy, completed migration docs, and tests** without deleting CSV format/codec coverage.
- [x] **Step 4: Run the focused tests** for conformance and URL literals and confirm they pass.
- [x] **Step 5: Commit** with `git add` on the conformance, scripts, policy, specs, plans, and tests, then `git commit -m "docs: record CSV file URL scope correction"`.

### Task 3: Whole-branch verification and delivery

**Files:**
- Modify: Any files required by verification findings from Tasks 1–2.
- Test: Full repository test and quality-check commands.

**Interfaces:**
- Consumes: The complete file-URL CSV implementation and aligned repository policy.
- Produces: A verified branch ready to merge into remote `main`.

- [x] **Step 1: Search the graph exhaustively** for `SCHEME_MANAGED_CSV`, the `managed+csv` scheme, and scheme-specific CSV URI construction; resolve every remaining production reference.
- [x] **Step 2: Run the full suite** with `uv run pytest -q` and record the result: 1,632 passed, 5 skipped, 2 unrelated warnings.
- [x] **Step 3: Run repository quality checks**: Ruff, mypy scripts, metadata, package-boundary/independence checks, canonical-literal checks, URL-literal checks, schema parity, provider independence, and package build checks as defined by the repository CI workflow; all exited 0.
- [x] **Step 4: Rebuild graft** with `graft build`, then run the final graph search and inspect the diff for scope compliance.
- [x] **Step 5: Commit any verification fixes**, run the affected checks again, and commit with an appropriate `fix:` message; the pre-delivery physical-target validation fix was committed as `1578e3b` and verified by 37 focused tests plus the full suite.
- [x] **Step 6: Push the verified branch to remote `main`** using the repository's existing direct-main delivery convention, then verify `origin/main` points to the delivered commit.
