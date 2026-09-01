# Task 7 Report

Date: 2026-09-02
Task: Core Formula Extension, Task 7 review finding
Branch: `codex/formula-extension`
Commit: `fix: harden disabled formula discovery checkpoint`

## RED

Command:

```bash
uv run --frozen python -m pytest specification/conformance/universal/test_discovery.py::test_unknown_formula_capability_is_rejected_by_disabled_discovery_checkpoint -q
```

Result: failed with `NameError` because the regression's checkpoint helper did not yet exist.

## GREEN

Command:

```bash
uv run --frozen python -m pytest specification/conformance/universal/test_discovery.py -q
```

Result: `65 passed in 0.46s`.

Additional checks:

```bash
uv run --frozen ruff check specification/conformance/universal/test_discovery.py
git diff --check
```

Both completed successfully.

## Changed Files

- `specification/conformance/universal/test_discovery.py`
- `.superpowers/sdd/2026-09-01-formula-extension-core/task-7-report.md`

The disabled-discovery checkpoint now rejects every advertised capability identity beginning with `formula.`, including unknown future identities. The regression passes an unknown `formula.future.calculate` identity directly to the checkpoint helper, without modifying descriptor fixtures.

## Concerns

- None.

## Round 2 Correction Evidence

### RED

Command:

```bash
uv run --frozen python -m pytest specification/conformance/universal/test_discovery.py::test_unknown_formula_capability_is_rejected_by_disabled_discovery_checkpoint -q
```

Result: failed as intended because the helper raised `AssertionError("fixture")`, which did not include `formula.future.calculate`.

### GREEN

Commands:

```bash
uv run --frozen python -m pytest specification/conformance/universal/test_discovery.py::test_unknown_formula_capability_is_rejected_by_disabled_discovery_checkpoint -q
uv run --frozen python -m pytest specification/conformance/universal/test_discovery.py -q
uv run --frozen ruff check specification/conformance/universal/test_discovery.py
git diff --check
```

Results: focused test passed (`1 passed`); universal discovery suite passed (`65 passed`); Ruff and `git diff --check` completed successfully. The checkpoint now reports the connector identity and every offending `formula.*` identity, while the regression fixture remains an unknown future capability.

### Commit Details

- Conventional Commit: `fix(test): diagnose disabled formula capabilities`
- Files: `specification/conformance/universal/test_discovery.py` and this report only.
