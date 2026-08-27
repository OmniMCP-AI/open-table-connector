# Task 3 Report

Date: 2026-08-28

## Implementation Commit

`fcb90d53ea84e70131ae688ae3914f3b40bf5999` — `test: add universal table connector conformance`

## Files Changed

- `specification/conformance/universal/cases.py`
- `specification/conformance/universal/fixtures.py`
- `specification/conformance/universal/test_table_connectors.py`

No production connector implementation was changed.

## TDD Evidence

### Red

Command:

```bash
uv run python -m pytest specification/conformance/universal/test_table_connectors.py -q
```

Result:

```text
25 failed, 36 passed in 0.93s
```

The expected failures covered missing recording/failure handles, incomplete
provider payloads and pagination, absent selected range/field state, one-row
MaybeSheet responses, incorrect fixture affected-row counts, and incomplete
CSV/XLSX fixtures.

A later provider-failure refinement was also driven red first:

```bash
uv run python -m pytest specification/conformance/universal/test_table_connectors.py -q -k 'provider_failures and google'
```

```text
1 failed, 60 deselected in 0.20s
```

The failure proved the Google case still exercised authentication rather than
a recorded provider error.

### Green

Command:

```bash
uv run python -m pytest specification/conformance/universal/test_table_connectors.py -q
```

Result:

```text
61 passed in 0.63s
```

## Verification

- `uv run python -m pytest specification/conformance/universal -q` — `127 passed in 1.23s`.
- Relevant Google Sheets, Feishu Bitable, MaybeSheet, and local-files regression tests — `40 passed in 0.41s`.
- `uv run python -m compileall -q specification/conformance/universal` — passed.
- `git diff --check` — passed.
- Independent read-only review completed; two alleged critical failures were
  disproved by the focused green run and contract behavior. The useful
  selection-recording feedback was incorporated by deriving recorded fields
  and ranges from the actual request objects.

## Coverage Added

- Arrow/Polars parity, stable columns, receipt fingerprints, inspections, and
  coordinate conventions.
- Bounded over-returned rows, timeout/limit propagation, Feishu pagination,
  and repeated-read determinism.
- Write request shapes, affected-row counts, supported/unsupported policies,
  Feishu `_record_id`, and MaybeSheet stdin JSONL.
- Provider failure redaction and credential locality.
- Local CSV/XLSX fixtures with empty cells and mixed values.

## Concerns

- Feishu field selection is currently applied client-side by the public
  connector rather than encoded in the provider URL. Because production
  connectors were explicitly out of scope, the universal case records fields
  from the actual `FeishuBitableReadRequest` and verifies the resulting stable
  columns; a future production change that adds provider-side projection
  should tighten the URL assertion.
- The HTTP recording fixture cycles deterministic page payloads so repeated
  reads can replay the same multi-page response. URL and page-token assertions
  remain responsible for detecting incorrect pagination requests.
