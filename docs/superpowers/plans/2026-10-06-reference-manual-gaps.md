# Reference Manual Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the CLI, recipe, generic-dispatch, MCP-host, artifact-runtime, and reference-generation gaps so the complete manuals describe behavior that can be executed and verified.

**Architecture:** Preserve the existing SDK/session/result contracts. Make CLI shortcuts and generic operation dispatch enter the same buffered workbook write path, make recipe export observation-backed, inject an explicit MCP SDK host, and make OfficeCLI runtime state an explicit adapter capability. Generate exhaustive reference inventories from the parser/catalog/public exports, then write behavior manuals around those verified contracts.

**Tech Stack:** Python 3.11-3.14, argparse, pytest, Polars, Excelize-backed local provider, official MCP SDK/FastMCP, JSON/TOML contracts, Markdown generation.

**Spec:** `docs/superpowers/specs/2026-10-06-reference-manual-gaps-design.md`

## Global Constraints

- Local workbook and CSV paths use canonical `file://` URLs; MaybeSheet uses canonical HTTPS document URLs.
- Rich XLSX authoring uses existing Excelize capabilities only; OfficeCLI never authors authoritative XLSX.
- Preserve `OperationResult`, receipts, commit states, verification states, error codes, and existing exit-code mappings.
- Unsupported or unqualified capabilities fail closed before dispatch; remote partial/unknown effects remain explicit.
- Optional packages must remain removable from core help and SDK imports.
- Generated references are deterministic and checked in; CI uses `--check`.

## Review Focus

- A shortcut that parses but does not call `write()` must be rejected by persistence/reopen tests.
- Recipe selectors must not manufacture observations from request text; missing observations must fail or warn explicitly.
- Generic dispatch must not leave a staged session open or convert an unknown commit into success.
- MCP no-host startup must fail closed while a test host must execute through the same catalog as CLI.
- Renderer/browser absence must produce capability evidence, never synthetic HTML/PNG/watch success.

### Task 1: Make Spreadsheet Shortcuts Commit Through Workbook Sessions

**Files:**
- Modify: `packages/cli/src/open_table_connector/cli/spreadsheet_commands.py`
- Test: `packages/cli/tests/test_spreadsheet_commands.py`
- Test: `packages/cli/tests/test_spreadsheet_shortcuts.py`

**Interfaces:** `run_spreadsheet(args, registry, out, err) -> int` must route `style`, `format`, `write`, and `worksheet` through the same `WorkbookSession.write()` branch as `operation` and `batch`, preserving `ExecutionOptions` flags and result serialization.

- [x] **Step 1: Write failing CLI persistence tests**

Add tests for style, format, write, worksheet create/rename/delete that create a local workbook, invoke the parser/handler, reopen it, and assert the persisted cell/style/sheet change and `commit == "committed"`. Add dry-run assertions for unchanged bytes and `outcome == "planned"`.

- [x] **Step 2: Run the focused tests to verify failure**

Run: `uv run --all-packages pytest -q packages/cli/tests/test_spreadsheet_commands.py packages/cli/tests/test_spreadsheet_shortcuts.py`

Expected: the new persistence tests fail because shortcut actions currently return inspection output without committing.

- [x] **Step 3: Implement one-operation shortcut commit routing**

Update the action branch so `changes` from `_changes(args)` are queued and `book.write(...)` is called for `style`, `format`, `write`, and `worksheet`. Keep read/style-read/config-read/verify/inspect behavior unchanged. Ensure the output is the `OperationResult.to_wire()` from the write or dry-run.

- [x] **Step 4: Run focused tests and existing CLI tests**

Run the command from Step 2 plus `uv run --all-packages pytest -q packages/cli/tests/test_artifact_export.py packages/cli/tests/test_recipe_commands.py`.

Expected: all pass, including zero-dispatch validation and shortcut/generic request parity.

- [x] **Step 5: Commit the shortcut fix**

```bash
git add packages/cli/src/open_table_connector/cli/spreadsheet_commands.py packages/cli/tests/test_spreadsheet_commands.py packages/cli/tests/test_spreadsheet_shortcuts.py
git commit -m "fix: commit spreadsheet shortcut mutations"
```

### Task 2: Make Recipe Export Fresh, Observable, and Unambiguous

