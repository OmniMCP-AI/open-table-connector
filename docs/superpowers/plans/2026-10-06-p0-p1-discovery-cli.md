# P0-P1 Discovery and CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make installed operations discoverable and common spreadsheet commands ergonomic without changing execution semantics.

**Architecture:** Neutral descriptors and strict parsing feed an SDK catalog/dispatcher. CLI help, capabilities and shortcuts adapt those APIs; providers retain physical ownership.

**Tech Stack:** Python, argparse, JSON Schema draft 2020-12, pytest, existing entry-point discovery. Use `jsonschema>=4,<5` in the SDK for schema validation; contract objects remain dependency-light data.

**Spec:** [P0-P2 design, sections 3-6](../specs/2026-10-06-cli-and-office-artifacts-p0-p2-design.md).

## Global Constraints

All [index constraints and interfaces](2026-10-06-cli-and-office-artifacts-p0-p2.md) apply. Preserve 16 MiB/10,000 limits, current exit/result contracts, canonical URLs, literal writes and optional provider imports. Static help must not access credentials/network or activate a provider.

## Review Focus

- Duplicate/broken optional schema plugins: D1/D2 reject the affected entry without initializing unrelated providers.
- Missing local output versus unreachable remote target: D2 distinguishes static creation support from live unknown state.
- Boolean omission and numeric-looking strings: D3 preserves them exactly.
- Stdin EOF/byte boundary and MCP-owned stdin: D1/D3 reject before dispatch or never read protocol input.
- Suggested property spellings containing secrets: D4 emits only schema-derived safe suggestions.

## Task D1: Descriptor Types and Strict Input

**Files:** Create `packages/contract/src/open_table_connector/contract/operations.py`, `json_input.py`; create `packages/contract/tests/test_operations.py`, `test_json_input.py`; update `packages/contract/src/open_table_connector/contract/__init__.py`.

**Interfaces:** Produce the five frozen types and strict wire methods in the index. `OperationDescriptor` fields match spec 5.2 exactly; effect is one of `read`, `buffered_write`, `publish`, `session_control`. `CapabilityObservation` carries target, provider/version, resolution (`static`/`live`), observed timestamp and per-operation support/constraints/guarantees/coverage. `read_json_input(source: str, *, stdin: BinaryIO | None=None, max_bytes: int=16777216) -> object` opens files in binary mode; `source == "-"` requires explicit supplied stdin. It rejects duplicate keys/nonfinite values with a neutral typed input error containing an argument path, not raw data.

- [x] Add `test_descriptor_roundtrip_and_closed_fields`: assert stable round-trip, deep immutability, unknown fields/version/effect reject. Add `test_requests_preserve_null_false_zero_empty` using `[None, False, 0, "", "00123", "=SUM(A1:A2)"]` and assert exact types/values after wire round-trip.
- [x] Add `test_json_exact_byte_limit`, `test_duplicate_nested_key`, `test_nonfinite_rejected`, `test_missing_explicit_stdin`, `test_utf8_limit_counts_bytes`: use a small injected limit for exact boundary fixtures and assert oversized input reads at most limit+1 bytes, malformed input yields no returned payload, and duplicates reject at any nesting depth.
- [x] Run `pytest packages/contract/tests/test_operations.py packages/contract/tests/test_json_input.py`; initial run failed because production modules were absent, as expected.
- [x] Implement immutable types, closed validation and strict bounded parser. Add no provider/SDK imports and no default stdin acquisition.
- [x] Run the same tests: 5 passed. Commit: `feat: add versioned operation discovery contracts`.

## Task D2: SDK Catalog, Capability Resolution and Help

**Files:** Create `packages/sdk/src/open_table_connector/sdk/discovery.py`, `operations.py`; create `packages/spreadsheets/src/open_table_connector/spreadsheets/operation_catalog.py`, `schemas/operations.json`; create `packages/cli/src/open_table_connector/cli/discovery_commands.py`; update CLI `__main__.py`, `commands.py`; update SDK/spreadsheets `pyproject.toml` and `uv.lock`; create `packages/sdk/tests/test_discovery.py`, `test_operations.py`, `packages/cli/tests/test_discovery_commands.py`.

**Interfaces:** Implement the index catalog/resolution/dispatch APIs. Introduce versioned entry-point groups `open_table_connector.operation_catalogs.v1` (factory returns `tuple[OperationDescriptor, ...]`, zero I/O) and `open_table_connector.operation_handlers.v1` (factory returns explicit operation-to-handler registrations loaded only at execution). Preserve existing `PluginDescriptor` routing fields unchanged. Reject duplicate `(namespace, operation_id, version)` registrations deterministically. Handler signature is `(client: Client, request: OperationRequest, options: ExecutionOptions) -> OperationResult[object]`; handlers live in SDK/host adapter code, not neutral providers.

The spreadsheet catalog starts with every currently dispatched operation and read action. `execute_operation` validates a request and enters the existing WorkbookSession for writes/observations. Initially register only those current operations; future tasks register qualified ones. Capability resolution uses existing configured SDK routing and provider bindings, never creates a workbook. Missing endpoint data produces unknown/live-error evidence, not synthesized support. Add `otc help ... --output-format json|table` and `otc capabilities ... --output-format json|table` through this API.

