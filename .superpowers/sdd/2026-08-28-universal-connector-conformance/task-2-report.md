# Task 2 Report

Date: 2026-08-28

## Files Changed

- `specification/conformance/universal/assertions.py`
- `specification/conformance/universal/conftest.py`
- `specification/conformance/universal/test_discovery.py`
- `specification/conformance/universal/test_contract.py`

## TDD Flow

### Red

Command:

```bash
uv run python -m pytest specification/conformance/universal/test_discovery.py specification/conformance/universal/test_contract.py -q
```

Output:

```text
==================================== ERRORS ====================================
____ ERROR collecting specification/conformance/universal/test_discovery.py ____
ImportError while importing test module '/Users/admin/Code/GitHub/open-table-connectors/specification/conformance/universal/test_discovery.py'.
Traceback:
specification/conformance/universal/test_discovery.py:9: in <module>
    from specification.conformance.universal.assertions import (
E   ModuleNotFoundError: No module named 'specification.conformance.universal.assertions'
____ ERROR collecting specification/conformance/universal/test_contract.py _____
ImportError while importing test module '/Users/admin/Code/GitHub/open-table-connectors/specification/conformance/universal/test_contract.py'.
Traceback:
specification/conformance/universal/test_contract.py:10: in <module>
    from specification.conformance.universal.assertions import (
E   ModuleNotFoundError: No module named 'specification.conformance.universal.assertions'
=========================== short test summary info ============================
ERROR specification/conformance/universal/test_discovery.py
ERROR specification/conformance/universal/test_contract.py
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!!
2 errors in 0.13s
```

Observed result: the new discovery and contract tests failed immediately because the shared assertion module did not exist yet.

### Green

Command:

```bash
uv run python -m pytest specification/conformance/universal/test_discovery.py specification/conformance/universal/test_contract.py -q
```

Output:

```text
.........................................................                [100%]
57 passed in 0.83s
```

Observed result: the new universal discovery and contract invariants pass across the seven named cases using only offline deterministic fixtures and test-side helpers.

## Broader Verification

Command:

```bash
uv run python -m pytest specification/conformance/universal/test_discovery.py specification/conformance/universal/test_contract.py packages/google_sheets/tests/test_connector.py packages/feishu_bitable/tests/test_connector.py packages/maybesheet/tests/test_connector.py packages/sqlite/tests/test_reader.py packages/postgres/tests/test_reader.py packages/dbt/tests/test_connector.py packages/local_files/tests/test_conformance.py packages/local_files/tests/test_excel_reader.py -q
```

Output:

```text
........................................................................ [ 78%]
....................                                                     [100%]
92 passed in 0.69s
```

Observed result: the shared invariant helpers and fixtures did not regress the existing connector-level offline test slice that backs the universal suite.

## What Changed

- Added `specification/conformance/universal/assertions.py` with pure assertion helpers for connector identity round-trips, manifest/capability uniqueness, safe URIs, safe errors, and receipt wire/metadata validation.
- Expanded `specification/conformance/universal/test_discovery.py` to cover identity closure, stable case ordering, capability wire shape, manifest-backed capability invariants, and mode validation without introducing networked or credentialed setup.
- Added `specification/conformance/universal/test_contract.py` to cover absolute credential-free URIs, invalid credential-bearing URI rejection, safe error wire keys, closed receipt wire keys, deterministic read metadata, and safe write receipts.
- Extended `specification/conformance/universal/conftest.py` with deterministic test-only fixtures for invalid credential-bearing URIs, write frames, case-specific write policies and expected affected-row counts, plus capability identity/manifest accessors for manifest-backed and identity-only connectors.

## Concerns

- `dbt` remains an identity-only universal case for this suite: it has capability bindings and schemes but no connector manifest or table modes, so the new tests intentionally validate its capability wire shape and stable empty mode set without forcing it through `CapabilityManifest`.
- The shared sqlite case still does not expose a table-specific inspect request through the Task 1 boundary, so Task 2’s deterministic inspection test excludes `sqlite` and covers its deterministic metadata through read and write receipts instead.
- The MaybeSheet write fixture intentionally returns `affected_rows == 1` for a two-row append receipt in the recorded process response. The suite now locks that deterministic fixture value in place; if the fixture contract changes later, that expectation will need to change with it.