**Files:**
- Modify: `packages/cli/src/open_table_connector/cli/__main__.py` or `spreadsheet_commands.py`
- Modify: `packages/cli/src/open_table_connector/cli/recipe_commands.py`
- Modify: `packages/sdk/src/open_table_connector/sdk/recipes.py`
- Modify: `packages/spreadsheets/src/open_table_connector/spreadsheets/recipes.py`
- Test: `packages/cli/tests/test_recipe_commands.py`
- Test: `packages/sdk/tests/test_recipes.py`

**Interfaces:** Accept `otc spreadsheet recipe export --uri URI --selectors FILE [--allow-incomplete]` without positional ambiguity. `export_recipe(client, target, selectors, *, allow_incomplete=False)` must bind the target and return an `OperationResult[LayoutRecipe]` based on a fresh local snapshot/provider observation. `apply_recipe(...)` must close its session after commit or failure.

- [x] **Step 1: Write parser, freshness, and omission tests**

Add parser coverage for the exact command form and ambiguous forms. Add local tests that export a recipe only after creating a workbook, reject a missing/stale observation by default, report omissions with `allow_incomplete=True`, and prove exported operations contain no values/formulas/assets.

- [x] **Step 2: Run recipe tests to verify failure**

Run: `uv run --all-packages pytest -q packages/cli/tests/test_recipe_commands.py packages/sdk/tests/test_recipes.py`

Expected: parser export and fresh-observation tests fail against the current positional parser and selector-only implementation.

- [x] **Step 3: Fix parser ownership and target observation**

Give `recipe` a dedicated nested parser or normalize `export` before the shared positional choices are evaluated. In `export_recipe`, resolve the target through the client, capture a local `WorkbookSnapshot` or provider observation, validate each selector against that observation, and return explicit `OperationWarning` omissions only when allowed.

- [x] **Step 4: Harden apply lifecycle and recipe validation**

Ensure `apply_recipe` uses a context-managed workbook session or an explicit close/finalize path after `write()`; preserve committed/unknown receipts. Keep the schema’s forbidden keys and recomputed requirements checks.

- [x] **Step 5: Run recipe tests and commit**

Run the tests from Step 2 plus `uv run --all-packages pytest -q packages/spreadsheets/tests/test_recipes.py`.

Expected: all pass with no mutation on dry-run and no dispatch for unsupported selectors.

```bash
git add packages/cli/src/open_table_connector/cli/__main__.py packages/cli/src/open_table_connector/cli/spreadsheet_commands.py packages/cli/src/open_table_connector/cli/recipe_commands.py packages/sdk/src/open_table_connector/sdk/recipes.py packages/spreadsheets/src/open_table_connector/spreadsheets/recipes.py packages/cli/tests/test_recipe_commands.py packages/sdk/tests/test_recipes.py packages/spreadsheets/tests/test_recipes.py
git commit -m "fix: qualify spreadsheet recipe export and apply"
```

### Task 3: Close Generic Spreadsheet Operation Sessions Correctly

**Files:**
- Modify: `packages/sdk/src/open_table_connector/sdk/operations.py`
- Test: `packages/sdk/tests/test_operations.py`

**Interfaces:** `_builtin_spreadsheet_handler(client, request, options) -> OperationResult[object]` must close every workbook session and call `write()` for mutating operation IDs, passing `dry_run`, `allow_partial`, `expected_revision`, and `idempotency_key` from `ExecutionOptions`.

- [x] **Step 1: Write failing generic-dispatch tests**

Add tests for range write/style, worksheet create, dry-run, unsupported operation, stale revision, and a tracking provider that asserts session close occurs after committed, rejected, and unknown outcomes.

- [x] **Step 2: Run the focused tests to verify failure**

Run: `uv run --all-packages pytest -q packages/sdk/tests/test_operations.py`

Expected: mutation tests reject or leave bytes unchanged because the current handler returns `_rejected` for write operations and does not finalize sessions.

- [x] **Step 3: Implement explicit read/mutation operation routing**

Use a context-managed workbook access for each operation. Reads return observation results. Mutations queue exactly one change, invoke `book.write(...)` with `ExecutionOptions`, return the complete result, and close in `finally` without suppressing `OTCError` or uncertain receipts.

- [x] **Step 4: Run SDK operation and workbook suites**

