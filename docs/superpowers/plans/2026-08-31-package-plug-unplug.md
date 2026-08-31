# Package Plug/Unplug Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make every workspace distribution independently installable, importable, and removable while allowing the CLI and process host to discover installed providers dynamically.

**Architecture:** `open-table-connector-contract` owns a small provider-neutral plugin descriptor and discovery-facing interfaces. CLI and process are thin hosts that load entry points and skip absent providers; provider packages own their implementations and registration metadata. No host imports a provider at module import time.

**Tech Stack:** Python 3.11–3.14, setuptools package metadata, `importlib.metadata`, uv workspace, pytest.

**Spec:** `docs/superpowers/specs/2026-08-31-critical-review-remediation-design.md`

## Global Constraints

- Every package must import successfully with only its declared runtime dependencies installed.
- Removing one provider distribution must not make contract, timeseries, CLI, or process imports fail.
- Provider discovery must be deterministic and reject duplicate scheme/host routes.
- Provider-specific credentials and transports remain late-bound; importing a package must not perform I/O.
- Each implementation step is tested, committed, and pushed before the next step.

### Task 1: Define the provider-neutral plugin seam

**Files:**
- Create: `packages/contract/src/open_table_connector/contract/plugins.py`
- Modify: `packages/contract/src/open_table_connector/contract/__init__.py`
- Create: `packages/contract/tests/test_plugins.py`

Add `PluginDescriptor` with `name`, `identity`, `schemes`, `hosts`, and a zero-I/O `factory` callable. Add `PluginFactory` and closed validation for duplicate/empty routes. Keep the interface independent of CLI and provider packages.

Verify with isolated contract imports and descriptor validation tests.

### Task 2: Make CLI discovery lazy and optional

**Files:**
- Create: `packages/cli/src/open_table_connector/cli/plugins.py`
- Modify: `packages/cli/src/open_table_connector/cli/adapters.py`
- Modify: `packages/cli/src/open_table_connector/cli/registry.py`
- Modify: `packages/cli/src/open_table_connector/cli/__main__.py`
- Modify: `packages/cli/pyproject.toml`
- Create: `packages/cli/tests/test_plugins.py`

Move provider imports behind discovery factories. Load `open_table_connector.cli_adapters` entry points, convert each descriptor to the existing adapter seam, and skip unavailable optional providers with a deterministic diagnostic. Keep local codecs available only when the local-files plugin is installed; the CLI core must still import without it.

Verify a clean CLI-only environment, provider-present discovery, provider-absent discovery, and duplicate-route rejection.

### Task 3: Make process handlers optional

**Files:**
- Create: `packages/process/src/open_table_connector/process/plugins.py`
- Modify: `packages/process/src/open_table_connector/process/bootstrap.py`
- Modify: `packages/process/src/open_table_connector/process/registry.py`
- Modify: `packages/process/pyproject.toml`
- Create: `packages/process/tests/test_plugins.py`

Replace eager imports of local-files, MaybeSheet, PostgreSQL, and SQLite with entry-point handler discovery. The process core retains contract/protocol dependencies only; handlers register themselves when their distributions are installed.

Verify process-core import and bootstrap with no provider packages, then verify each installed handler is discoverable.

### Task 4: Register provider packages without reverse dependencies

**Files:**
- Modify: provider `pyproject.toml` files for local-files, MaybeSheet, PostgreSQL, SQLite, Google Sheets, Feishu Bitable, and dbt
- Create: provider-local `plugin.py` registration modules as needed
- Modify: provider `__init__.py` exports and tests

Declare CLI/process entry points that target provider-owned factories. Keep provider dependencies directed downward toward contract/timeseries; no provider may depend on CLI or process. Preserve optional live database drivers as extras.

Verify each provider wheel imports in a clean environment and exposes only its own registration metadata.

### Task 5: Enforce independent install/uninstall in CI

**Files:**
- Modify: `scripts/check_package_boundaries.py`
- Create: `scripts/check_package_independence.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `docs/package-boundaries.md`
- Create: `packages/*/tests/test_independent_import.py` where package-local coverage is needed

Build every wheel, install each distribution alone in a temporary environment, import its public package, and run an uninstall matrix proving remaining packages still import. Fail on undeclared imports, reverse dependencies, missing package data, or eager provider imports.

Run the full matrix, compatibility verifier, wheel smoke tests, and affected test suites. Commit only after all gates pass.
