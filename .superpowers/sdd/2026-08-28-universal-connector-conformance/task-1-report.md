# Task 1 Report

Date: 2026-08-28

## Files Changed

- `specification/conformance/universal/__init__.py`
- `specification/conformance/universal/cases.py`
- `specification/conformance/universal/conftest.py`
- `specification/conformance/universal/fixtures.py`
- `specification/conformance/universal/test_discovery.py`

## TDD Flow

### Red

Command:

```bash
uv run python -m pytest specification/conformance/universal/test_discovery.py -q
```

Output:

```text
==================================== ERRORS ====================================
____ ERROR collecting specification/conformance/universal/test_discovery.py ____
ImportError while importing test module '/Users/admin/Code/GitHub/open-table-connectors/specification/conformance/universal/test_discovery.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
specification/conformance/universal/test_discovery.py:5: in <module>
    from specification.conformance.universal.cases import all_cases, case
E   ModuleNotFoundError: No module named 'specification.conformance.universal.cases'
=========================== short test summary info ============================
ERROR specification/conformance/universal/test_discovery.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.09s
```

Observed result: expected red phase failure because the registry module did not yet exist.

### Green

Command:

```bash
uv run python -m pytest specification/conformance/universal/test_discovery.py -q
```

Output:

```text
..                                                                       [100%]
2 passed in 0.01s
```

Observed result: discovery registry now resolves the seven named cases and rejects unknown lookups.

## Broader Verification

Command:

```bash
uv run python -m pytest \
  packages/google_sheets/tests/test_connector.py \
  packages/feishu_bitable/tests/test_connector.py \
  packages/maybesheet/tests/test_connector.py \
  packages/sqlite/tests/test_reader.py \
  packages/postgres/tests/test_reader.py \
  packages/dbt/tests/test_connector.py \
  packages/local_files/tests/test_conformance.py \
  packages/local_files/tests/test_excel_reader.py -q
```

Output:

```text
...................................                                      [100%]
35 passed in 0.61s
```

Observed result: the new universal fixture boundary did not regress the existing connector-focused tests.

## Notes

- The universal registry uses deterministic recording doubles for Google Sheets, Feishu Bitable, MaybeSheet, Postgres, and dbt.
- Local file and SQLite fixtures are created under pytest-managed temporary paths, not repository paths.
- No credentials, network calls, vendor binaries, or external databases are required by the new registry.

## Concerns

- `specification/conformance/universal/conftest.py` bootstraps temporary fixture paths through pytest's internal `TempPathFactory.from_config(...)` API so case data exists before collection-time `all_cases()` calls. If pytest changes that internal entry point, this bootstrap may need a small follow-up adjustment.