Run: `uv run --all-packages pytest -q packages/sdk/tests/test_operations.py packages/sdk/tests/test_artifacts.py packages/sdk/tests/test_preview_sessions.py packages/local_files/tests/test_excelize_rich_workbook.py`.

- [x] **Step 5: Commit the dispatcher fix**

```bash
git add packages/sdk/src/open_table_connector/sdk/operations.py packages/sdk/tests/test_operations.py
git commit -m "fix: finalize generic spreadsheet operation sessions"
```

### Task 4: Add Explicit MCP SDK Host Wiring

**Files:**
- Modify: `packages/mcp/src/open_table_connector/mcp/server.py`
- Modify: `packages/mcp/src/open_table_connector/mcp/tools.py`
- Modify: `packages/mcp/src/open_table_connector/mcp/policy.py`
- Test: `packages/mcp/tests/test_tools.py`
- Test: `packages/mcp/tests/test_stdio.py`

**Interfaces:** `create_server(*, host: MpcHost | None = None, policy: AccessPolicy | None = None) -> FastMCP` accepts an explicit host exposing `client`. `otc_inspect` and `otc_execute` route through `execute_operation(host.client, request, ExecutionOptions)` after catalog and policy validation. `main()` remains fail-closed without `OTC_MCP_CONFIG` and may load a host from a deployment-owned adapter.

- [x] **Step 1: Write failing official-client and host tests**

Add a fake host with a local `Client`, verify official MCP initialize/list exposes exactly three tools, call `otc_discover`, call read-only `otc_inspect`, call typed local `otc_execute`, and assert no-host inspect/execute return configuration errors. Add policy rejection tests for credentials, unauthorized roots/origins, and unknown operations.

- [x] **Step 2: Run MCP tests to verify failure**

Run: `uv run --all-packages pytest -q packages/mcp/tests/test_tools.py packages/mcp/tests/test_stdio.py packages/mcp/tests/test_policy.py`

Expected: host-backed inspect/execute fail with the current hard-coded configuration response.

- [x] **Step 3: Implement host injection and shared dispatch**

Add the minimal host protocol/dataclass, pass it into the three closures, reuse `OperationCatalog`, `OperationRequest.from_wire`, `authorize`, and `ExecutionOptions`, and preserve structured `isError` result mapping. Do not add tools or accept shell/module/credential fields.

- [x] **Step 4: Run MCP tests and official SDK smoke**

Run the tests from Step 2 and the repository’s official-client smoke fixture. Expected: exactly three tools, successful discovery/host-backed read/execute, and fail-closed no-host behavior.

- [x] **Step 5: Commit MCP host wiring**

```bash
git add packages/mcp/src packages/mcp/tests
git commit -m "feat: wire MCP tools to an explicit SDK host"
```

### Task 5: Qualify Artifact Renderer and Watch Runtime State

**Files:**
- Modify: `packages/officecli/src/open_table_connector/officecli/capabilities.py`
- Modify: `packages/officecli/src/open_table_connector/officecli/document.py`
- Modify: `packages/officecli/src/open_table_connector/officecli/views.py`
- Modify: `packages/officecli/src/open_table_connector/officecli/process.py`
- Modify: `packages/sdk/src/open_table_connector/sdk/artifacts.py`
- Modify: `packages/sdk/src/open_table_connector/sdk/preview_sessions.py`
- Test: `packages/officecli/tests/test_views.py`
- Test: `packages/officecli/tests/test_process.py`
- Test: `packages/sdk/tests/test_artifact_views.py`
- Test: `packages/sdk/tests/test_preview_sessions.py`

**Interfaces:** Extend `OfficeCliCapability` with renderer/browser modes and `check_officecli(binary, renderer=...)`. `OfficeCliAdapter.render(snapshot_path, request)` must either return bounded output evidence or a capability error. `ArtifactAccess.watch(WatchRequest)` must preserve owned session identity, snapshot hash, state, URL, editability, and discard persistence.

- [x] **Step 1: Write fake-runtime and lifecycle tests**

Add tests for missing binary/renderer, nonblank HTML/PNG fake output, source hash immutability, asset-path rejection, occupied-port selection, stale PID protection, crash status, refresh replacement, and stop-without-publish.

- [x] **Step 2: Run artifact/runtime tests to verify failure**

