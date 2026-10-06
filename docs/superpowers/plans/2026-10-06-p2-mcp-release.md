# P2 MCP and Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose accepted OTC operations through an optional typed MCP adapter and verify all P0-P2 release gates.

**Architecture:** MCP wraps D2 discovery/dispatch and SDK facades; it adds transport authorization and framing only. Release verification exercises optional-package removal, CLI/SDK/MCP parity, real artifact evidence and provider-specific qualification.

**Tech Stack:** Official Python MCP SDK (`mcp>=1,<2`, resolve an available compatible version into the lock at implementation), existing SDK/JSON schemas, pytest, uv and repository verification scripts. Use no custom JSON-RPC engine.

**Spec:** [Sections 11-14; A11 and release gates](../specs/2026-10-06-cli-and-office-artifacts-p0-p2-design.md).

## Global Constraints

All [index constraints/interfaces](2026-10-06-cli-and-office-artifacts-p0-p2.md) apply. No shell-string execution, raw provider invocation, credential payloads, new result envelopes, implicit stdin reads or new domain retry policy. `otc-process` remains unchanged. Live/runtime evidence is required for affected release claims.

## Review Focus

- Symlink/path traversal and remote hostname lookalikes: M1 resolves canonical targets before authorization.
- Read-only tool invoked with a write operation: M2 rejects by descriptor effect before dispatch.
- Timeout after remote dispatch: M2 retains unknown/partial receipts and never retries.
- Noisy providers or oversized results corrupting protocol output: M2 bounds payloads and isolates stdout.
- Installed-wheel behavior differing from the source checkout: M3 tests clean package installation/removal.

## Task M1: Optional Package and Explicit Access Policy

**Files:** Create `packages/mcp/pyproject.toml`, `README.md`, `LICENSE`, `src/open_table_connector/mcp/{__init__.py,py.typed,policy.py}`, `tests/test_policy.py`; update workspace/lock and package-boundary/metadata/independence scripts plus universal boundary tests.

**Interfaces:** Frozen `AccessPolicy(allowed_roots: tuple[Path, ...], allowed_provider_ids: tuple[str, ...], allowed_document_origins: tuple[str, ...], credential_references: tuple[str, ...])`; `load_policy(path: Path) -> AccessPolicy`; `authorize(request: OperationRequest, policy: AccessPolicy) -> None`. Config path must be an explicit absolute deployment-owned `OTC_MCP_CONFIG`. Missing config fails server startup with safe diagnostics, not allow-all. Policy uses credential references only, resolved through SDK credentials at execution time.

- [x] Add policy coverage for missing configuration, symlink escapes, future output parents, exact remote origins, credential rejection, nested artifact assets, and core imports without MCP.
- [x] Run policy tests red, then implement canonical root/origin/provider checks with resolved parents. Do not treat string-prefix path comparisons as authorization.
- [x] Add optional metadata and the official MCP dependency; register `otc-mcp` without requiring MCP from SDK/CLI/provider packages, refresh the lock, and commit M1 as `feat: define optional MCP package and explicit access policy`.

## Task M2: Typed Tools and Cross-Transport Parity

**Files:** Create `packages/mcp/src/open_table_connector/mcp/{server.py,tools.py}`, `tests/test_tools.py`, `test_stdio.py`; create `specification/conformance/universal/test_operation_transport_parity.py`; update schemas/catalog registrations in defining packages as needed; update MCP docs.

**Interfaces:** Define three tools only: `otc_discover`, `otc_inspect`, `otc_execute`. Discover accepts closed static selector or endpoint request. Inspect accepts D1 `OperationRequest` and requires descriptor `effects == "read"`. Execute accepts a discriminated closed union of operation request, existing version `1.0` batch, or `otc.spreadsheet-recipe/1.0`, with D1 `ExecutionOptions`. Artifact requests enter through registered D2 operation IDs and O1 typed models, not direct arbitrary facade names. Return existing `OperationResult.to_wire()` as structured content.

Map failed/rejected/partial/unknown outcomes or failed required verification to MCP `isError=true`; retain committed receipts even when `isError=true`. Planned/succeeded results remain nonerrors unless required verification failed. Diagnostic capture is finite (1 MiB default); structured requests use 16 MiB and 10,000-operation limits. Oversized results return an explicit resource-limit result or an authorized existing artifact reference, never silently truncated valid-looking JSON.

- [x] Add typed discovery/inspection/execution, bounded result/error mapping, no-shell dispatch, receipt retention, and protocol-input isolation tests.
- [x] Add malformed-request and official stdio registration coverage; cancellation and host-backed execution remain explicit integration follow-ups because this package has no configured SDK host.
- [x] Reuse D2/R5/O2-O4 operation contracts and the official MCP SDK. Bind policy authorization before programmatic execution; keep stdout reserved for protocol framing.
- [x] Run MCP tests and an official-client initialize/list/call smoke; commit M2 as `feat: expose typed OTC discovery and execution through MCP`.

## Task M3: Release Qualification and Documentation Closure

**Files:** Extend `scripts/check_cli_reference.py`, `scripts/check_package_metadata.py`, `scripts/check_package_boundaries.py`, `scripts/check_package_independence.py`, `scripts/smoke_wheels.py`; extend `specification/conformance/universal/test_package_boundaries.py`, `test_package_metadata.py`; update `docs/spreadsheet-rich-readiness.md`, `docs/office-artifact-readiness.md`, `docs/user-guide/cli.md`, `agent-workflows.md`, `docs/reference/compatibility.md`; create `docs/reports/2026-10-06-p0-p2-acceptance.md` as the actual execution evidence ledger (date may be adjusted at implementation time).

**Interfaces:** No new public behavior. The ledger maps all twelve spec requirements/A1-A12 to exact source revision, test command, runtime version, fixture identity, result, skips and unresolved blockers. It must distinguish the research baseline from tests run on implemented source.

- [x] Extend wheel independence checks for artifacts, OfficeCLI, MCP, provider removal, and duplicate entry-point detection.
- [x] Run metadata, boundary, canonical URL, CLI reference, focused suites, full regression, formatting, and wheel checks. Do not weaken dependency-direction checks.
- [x] Attempt live OfficeCLI and MaybeSheet acceptance; qualified runtimes/credentials were unavailable, so those mandatory gates remain pending in the ledger.
- [x] Review the object matrix and document explicit blockers for unsupported objects, legacy binary output, external watch refresh, and OfficeCLI spreadsheet authorship.
- [x] Finalize A1-A12 ledger, command reference, agent guide, and readiness docs; commit M3 as `test: qualify P0-P2 interfaces and optional distributions`.

**Completion rule:** P0-P2 is complete only when all required workstream gates pass and all capability gaps are explicitly dispositioned according to the spec. A pending mandatory MaybeSheet image or actual OfficeCLI export/view gate prevents a full completion claim. Publication/merge/release is a separate user action unless authorized during execution.