- [x] Add `test_help_does_not_activate_provider`: fake provider factory/credential resolver raises if called; help succeeds. Add `test_duplicate_schema_registration_rejected` and `test_absent_spreadsheet_package_keeps_core_help` in an isolated import fixture.
- [x] Add `test_missing_file_uses_static_creation_only`, `test_remote_auth_failure_not_supported`, `test_schema_known_but_provider_unsupported`, `test_schema_examples_match_dispatch_validation`; assert support state, resolution origin, no mutation, and argument rejection before handler calls.
- [x] Add `test_help_and_capabilities_cli_use_sdk_payload` and `test_unknown_operation_never_imports_arbitrary_module`; compare CLI JSON with SDK results and assert zero dispatch for unregistered IDs.
- [x] Run the three new test modules; initial run failed on the intentionally missing catalog/commands.
- [x] Implement modules, entry points, closed schemas and validation; package schema resources. Add SDK `jsonschema>=4,<5`, refresh lock intentionally, then test frozen execution. Keep registry/provider loading lazy.
- [x] Run new tests plus `packages/cli/tests/test_commands.py` and `specification/conformance/universal/test_discovery.py`; all pass. Commit D2 files: `feat: expose operation help and endpoint capabilities`.

## Task D3: Shortcuts and Stdin Batch Parity

**Files:** Create `packages/cli/src/open_table_connector/cli/spreadsheet_shortcuts.py`; update `spreadsheet_commands.py`, `__main__.py`; create `packages/cli/tests/test_spreadsheet_shortcuts.py`, `test_batch_stdin.py`; update `packages/cli/tests/test_spreadsheet_commands.py`.

**Interfaces:** `compile_shortcut(args: Namespace) -> OperationRequest`; `style`, `format`, `write`, `worksheet create|rename|delete` map exactly as spec 6.1. Boolean flags use tri-state `None/True/False`. `--values-file` calls D1 parser; range dimensions validate before dispatch. Existing batch `_read_json` delegates to D1 parser while preserving its usage-error interface. Main supplies `sys.stdin.buffer` only when explicit `--commands -`; programmatic/MCP execution uses structured requests and no implicit stdin.

- [x] Add `test_shortcut_equals_generic_operation` parameterized over style/format/write/create/rename/delete: compare normalized request, receipts/commit semantics and persisted readback with generic command. Add `test_omitted_bold_differs_from_no_bold` and `test_values_stay_literal_and_typed` using the D1 edge values.
- [x] Add `test_conflicting_boolean_flags_reject`, `test_ragged_or_wrong_size_range_rejects_before_dispatch`, `test_worksheet_delete_keeps_reference_guard`, `test_unsupported_revision_rejected` and assert no mutation on rejection.
- [x] Add `test_file_stdin_identical`, `test_10000_changes_accepted_10001_rejected`, `test_stdin_limit_16777216`, `test_empty_stdin_rejected`, `test_batch_mcp_without_stdin_raises_usage`: exact bounds, zero provider calls on invalid input. Retain existing unknown-envelope-key tests.
- [x] Run the three affected test modules; initial run failed on the intentionally missing shortcut module.
- [x] Implement parser/compiler and shared dispatch. Use schema field enums from D2; preserve generic commands and output defaults. Restrict flags to the spec's initial style set.
- [x] Run new tests plus existing `test_commands.py`, `test_cli_e2e.py`; all pass. Commit D3 files: `feat: add typed spreadsheet shortcuts and bounded stdin batches`.

## Task D4: Safe Errors, Command Index and Agent Guide

**Files:** Update `packages/cli/src/open_table_connector/cli/output.py`, `discovery_commands.py`; create `scripts/check_cli_reference.py`; update `docs/user-guide/cli.md`, `docs/user-guide/spreadsheet-operations.md`; create `docs/user-guide/agent-workflows.md`; create `packages/cli/tests/test_error_suggestions.py`, `test_reference_inventory.py`.

**Interfaces:** `suggest_argument(name: str, descriptor: OperationDescriptor) -> tuple[str, ...]` uses only declared schema names and deterministic ordering, never values or provider exception text. `check_cli_reference(root: Path) -> list[str]` compares parser command/action inventory and generated reference markers without credentials or network. Exit codes stay exactly as spec 6.3.

- [x] Add `test_suggestion_does_not_dispatch_or_correct`, `test_suggestion_redacts_secret_value`, `test_spreadsheet_otc_error_remains_exit_five`, `test_table_legacy_category_codes_unchanged`, `test_partial_result_keeps_receipts`.
- [x] Add `test_cli_reference_contains_every_action` and `test_agent_examples_parse_and_validate`: guide examples cover file, MaybeSheet HTTPS, formulas, partial effects, capability errors and delivery checks using fake/disposable providers.
- [x] Run the two new modules; initial run failed on the intentionally missing reference/suggestion implementations.
- [x] Implement suggestion/reference checker and docs. Examples remain bounded and do not install clients automatically.
- [x] Run all `packages/cli/tests`, `scripts/check_cli_reference.py`, and `git diff --check`; all pass. Commit D4 files: `docs: publish complete CLI discovery and agent workflows`.

**Handoff:** D1-D4 complete A1-A6. RICH/DOC/MCP implementations consume D1/D2 APIs, not CLI private helpers. Record current test counts, versions and any allowed skips in the release evidence ledger.
