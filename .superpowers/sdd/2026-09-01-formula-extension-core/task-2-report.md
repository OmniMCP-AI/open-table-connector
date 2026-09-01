# Task 2 Report: Formula Observations, Values, Capability Details, and Wire Codecs

## Status

Completed in `/Volumes/Lexar1T/Code/GitHub/open-table-connector/.worktrees/formula-extension`.

Commit: `ce9e5b9c6f834fb934af5d31ba5aa8ae60494cae`

## RED Evidence

Command:

```bash
uv run --frozen python -m pytest packages/formulas/tests/test_observations.py packages/formulas/tests/test_wire.py -q
```

Observed output:

```text
==================================== ERRORS ====================================
ERROR collecting packages/formulas/tests/test_observations.py
ImportError: cannot import name 'CalculationState' from 'open_table_connector.formulas'
ERROR collecting packages/formulas/tests/test_wire.py
ImportError: cannot import name 'CalculationState' from 'open_table_connector.formulas'
2 errors in 0.30s
```

The new public Task 2 API was missing before implementation, so the test-first failure condition was satisfied.

## GREEN Evidence

Focused tests:

```bash
uv run --frozen python -m pytest packages/formulas/tests/test_observations.py packages/formulas/tests/test_wire.py -q
```

Output:

```text
................                                                         [100%]
16 passed in 0.25s
```

Lint:

```bash
uv run --frozen ruff check packages/formulas
```

Output:

```text
All checks passed!
```

Diff hygiene:

```bash
git diff --check
```

Output:

```text
[no output]
```

## Changed Files

- `packages/formulas/src/open_table_connector/formulas/__init__.py`
- `packages/formulas/src/open_table_connector/formulas/model.py`
- `packages/formulas/src/open_table_connector/formulas/observations.py`
- `packages/formulas/src/open_table_connector/formulas/wire.py`
- `packages/formulas/tests/test_observations.py`
- `packages/formulas/tests/test_wire.py`

## What Changed

- Added immutable formula observation/value domain records with exact-key `to_wire()` / `from_wire()` codecs.
- Added closed enums for calculation state, trigger, mutation atomicity, revision enforcement, and idempotency strength.
- Added tagged recursive `FormulaValue` handling for null, boolean, integer, number, string, sequence, mapping, logical, and provider-error values.
- Added `FormulaCapabilityDetails` and `FormulaCapabilitySet` validation for duplicate capabilities, target-kind mismatches, dialect subset enforcement, and recalculation-scope requirements.
- Added `FormulaMutation` and `RecalculationObservation` validation, including affected-count and scope/verification consistency.
- Added closed wire dispatch helpers and canonical observation hashing in `wire.py`.
- Added exact-key wire support to `FormulaExpression` without changing Task 1 validation behavior.

## Commands Run

```bash
uv run --frozen python -m pytest packages/formulas/tests/test_observations.py packages/formulas/tests/test_wire.py -q
uv run --frozen ruff check packages/formulas
git diff --check
git add packages/formulas
git commit -m "feat: add formula observations and wire codecs"
```

## Commit

`ce9e5b9c6f834fb934af5d31ba5aa8ae60494cae` - `feat: add formula observations and wire codecs`

## Concerns

- No functional blockers from the Task 2 brief remain.
- The commit used the local auto-configured Git identity (`Tony <Shelly1@Shellys-Mac-mini-4.local>`), which Git warned may need adjustment if that identity is not intended.

## Fix Round 1

### Scope

- Enforced `FormulaCapabilitySet` membership against the closed `ALL_CAPABILITIES` set, including rejecting unknown formula capability IDs and unexpected versions.
- Redacted diagnostic `repr()` output for value-bearing public records so raw calculated values no longer appear in logs or assertions.

### RED Evidence

Command:

```bash
uv run --frozen python -m pytest packages/formulas/tests/test_observations.py -q
```

Observed output:

```text
........FF..
FAILED packages/formulas/tests/test_observations.py::test_formula_capability_set_rejects_duplicates_mismatches_and_empty_recalc_scopes
Failed: DID NOT RAISE ValueError

FAILED packages/formulas/tests/test_observations.py::test_value_bearing_repr_is_redacted_for_diagnostics
AssertionError: assert 'literal' not in rendered
2 failed, 10 passed in 0.26s
```

### GREEN Evidence

Focused regression:

```bash
uv run --frozen python -m pytest packages/formulas/tests/test_observations.py -q
```

Output:

```text
............                                                             [100%]
12 passed in 0.15s
```

Covering package tests:

```bash
uv run --frozen python -m pytest packages/formulas/tests -q
```

Output:

```text
.................................                                        [100%]
33 passed in 0.14s
```

Lint:

```bash
uv run --frozen ruff check packages/formulas
```

Output:

```text
All checks passed!
```

Diff hygiene:

```bash
git diff --check
```

Output:

```text
[no output]
```

### Fix-Round Changed Files

- `packages/formulas/src/open_table_connector/formulas/observations.py`
- `packages/formulas/tests/test_observations.py`
