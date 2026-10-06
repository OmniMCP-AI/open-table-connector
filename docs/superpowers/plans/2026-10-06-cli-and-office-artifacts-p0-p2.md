# OTC CLI and Office Artifacts P0-P2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver all twelve P0-P2 requirements in the specification through four independently testable workstreams.

**Architecture:** CLI and MCP reuse SDK orchestration and operation schemas. Rich spreadsheets use existing local Excelize or MaybeSheet sheet-mode operations; OfficeCLI writes DOCX/PPTX and renders disposable snapshots only.

**Tech Stack:** Python `>=3.11,<3.15`, argparse, existing SDK/Arrow/Polars, Excelize `>=0.1,<0.2` (current lock `0.1.0`), existing MaybeSheet transport, optional OfficeCLI process adapter, optional official Python MCP SDK, pytest, uv.

**Spec:** [P0-P2 design](../specs/2026-10-06-cli-and-office-artifacts-p0-p2-design.md). Read it and the relevant workstream before execution. Status: planning only; every task is unchecked.

## Global Constraints

- Preserve `Client`, `Table`, `Query`, DataFrame, existing table commands and result contracts.
- Use canonical `file://` URLs and MaybeSheet HTTPS document URLs. Do not introduce retired local-format/provider URI routes.
- Rich XLSX authoring uses existing Excelize capabilities only. MaybeSheet sheet-mode is a required provider, not a later optional target.
- OfficeCLI never writes, recalculates or resaves the authoritative spreadsheet. Render only disposable snapshots.
- Integration wrappers and qualification are in scope; new engines, Excelize features, MaybeSheet server endpoints and legacy DOC/PPT/XLS conversion are not.
- Keep strict `literal-artifact/1.0` unchanged. New local rich operations require explicit `rich-artifact/1.0`; MaybeSheet retains `general/1.0`.
- Preserve literal values, explicit formula dialects, native units, partial/unknown effects and provider capability restrictions.
- Strict JSON inputs: 16 MiB UTF-8 bytes, 10,000 batch/recipe operations, no duplicate properties/non-finite numbers/unknown keys.
- Python `>=3.11,<3.15`; optional packages must remain removable. Physical providers must not introduce SDK imports.
- New artifact commands: input/usage exit `2`, execution failure/rejection/partial/unknown exit `5`; preserve existing command exit mappings.
- Follow repository instructions: use graph tools first if available; cap potentially large command output. No implementation, dependency install or commits occur while writing these plans.

## Review Focus

- Optional package absence or duplicate registration must not break unrelated core imports: D1, D2, O1, M3.
- Formula-like text, null/empty string and shell metacharacters must survive transport unchanged: D3, R2, O2, M2.
- A remote timeout after dispatch must preserve unknown effects and block automatic retry: R3, M2.
- A snapshot can be visually current while the authoritative source is different: O3, O4, R4.
- A rich object can survive engine acknowledgment but disappear on save/reopen: R2, R4, O2.

## Workstream Plans and Order

| Order | Plan | Tasks | Spec coverage |
| --- | --- | --- | --- |
| 1 | [Discovery and CLI](2026-10-06-p0-p1-discovery-cli.md) | D1-D4 | DISC-1/2, CLI-1/2/3, GUIDE-1; A1-A6 |
| 2A | [Rich spreadsheets and recipes](2026-10-06-p2-rich-spreadsheets-recipes.md) | R1-R5 | RICH-1/2, RECIPE-1; A9/A10/A12 |
| 2B | [Artifacts and presentation](2026-10-06-p2-artifacts-presentation.md) | O1-O4 | DOC-1, VIEW-1; A7/A8 |
| 3 | [MCP and release](2026-10-06-p2-mcp-release.md) | M1-M3 | MCP-1; A11 and all release gates |

Execute D1 before D2-D4. R1 follows D1/D2; R2/R3 follow R1; R4 follows R2/R3; R5 follows R4. O1 follows D1/D2; O2 follows O1; O3 follows O2 and consumes R2/R3 snapshot adapters; O4 follows O3. M1 follows D2; M2 requires D3, R5 and O4. M3 is last. Workstreams 2A and 2B have separate ownership but share contracts; parallel execution is optional, not authorized or launched by this document.

## Cross-Plan Interface Ledger

These are proposed interfaces to implement, not existing imports. Defining tasks own the types. No later task may invent a second parser, result envelope or provider router.

