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

## Fix Round 2 Evidence

The replay branch now treats every replay, including one without a cached operation hash, as terminal uncertainty and publishes the completed result while holding the ledger lock. Added explicit coverage for dual worksheet selectors that identify different sheets. The existing implementation and tests also cover digit-suffixed function names, caller expression limits after response parsing, and strict recognized HTTP 400 formula reasons.

GREEN verification:

```text
uv run --frozen python -m pytest packages/google_sheets/tests/test_formula.py packages/google_sheets/tests/test_connector.py packages/google_sheets/tests/test_cli_adapter.py -q
44 passed in 0.31s

uv run --frozen ruff check packages/google_sheets packages/formulas/src/open_table_connector/formulas/operations.py
All checks passed!

git diff --check
[no output]
```

Changed files:

- `packages/google_sheets/src/open_table_connector/google_sheets/formula.py`
- `packages/google_sheets/tests/test_formula.py`

Commit: pending after scoped re-review.
- The full-suite canonical-literal check still reports pre-existing repeated literals outside this round’s requested behavior.

## Round 2 Evidence

### Scope Delivered

- Published successful idempotency results atomically with the ledger state and made an uncached replay terminal/uncertain, preventing a replay from issuing a second POST.
- Required worksheet name and worksheet ID selectors to agree with one metadata worksheet, including pre-I/O rejection when the URI and selector names conflict.
- Added caller `FormulaResourceLimits.max_expression_bytes` handling to returned formula parsing and request validation while preserving the provider hard ceiling.
- Prevented digit-suffixed function names such as `LOG10` from being shifted as A1 references while retaining valid relative, absolute, and mixed reference shifting.
- Restricted HTTP 400 `INVALID_FORMULA` mapping to an explicit normalized reason/code allowlist; non-formula and formula-service-like errors remain execution failures.
- Kept formula capabilities and `manifest.json` disabled and made no changes to the ordinary RAW/value writer.

### RED Evidence

```text
uv run --frozen python -m pytest packages/google_sheets/tests/test_formula.py packages/formulas/tests/test_model.py -q
7 failed, 26 passed
```

The expected failures covered dual selector construction/binding, caller expression
limits, `LOG10` translation, formula-service-like 400 classification, and uncached
replay behavior.

### GREEN Evidence

```text
uv run --frozen python -m pytest packages/google_sheets/tests/test_formula.py packages/google_sheets/tests/test_connector.py packages/google_sheets/tests/test_cli_adapter.py -q
42 passed
```

```text
uv run --frozen python -m pytest packages/formulas/tests packages/sdk/tests/test_formula.py -q
98 passed
```

```text
uv run --frozen ruff check packages/google_sheets packages/formulas packages/sdk
All checks passed!
```

```text
git diff --check
[no output]
```

### Round 2 Commit

This evidence is included in the round-2 Conventional Commit for Task 2.