Run: `uv run --all-packages pytest -q packages/officecli/tests packages/sdk/tests/test_artifact_views.py packages/sdk/tests/test_preview_sessions.py`

Expected: renderer remains an unconditional unavailable error and watch records lack runtime state.

- [x] **Step 3: Implement bounded runtime adapter state**

Use argv-only subprocess execution with capped output, owned disposable snapshot paths, source hash before/after, loopback-only URLs, process creation identity, and explicit capability errors. Never edit or publish the authoritative XLSX and never poll in the background.

- [x] **Step 4: Run focused artifact tests and commit**

Run the tests from Step 2 plus `uv run --all-packages pytest -q packages/artifacts/tests`.

```bash
git add packages/officecli/src packages/officecli/tests packages/sdk/src/open_table_connector/sdk/artifacts.py packages/sdk/src/open_table_connector/sdk/preview_sessions.py packages/sdk/tests/test_artifact_views.py packages/sdk/tests/test_preview_sessions.py
git commit -m "feat: qualify artifact renderer and watch runtime state"
```

### Task 6: Generate and Write the Complete Manuals

**Files:**
- Modify: `scripts/generate_reference_manuals.py`
- Create/update: `docs/user-guide/cli-manual.md`
- Create/update: `docs/user-guide/sdk-manual.md`
- Create/update: `docs/user-guide/components.md`
- Generate: `docs/reference/cli-options.md`, `docs/reference/api-inventory.md`, `docs/reference/spreadsheet-schemas.md`
- Modify: `README.md`, `CHANGELOG.md`, `docs/reference/README.md`, `docs/user-guide/README.md`, package READMEs

**Interfaces:** Generator supports `--check`, deterministic output, optional-package absence, stable source links, and complete parser/catalog/export inventories. Manuals link every generated inventory and every package README to the appropriate behavior section.

- [x] **Step 1: Add generator tests and manual link checks**

Test that all parser commands appear in `cli-manual.md`, all spreadsheet descriptors appear in `spreadsheet-schemas.md`, public exports are present in `api-inventory.md`, and every manual/package README link resolves to a tracked file.

- [x] **Step 2: Run generator checks red**

Run: `uv run --all-packages python scripts/generate_reference_manuals.py --check`

Expected: failure until the generated inventories and manual links are synchronized.

- [x] **Step 3: Complete manuals with verified examples**

Use the local provider fixture for runnable SDK examples. Include the exact CLI examples from the parser, commit/verification output interpretation, canonical URL rules, provider prerequisites, capability gates, and error/reconciliation behavior. Mark remote/live and renderer-dependent examples with explicit setup requirements.

- [x] **Step 4: Generate and verify references**

Run:

```bash
uv run --all-packages python scripts/generate_reference_manuals.py
uv run --all-packages python scripts/generate_reference_manuals.py --check
uv run --all-packages python scripts/check_cli_reference.py
```

Expected: generated files are stable and CLI reference parity passes.

- [x] **Step 5: Commit manuals and generated references**

```bash
git add scripts/generate_reference_manuals.py docs/reference docs/user-guide README.md CHANGELOG.md packages/*/README.md
git commit -m "docs: publish complete CLI and SDK reference manuals"
```

### Task 7: Full Verification and Acceptance Update

**Files:**
- Modify: `docs/reports/2026-10-06-p0-p2-acceptance.md`
- Modify: `docs/office-artifact-readiness.md`
- Modify: `docs/spreadsheet-rich-readiness.md`

- [ ] **Step 1: Run focused gap suites**

Run the task test commands plus `git diff --check`, package boundary and
independence checks, and wheel smoke for CLI, SDK, spreadsheets, artifacts,
OfficeCLI, and MCP.

- [ ] **Step 2: Run the full regression suite**

Run: `uv run --all-packages pytest -q`

Expected: no regressions; live OfficeCLI/browser/MaybeSheet gates remain
explicit if their prerequisites are unavailable.

- [ ] **Step 3: Update acceptance evidence**

Record shortcut persistence, recipe freshness, generic dispatch lifecycle, MCP
host behavior, renderer capability results, generated-reference checks, exact
commands, and any remaining live blockers.

- [ ] **Step 4: Review, commit, and report**

Run `git diff --check`, inspect the staged file list to exclude user-owned
changes, then commit the acceptance update and report the verification evidence.
