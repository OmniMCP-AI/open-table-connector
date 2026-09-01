# Task 2 Report

Date: 2026-09-02
Task: Grid Formula Providers, Task 2 — Google Sheets
Branch: `codex/formula-extension`

## Scope Delivered

- Hardened `GoogleSheetsFormulaExtension` after POST dispatch: partial, protocol, response-limit, transport, and readback failures mark the idempotency entry unknown; only proven pre-dispatch failures use reusable `fail_known` state.
- Made a `fail_known` ledger entry reusable for a later attempt, preserving safe retries only when no POST was sent.
- Mapped HTTP 400 to `INVALID_FORMULA` only when provider reason/code identifies a formula rejection; other 400 responses use sanitized `EXECUTION_FAILED` details.
- Applied the 8 MiB ceiling and caller `max_response_bytes` to grid GETs and `updatedSpreadsheet` POST responses before parsing or readback I/O.
- Validated URI worksheet names against the bound numeric sheet ID and escaped special worksheet titles in Google A1 ranges, including POST `responseRanges`.
- Kept the existing CLI forwarding, static capabilities, manifest, and ordinary value-only table writer unchanged.

## RED Evidence

The first focused regression run against base commit `643ff15` failed as expected:

```text
10 failed, 12 passed
Failures covered ignored caller response limits, mismatched worksheet binding,
unescaped A1 titles, non-reusable pre-dispatch retry state, post-dispatch
idempotency state, non-formula 400 mapping, and POST response limits.
```

## GREEN Evidence

```text
uv run --frozen python -m pytest packages/google_sheets/tests/test_formula.py -q
22 passed
```

```text
uv run --frozen python -m pytest packages/google_sheets/tests/test_formula.py packages/google_sheets/tests/test_connector.py packages/google_sheets/tests/test_cli_adapter.py -q
35 passed
```

```text
uv run --frozen ruff check packages/google_sheets packages/formulas
All checks passed!
```

```text
git diff --check
[no output]
```

The full suite reached `1230 passed, 3 skipped, 3 failed`; the failures are the
known base-scope `test_production_python_reuses_canonical_provider_and_route_constants`
failure and the two intentionally red grid-provider matrix tests while later
providers remain disabled.

## Changed Files

- `packages/google_sheets/src/open_table_connector/google_sheets/formula.py`
- `packages/google_sheets/tests/test_formula.py`
- `packages/formulas/src/open_table_connector/formulas/operations.py`
- `docs/superpowers/plans/2026-09-02-google-grid-task-2-round-1.md`
- `.superpowers/sdd/2026-09-01-grid-formula-providers/task-2-report.md`

## Commit

- Implementation: `855d6b3de6300bd7c6922ebea8e2feb04049c524` (`fix: harden Google Sheets grid formula mutations`)
- This report is included in the follow-up Conventional Commit `docs: record Google grid task 2 round 1`.

## Concerns

- Static Google capability tuples and `manifest.json` remain unchanged by design; capability discovery remains disabled until the later enablement task.
- The shared grid-provider matrix remains intentionally red until Tasks 3–5 register and enable all providers.
- The full-suite canonical-literal check still reports pre-existing repeated literals outside this round’s requested behavior.
