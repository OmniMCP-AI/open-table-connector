# Task 3 report — portable Excel worksheet materialization

## Implementation

- Added a structured `SheetModeDestination` worksheet field while retaining old
  destination wire compatibility; profiled Excel materialization accepts either
  it or the legacy `file:///...xlsx#sheet=Name` shorthand.
- Advertised the exact portable create capability for local-file sheet mode.
- Added create-only portable worksheet publication using the existing workbook
  provider transaction.  It creates the destination worksheet and a unique,
  very-hidden adapter metadata worksheet in one revision-checked commit.
- Metadata contains an immutable table ID, exact destination binding, schema,
  row count, and schema fingerprint.  Typed reads require valid metadata and
  recover String, Boolean, Int64, Float64, Decimal, Date, and UTC microsecond
  datetime values without Excel numeric inference.
- Returned portable Excel bindings carry a durable `SheetModeTableAddress`
  table ID; fresh opens by that address find the matching metadata record rather
  than relying on the mutable sheet URL.  Legacy lexical Excel materialization
  remains on its original implementation path.
- Mutation/readback failures after commit retain ordered receipts and report
  `READBACK_MISMATCH`; case-folded worksheet conflicts report
  `DESTINATION_EXISTS` and provider revision conflicts map to `STALE_REVISION`.

## Tests

`packages/local_files/tests/test_portable_excel_materialization.py` covers
structured destinations/wire round-trip, all admitted portable scalars,
Unicode and empty strings, exact Int64 limits, decimal/date/UTC datetime
recovery, all-null and zero-row frames, preservation of unrelated workbook
content, case-insensitive conflicts, and metadata tampering.

## TDD evidence

Initial RED run:

```text
./.venv/bin/pytest packages/local_files/tests/test_portable_excel_materialization.py -q
4 failed
```

The failures were the expected missing structured destination and missing
sheet-mode portable capability/implementation paths.

Final verification:

```text
./.venv/bin/pytest packages/local_files/tests/test_portable_excel_materialization.py packages/local_files/tests/test_excel_table_materialize.py packages/sdk/tests/test_model.py -q
25 passed

./.venv/bin/ruff check <changed source and test files>
All checks passed

git diff --check
exit 0
```

## Concerns

- Excel stores portable values lexically, with typed recovery intentionally
  dependent on adapter-owned metadata.  Direct legacy sheet URLs without valid
  metadata remain lexical reads.
- Polars currently emits deprecation warnings for String-to-Date/Datetime casts
  in the independent typed recovery test; these do not affect the test result
  but should be updated to explicit string parsing before Polars 2.0.
