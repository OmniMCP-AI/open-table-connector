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

## Fix Round 1

Date: 2026-08-28

This round supersedes the original selection-recording and cyclic-replay
concerns above.

### Implementation Commit

`931386e2d686135496a32ea25261166f18a558fe` — `test: tighten universal table conformance`

### Reviewer Findings Addressed

- Feishu projection is now observed where the real adapter reads provider field
  values. The fixture includes an unselected `internal_only` field, and the
  tests require exactly `name`, `score`, and `note` to be consumed and exposed.
- Google, Feishu, and MaybeSheet assertions now match complete fixture URLs,
  endpoints, queries, argv, flags, targets, and literal fixture credentials.
- Google failure coverage now injects a raw non-`ConnectorError` through
  `UrllibSheetsTransport` and verifies adapter mapping and credential safety.
- Sheet coordinates are scenario-specific, collection parameters no longer
  construct live connector cases at import time, and HTTP response queues fail
  closed when their explicit replay budget is exhausted.
- Provider state uses typed HTTP/process fixture handles with explicit raw
  failure probes instead of the generic recording union and untyped hook.

### TDD Evidence

Red:

```text
uv run python -m pytest specification/conformance/universal/test_table_connectors.py -q
3 failed, 59 passed in 0.79s
```

The failures were the missing Feishu field-use observation, cyclic HTTP
over-consumption, and the already-normalized Google failure fixture.

Green:

```text
uv run python -m pytest specification/conformance/universal/test_table_connectors.py -q
62 passed in 0.61s
```

### Verification

- Focused table/contract/discovery tests: `128 passed in 1.21s`.
- Universal suite: `128 passed in 1.22s`.
- Google Sheets, Feishu Bitable, MaybeSheet, and local-files regressions:
  `40 passed in 0.67s`.
- Full workspace suite: `314 passed in 4.61s`.
- `uv run python -m compileall -q specification/conformance/universal` — passed.
- `git diff --check` — passed.

### Concerns

- Production connectors were intentionally unchanged. Feishu projection remains
  client-side, so the conformance boundary records the provider field values
  consumed by the production projection function rather than claiming the
  provider URL carries unsupported projection parameters.
- Replay remains finite and deterministic: current fixtures explicitly budget
  three Google reads and three Feishu page pairs for same-case contract checks;
  any additional response consumption raises an assertion.

## Fix Round 2

Date: 2026-08-28

### Implementation Commit

`e8abd13b9fd9d6f67b11260e5ac91b3c5253fa3e` — `fix: redact Google Sheets transport errors`

### Reviewer Finding Addressed

- The universal Google raw-failure fixture now raises a provider exception whose
  message contains the known fixture credential. `UrllibSheetsTransport` maps
  arbitrary exception diagnostics to the stable safe reason `unexpected
  transport exception`, preserving the existing error code, public message, and
  `safe_details["reason"]` shape without exposing the provider message.
- A focused production regression exercises the real `urlopen` error-mapping
  boundary and verifies that the credential is absent from the serialized
  `ConnectorError`.

### TDD Evidence

Red:

```text
uv run python -m pytest packages/google_sheets/tests/test_connector.py::test_google_sheets_transport_redacts_credentials_from_provider_errors specification/conformance/universal/test_table_connectors.py::test_provider_failures_map_to_safe_redacted_errors -q -k 'google'
2 failed, 2 deselected in 0.14s
```

Both failures showed the injected credential-bearing provider message copied
verbatim into `safe_details["reason"]`.

Green:

```text
uv run python -m pytest packages/google_sheets/tests/test_connector.py::test_google_sheets_transport_redacts_credentials_from_provider_errors specification/conformance/universal/test_table_connectors.py::test_provider_failures_map_to_safe_redacted_errors -q -k 'google'
2 passed, 2 deselected in 0.04s
```

### Verification

- Google Sheets regressions: `6 passed in 0.47s`.
- Focused table universal suite: `62 passed in 0.60s`.
- Universal suite: `128 passed in 1.63s`.
- Google Sheets, Feishu Bitable, MaybeSheet, and local-files regressions:
  `41 passed in 0.61s`.
- Full workspace suite: `315 passed in 4.79s`.
- `uv run python -m compileall -q packages specification/conformance/universal`
  — passed.
- `git diff --check` — passed.

### Concerns

- Safe Google transport errors no longer expose raw provider diagnostics. The
  stable generic reason intentionally trades diagnostic specificity for
  credential safety; the existing error code and public message remain
  unchanged.
- No unrelated connector error boundaries were changed in this narrowly scoped
  production fix.
