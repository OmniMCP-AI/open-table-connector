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
  packages/maybe_sheet/tests/test_connector.py \
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

## Fix Round 1

Reviewer findings addressed:

- Added capability-aware `CapabilityBinding` coverage to `ConnectorCase`, with a binding for every advertised capability.
- Split MaybeSheet fixture access into explicit base and sheet bindings so `sheet.read` produces `TableMode.SHEET` and a `sheet.read` receipt instead of silently reusing base mode.
- Added fixture-backed dbt bindings for `dbt.compile`, `dbt.run`, `dbt.cancel`, and `dbt.artifact.read`.
- Replaced the private pytest bootstrap dependency with lazy stdlib temporary-directory fixture creation inside the registry.
- Expanded discovery coverage to protect lazy bootstrap, `cases_with(...)`, full advertised capability binding coverage, MaybeSheet mode-specific reads, and dbt operation bindings.

### Red

Command:

```bash
uv run python -m pytest specification/conformance/universal/test_discovery.py -q
```

Output:

```text
..FFFF                                                                   [100%]
=================================== FAILURES ===================================
__________ test_all_cases_bootstrap_fixtures_without_pytest_configure __________
E   RuntimeError: universal connector fixtures are not configured
_____________ test_all_advertised_capabilities_have_case_bindings ______________
E   RuntimeError: universal connector fixtures are not configured
_____ test_cases_with_sheet_read_returns_mode_specific_maybe_sheet_binding ______
E   RuntimeError: universal connector fixtures are not configured
____________ test_dbt_capabilities_expose_fixture_backed_operations ____________
E   RuntimeError: universal connector fixtures are not configured
=========================== short test summary info ============================
FAILED specification/conformance/universal/test_discovery.py::test_all_cases_bootstrap_fixtures_without_pytest_configure
FAILED specification/conformance/universal/test_discovery.py::test_all_advertised_capabilities_have_case_bindings
FAILED specification/conformance/universal/test_discovery.py::test_cases_with_sheet_read_returns_mode_specific_maybe_sheet_binding
FAILED specification/conformance/universal/test_discovery.py::test_dbt_capabilities_expose_fixture_backed_operations
4 failed, 2 passed in 0.09s
```

Observed result: the new tests reproduced the missing lazy bootstrap and missing capability-bound operation surface.

### Green

Command:

```bash
uv run python -m pytest specification/conformance/universal/test_discovery.py -q
```

Output:

```text
......                                                                   [100%]
6 passed in 0.05s
```

Observed result: the registry now lazy-bootstraps fixtures, binds every advertised capability, keeps MaybeSheet base/sheet reads distinct, and exposes working dbt fixture operations.

### Broader Verification

Command:

```bash
uv run python -m pytest \
  specification/conformance/universal/test_discovery.py \
  packages/google_sheets/tests/test_connector.py \
  packages/feishu_bitable/tests/test_connector.py \
  packages/maybe_sheet/tests/test_connector.py \
  packages/sqlite/tests/test_reader.py \
  packages/postgres/tests/test_reader.py \
  packages/dbt/tests/test_connector.py \
  packages/local_files/tests/test_conformance.py \
  packages/local_files/tests/test_excel_reader.py -q
```

Output:

```text
.........................................                                [100%]
41 passed in 0.20s
```

Observed result: the registry fixes stayed offline and deterministic and did not regress the existing connector-focused test slice.

### Files Changed In Fix Round

- `specification/conformance/universal/__init__.py`
- `specification/conformance/universal/cases.py`
- `specification/conformance/universal/conftest.py`
- `specification/conformance/universal/fixtures.py`
- `specification/conformance/universal/test_discovery.py`

### Remaining Concerns

- The registry now uses a stdlib `TemporaryDirectory` for lazy fixture creation, which avoids pytest internals but still leaves cleanup to process exit rather than per-test teardown. That is stable for this suite, though future tests that need fixture isolation may want explicit override hooks via `configure_fixture_bundle(...)`.
