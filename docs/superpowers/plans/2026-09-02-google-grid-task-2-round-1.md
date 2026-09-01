# Google Sheets Grid Task 2 Round 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct Google Sheets grid formula mutation safety, provider error mapping, bounded POST responses, and worksheet identity/A1 handling at base commit `643ff15`.

**Architecture:** Keep the change inside the Google Sheets formula extension and its focused tests. Track whether the batchUpdate POST was dispatched so only pre-dispatch failures can release an idempotency entry; post-dispatch uncertainty remains protected. Validate provider status details before mapping 400 errors, enforce the shared response limit on every response path, and derive escaped A1 titles only from a validated binding.

**Tech Stack:** Python 3.11+, pytest, uv, Ruff, Google Sheets `batchUpdate`/grid-data transport stubs, Formula extension core types.

**Spec:** `docs/superpowers/plans/2026-09-01-grid-formula-providers.md` and reviewer findings supplied for Google Sheets Grid Task 2 round 1.

## Global Constraints

- Keep Google formula capabilities and `packages/google_sheets/src/open_table_connector/google_sheets/manifest.json` disabled/unchanged.
- Never send a second POST for an idempotency key after a POST has been dispatched.
- Preserve sanitized error details; raw provider diagnostics and formula text must not enter formula errors or receipts.
- Run focused Google formula/connector/CLI tests, Ruff, and `git diff --check` before completion.
- Update `.superpowers/sdd/2026-09-01-grid-formula-providers/task-2-report.md` and commit with a Conventional Commit.

### Task 1: Add red regressions for reviewer findings

**Files:**
- Modify: `packages/google_sheets/tests/test_formula.py`

- [ ] Add a regression proving post-dispatch partial/protocol/readback failures leave the idempotency key non-reusable and do not issue a second POST.
- [ ] Add a regression proving a non-formula HTTP 400 maps to the generic sanitized execution error rather than `INVALID_FORMULA`.
- [ ] Add a regression proving an oversized `updatedSpreadsheet` POST response is rejected before parsing or readback I/O, including a caller-supplied lower `max_response_bytes` limit.
- [ ] Add regressions for quoted worksheet titles in GET/POST A1 ranges and for name/ID metadata mismatches being rejected without binding.
- [ ] Run each new focused test before implementation and record the expected failures as RED.

### Task 2: Implement minimal fixes

**Files:**
- Modify: `packages/google_sheets/src/open_table_connector/google_sheets/formula.py`

- [ ] Introduce explicit post-dispatch state around batchUpdate and mark the ledger unknown for post-dispatch protocol, partial, and readback failures; use `fail_known` only for failures proven to occur before dispatch.
- [ ] Map status 400 to `INVALID_FORMULA` only for recognized provider formula reason/code values; map other 400s through the sanitized generic provider error path.
- [ ] Apply the effective response byte limit to `updatedSpreadsheet` before `_parse_grid_response`; combine 8 MiB with `FormulaResourceLimits.max_response_bytes`.
- [ ] Quote worksheet titles as A1 sheet names and require cached/bound worksheet name consistency with the target reference.
- [ ] Run the new regressions and the existing focused suite GREEN.

### Task 3: Verify, document, and commit

**Files:**
- Modify: `.superpowers/sdd/2026-09-01-grid-formula-providers/task-2-report.md`

- [ ] Run focused Google formula/connector/CLI tests, Ruff, and `git diff --check`.
- [ ] Verify capabilities and manifest remain disabled, inspect the final diff, and record RED/GREEN evidence, changed files, commit, and concerns in the report.
- [ ] Commit all requested changes with a Conventional Commit message and verify the final commit/status.
