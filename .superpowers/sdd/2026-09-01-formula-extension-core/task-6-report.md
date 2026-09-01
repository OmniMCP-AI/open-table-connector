# Task 6 Report

Date: 2026-09-02
Task: Core Formula Extension implementer, Task 6
Branch: `codex/formula-extension`
Commit: `f81d6cfa8c62eb8b751d87d3b1cb3c1fac66e2f4`

## Scope Delivered

Implemented reusable capability-selected Formula conformance assertions and security probes on top of accepted Core Tasks 1–5.

## RED Evidence

Command:

```bash
uv run --frozen python -m pytest packages/conformance/tests/test_formula_framework.py specification/conformance/formulas/test_security.py -q
```

Output:

```text
ERROR collecting packages/conformance/tests/test_formula_framework.py
ModuleNotFoundError: No module named 'open_table_connector.conformance.formulas'
ERROR collecting specification/conformance/formulas/test_security.py
ModuleNotFoundError: No module named 'open_table_connector.conformance.formulas'
```

This confirmed the new framework/security tests were failing for the missing Task 6 conformance surface before implementation.

## GREEN Evidence

Focused framework/security command after implementation:

```bash
uv run --frozen python -m pytest packages/conformance/tests/test_formula_framework.py specification/conformance/formulas/test_security.py -q
```

Output:

```text
...................                                                      [100%]
19 passed in 0.04s
```

Required verification commands from the brief:

```bash
uv run --frozen python -m pytest packages/conformance/tests/test_formula_framework.py specification/conformance/formulas -q
uv run --frozen ruff check packages/conformance specification/conformance/formulas
git diff --check
```

Outputs:

```text
..............................                                           [100%]
30 passed in 0.35s
```

```text
All checks passed!
```

```text
[no output]
```

## Changed Files

- `packages/conformance/pyproject.toml`
- `packages/conformance/src/open_table_connector/conformance/__init__.py`
- `packages/conformance/src/open_table_connector/conformance/formulas.py`
- `packages/conformance/src/open_table_connector/conformance/static_suite.py`
- `packages/conformance/src/open_table_connector/conformance/timeseries.py`
- `packages/conformance/tests/test_formula_framework.py`
- `packages/conformance/tests/test_framework_import_lock.py`
- `packages/conformance/tests/test_reference_reader.py`
- `specification/conformance/formulas/conftest.py`
- `specification/conformance/formulas/support.py`
- `specification/conformance/formulas/test_contract.py`
- `specification/conformance/formulas/test_security.py`

## Implementation Notes

- Added `FormulaProviderCase`, typed grid/field case payloads, `load_formula_cases()`, receipt safety checks, capability-selected pytest parameter helpers, and reusable grid/field conformance assertions in `packages/conformance/src/open_table_connector/conformance/formulas.py`.
- Added framework tests that prove the helper catches the required broken behaviors: exact-text broadcast, leading-`=` inference, missing `dependency_scope`, field conversion, receipt leakage, stale revision acceptance, same-key/different-payload reuse, and advertised methods returning unsupported.
- Added reusable security-probe support and security tests under `specification/conformance/formulas`.
- Added the formulas package dependency to the conformance package.
- Applied minimal ruff-driven import cleanup in existing `packages/conformance` and `specification/conformance/formulas/test_contract.py` so the required lint command passes.

## Concerns

- No functional concerns remain from Task 6 itself.
- The only non-feature edits outside the new Formula framework files were minimal import-order / duplicate-import cleanups required to satisfy `uv run --frozen ruff check packages/conformance specification/conformance/formulas`.

## Fix Round 1 Evidence

Review fixes are implemented in the working tree; focused verification follows.

- Security probing is provider-case driven, captures actual warnings and logger output, and scans errors, receipts, warnings, reprs, ledger snapshots, and operation IDs.
- Set conformance only performs independent formula-text readback when the corresponding read capability is advertised.
- Forbidden evidence text is derived from submitted security, set, and conflicting expressions and probe values, including field cases.
- The normal grid fake uses the exact submitted source expression for copy-fill expectations; the sensitive expression is reserved for the security probe.
- Case uniqueness and pytest IDs include provider, target kind, and dialect; scalar receipts are accepted by the receipt safety helper.

RED command (the prior Task 6 baseline before these regressions were added):

```text
uv run --frozen python -m pytest packages/conformance/tests/test_formula_framework.py specification/conformance/formulas -q
38 passed in 0.35s
```

GREEN command:

```text
uv run --frozen python -m pytest packages/conformance/tests/test_formula_framework.py specification/conformance/formulas -q
......................................                                   [100%]
38 passed in 0.35s
```

Additional GREEN checks:

```text
uv run --frozen ruff check packages/conformance specification/conformance/formulas
All checks passed!
git diff --check
[no output]
```

Changed files:

- `packages/conformance/src/open_table_connector/conformance/formulas.py`
- `packages/conformance/tests/test_formula_framework.py`
- `specification/conformance/formulas/support.py`
- `specification/conformance/formulas/test_security.py`

Commit: pending after scoped review.

## Fix Round 2 Evidence

Reviewer findings addressed:

- `assert_formula_security_safe()` now validates that the target-specific SET capability is statically advertised before binding or invoking the setter. Reduced-capability grid and field fakes raise if an unadvertised setter is called.
- Security probing now checks the returned `FormulaExtensionResult` representation and its value representation. Exact formula text is masked only when it belongs to a typed formula observation/mutation value; other marker or formula leaks remain rejected. Regression fakes cover result and value representation leaks.

RED command:

```bash
uv run --frozen python -m pytest specification/conformance/formulas/test_security.py -q
```

Output:

```text
..FF......FF.                                                            [100%]
4 failed, 9 passed in 0.08s
```

The two capability cases reached an unadvertised setter, and the result/value representation leaks were not detected.

GREEN command:

```bash
uv run --frozen python -m pytest packages/conformance/tests/test_formula_framework.py specification/conformance/formulas/test_security.py -q
```

Output:

```text
...............................                                          [100%]
31 passed in 0.06s
```

Required checks:

```bash
uv run --frozen ruff check packages/conformance specification/conformance/formulas
All checks passed!

git diff --check
[no output]
```

Changed files:

- `packages/conformance/src/open_table_connector/conformance/formulas.py`
- `specification/conformance/formulas/support.py`
- `specification/conformance/formulas/test_security.py`
- `.superpowers/sdd/2026-09-01-formula-extension-core/task-6-report.md`

Commit: `fix: harden formula conformance security probes (round 2)`.

Concerns:

- No functional concerns remain for the two reviewer findings.
- The worktree had a pre-existing `uv.lock` modification; it was not included in this round-2 commit.
- `ruff format --check` reports pre-existing formatting drift in the touched files; no bulk reformat was applied to keep scope narrow.