| Owner | Module and produced interface | Consumers |
| --- | --- | --- |
| D1 | `contract.operations`: immutable `OperationDescriptor`, `OperationRequest`, `TargetSelector`, `ExecutionOptions`, `CapabilityObservation`; strict `from_wire`/`to_wire` | All |
| D1 | `contract.json_input.read_json_input(source, stdin=None, max_bytes=16777216) -> object` | CLI, recipes, MCP validation |
| D2 | `sdk.discovery.OperationCatalog.describe(namespace, operation_id=None) -> tuple[OperationDescriptor, ...]`; `resolve_capabilities(client, target) -> OperationResult[CapabilityObservation]` | CLI, rich adapters, MCP |
| D2 | `sdk.operations.execute_operation(client, request, options) -> OperationResult[object]` with explicit registered dispatch | CLI shortcuts, recipes, MCP |
| R1 | `spreadsheets.rich.RichObjectRequest`, `ObjectObservation`, `RichQualification`; provider protocol remains bind/preflight/commit/observe | R2-R4, artifacts |
| R4 | `sdk.snapshots.capture_workbook_snapshot(client, target, directory) -> OperationResult[WorkbookSnapshot]` | Views/watch |
| R5 | `spreadsheets.recipes.parse_recipe(payload) -> LayoutRecipe`; `sdk.recipes.apply_recipe(client, target, recipe, options) -> OperationResult[object]` | CLI, MCP |
| O1 | `artifacts.model.ExportRequest`, `ViewRequest`, `WatchRequest`, `ArtifactValue`, `ViewValue`, `WatchValue`; neutral `ArtifactAdapter` protocol | SDK, OfficeCLI, MCP |
| O2 | `Client.artifacts() -> ArtifactAccess`; `ArtifactAccess.export(request) -> OperationResult[ArtifactValue]` | CLI, MCP |
| O3 | `ArtifactAccess.view(request) -> OperationResult[ViewValue]` | CLI, MCP |
| O4 | `ArtifactAccess.watch(request) -> OperationResult[WatchValue]` | CLI, MCP |
| M1 | `mcp.policy.AccessPolicy`; `authorize(request, policy) -> None` | MCP only |

`TargetSelector` has `uri: str`, `sheet: str | None`, `object_id: str | None`. Canonicalization and stable provider binding occur through the SDK, never by splitting worksheet/object names manually. `ExecutionOptions` has `dry_run: bool=False`, `allow_partial: bool=False`, `expected_revision: str | None=None`, `idempotency_key: str | None=None`, `failure_directory: str | None=None`. Reuse these exact fields across tasks. No added optimistic flags.

`OperationRequest` has `namespace: str`, `operation_id: str`, `version: str`, `target: TargetSelector | None`, `arguments: Mapping[str, object]`. It is structurally typed/frozen, and its arguments are validated against the resolved closed operation schema before execution. Dispatch is a closed registry, not an arbitrary Python/module/subprocess call.

## Execution Rules and Verification Commands

Each task follows red test, minimal implementation, green focused test, then a task-scoped commit. Commit steps belong to future execution; never stage unrelated `.gitignore`, `AGENTS.md`, `opencode.jsonc`, research or user changes implicitly. Before execution inspect the current branch/worktree and follow the worktree skill; do not create one for planning.

In task commands, `pytest PATH` means:

```sh
uv run --all-packages --frozen python -m pytest PATH -q --tb=short
```

Redirect long output to a task log, capture the actual command exit status, and display only a bounded tail; do not mistake the tail/head exit code for the test result. The expected result is exit `0`, all named tests passed, and only explicitly documented opt-in live skips. Red runs must fail for the new contract, not missing unrelated dependencies. New optional packages require an intentional `uv lock`/sync after metadata edits, followed by frozen runs; do not use `--frozen` to conceal an unrefreshed workspace lock.

## Acceptance Tracking

| Gate | Owning tasks |
| --- | --- |
| A1: command/reference inventory | D2, D4 |
| A2: static/live discovery truthfulness | D1, D2 |
| A3: shortcut parity | D3 |
| A4: bounded file/stdin input | D1, D3 |
| A5: safe errors and preserved exits | D4 |
| A6: version-aligned agent guide | D4 |
| A7: native document table export | O1, O2 |
| A8: snapshot views/watch | O3, O4 |
| A9: local Excelize rich objects | R1, R2, R4 |
| A10: MaybeSheet rich-sheet evidence | R1, R3, R4 |
| A11: typed MCP parity | M1, M2 |
| A12: observed recipe replay | R5 |

- [x] D1-D4 complete; A1-A6 evidence recorded.
- [x] R1-R5 complete; A9/A10/A12 evidence recorded, with live MaybeSheet evidence explicitly pending.
- [x] O1-O4 complete; A7/A8 source-level evidence recorded, with qualified OfficeCLI runtime evidence explicitly pending.
- [x] M1-M3 complete; A11 and package/release evidence recorded.
- [x] Every image/object family has an explicit qualified subset or evidence-backed blocker; no missing operation is silently advertised or omitted.
- [x] P3 resident mutation services and legacy converters remain excluded.

Unavailable live credentials, renderer binaries or remote operations are release blockers for the affected claims, not reasons to invent evidence. Continue independent tasks; keep affected gates open. Proposed operations are not implemented simply because their schemas or plans exist.
