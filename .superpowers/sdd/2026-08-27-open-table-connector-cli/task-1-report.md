# Task 1 Implementation Report

## Outcome

Task 1 is complete.

## Commit

- `c119226` - `feat: scaffold open table connector cli`

## Files changed

- `pyproject.toml`
- `uv.lock`
- `packages/cli/README.md`
- `packages/cli/pyproject.toml`
- `packages/cli/src/open_connectors/cli/__init__.py`
- `packages/cli/src/open_connectors/cli/model.py`
- `packages/cli/tests/test_model.py`

## What changed

- Added the `packages/cli` workspace member and synced the workspace lockfile.
- Created the CLI package metadata with the three console-script aliases.
- Added the shared CLI model layer:
  - `Endpoint`
  - `FormatName`
  - `CliOptions`
  - `PipelineSummary`
  - `parse_endpoint`
  - `parse_format`
- Added the model tests requested in the brief.
- Added a short package README explaining the scaffolded CLI package.

## Verification

Command:

```bash
uv sync --all-packages
```

Output:

```text
Resolved 28 packages in 7ms
   Building open-connectors-cli @ file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/cli
      Built open-connectors-cli @ file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/cli
Prepared 1 package in 806ms
Installed 1 package in 4ms
 + open-connectors-cli==0.1.0 (from file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/cli)
```

Command:

```bash
uv run pytest packages/cli/tests/test_model.py -q
```

Output:

```text
...                                                                      [100%]
3 passed in 0.44s
```

## Concerns

- The console-script targets are declared, but `open_connectors.cli.__main__` is not implemented yet. That is expected for this scaffold task and will need a follow-up task before the scripts are runnable.
- `PipelineSummary` is intentionally a lightweight value object for later orchestration work; downstream tasks may refine how receipts are populated.

## Round 1 Fix Report

### Outcome

Review feedback addressed.

### Commit

- `0319368` - `fix: address task 1 review feedback`

### Files changed

- `packages/cli/pyproject.toml`
- `packages/cli/README.md`
- `packages/cli/src/open_connectors/cli/model.py`
- `packages/cli/tests/test_model.py`
- `uv.lock`

### What changed

- Renamed the CLI distribution to `open-table-connector` while keeping the three console scripts.
- Updated `parse_endpoint` to treat Windows drive-letter paths like `C:\\tmp\\orders.csv` as local paths instead of URIs.
- Added a focused regression test for Windows drive-letter path parsing.
- Marked `open-connectors` as a deprecated compatibility alias in the README.
- Kept the console-script targets scoped to the current scaffold; `__main__.py` remains a later-task follow-up.

### Verification

Command:

```bash
uv sync --all-packages
```

Output:

```text
Resolved 28 packages in 7ms
   Building open-connectors-conformance @ file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/conformance
   Building open-connectors-contract @ file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/contract
   Building open-connectors-dbt @ file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/dbt
   Building open-connectors-feishu-bitable @ file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/feishu_bitable
   Building open-connectors-google-sheets @ file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/google_sheets
   Building open-connectors-local-files @ file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/local_files
   Building open-connectors-maybesheet @ file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/maybesheet
   Building open-connectors-postgres @ file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/postgres
   Building open-connectors-sqlite @ file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/sqlite
   Building open-table-connector @ file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/cli
      Built open-table-connector @ file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/cli
      Built open-connectors-sqlite @ file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/sqlite
      Built open-connectors-feishu-bitable @ file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/feishu_bitable
      Built open-connectors-postgres @ file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/postgres
      Built open-connectors-dbt @ file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/dbt
      Built open-connectors-conformance @ file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/conformance
      Built open-connectors-local-files @ file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/local_files
      Built open-connectors-maybesheet @ file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/maybesheet
      Built open-connectors-google-sheets @ file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/google_sheets
      Built open-connectors-contract @ file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/contract
Prepared 10 packages in 1.96s
Uninstalled 10 packages in 13ms
Installed 10 packages in 9ms
 - open-connectors-cli==0.1.0 (from file:///Users/admin/Code/GitHub/open-connectors/.worktrees/otc-cli/packages/cli)
 - open-connectors-conformance==0.1.0 (from file:///Users/admin/Code/GitHub/open-connectors/.worktrees/otc-cli/packages/conformance)
 + open-connectors-conformance==0.1.0 (from file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/conformance)
 - open-connectors-contract==0.1.0 (from file:///Users/admin/Code/GitHub/open-connectors/.worktrees/otc-cli/packages/contract)
 + open-connectors-contract==0.1.0 (from file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/contract)
 - open-connectors-dbt==0.1.0 (from file:///Users/admin/Code/GitHub/open-connectors/.worktrees/otc-cli/packages/dbt)
 + open-connectors-dbt==0.1.0 (from file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/dbt)
 - open-connectors-feishu-bitable==0.1.0 (from file:///Users/admin/Code/GitHub/open-connectors/.worktrees/otc-cli/packages/feishu_bitable)
 + open-connectors-feishu-bitable==0.1.0 (from file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/feishu_bitable)
 - open-connectors-google-sheets==0.1.0 (from file:///Users/admin/Code/GitHub/open-connectors/.worktrees/otc-cli/packages/google_sheets)
 + open-connectors-google-sheets==0.1.0 (from file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/google_sheets)
 - open-connectors-local-files==0.1.0 (from file:///Users/admin/Code/GitHub/open-connectors/.worktrees/otc-cli/packages/local_files)
 + open-connectors-local-files==0.1.0 (from file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/local_files)
 - open-connectors-maybesheet==0.1.0 (from file:///Users/admin/Code/GitHub/open-connectors/.worktrees/otc-cli/packages/maybesheet)
 + open-connectors-maybesheet==0.1.0 (from file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/maybesheet)
 - open-connectors-postgres==0.1.0 (from file:///Users/admin/Code/GitHub/open-connectors/.worktrees/otc-cli/packages/postgres)
 + open-connectors-postgres==0.1.0 (from file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/postgres)
 - open-connectors-sqlite==0.1.0 (from file:///Users/admin/Code/GitHub/open-connectors/.worktrees/otc-cli/packages/sqlite)
 + open-connectors-sqlite==0.1.0 (from file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/sqlite)
 + open-table-connector==0.1.0 (from file:///Users/admin/Code/GitHub/open-table-connectors/.worktrees/otc-cli/packages/cli)
```

Command:

```bash
uv run pytest packages/cli/tests/test_model.py -q
```

Output:

```text
error: Failed to spawn: `pytest`
  Caused by: No such file or directory (os error 2)
```

Command:

```bash
uv sync --all-packages --group dev
```

Output:

```text
Resolved 28 packages in 8ms
Checked 27 packages in 3ms
```

Command:

```bash
uv run python -m pytest packages/cli/tests/test_model.py -q
```

Output:

```text
....                                                                     [100%]
4 passed in 0.41s
```

### Concerns

- `open_connectors.cli.__main__` still needs the later task before the console scripts are runnable.
