# Task 4 implementation report

Status: complete

Changed files:

- `packages/cli/src/open_table_connector/cli/adapters.py`
- `packages/cli/src/open_table_connector/cli/registry.py`
- `packages/cli/tests/test_registry.py`

Commits:

- `433dab9 feat: add otc connector registry`

Tests and results:

- `uv run python -m pytest packages/cli/tests/test_registry.py -q` — 5 passed
- `uv run python -m pytest packages/cli/tests -q` — 18 passed
- `uv run python -m pytest packages/google_sheets/tests packages/feishu_bitable/tests packages/maybe_sheet/tests -q` — 15 passed
- `uv run python -m compileall -q packages/cli/src/open_table_connector/cli` — passed
- `git diff --check` — passed

Concerns:

- The task brief's exact command `uv run pytest ...` could not spawn `pytest` in this environment; the equivalent `uv run python -m pytest ...` command was used successfully.
- Local inspection/write receipts use the existing neutral contract with a stable local marker; local file contents and credentials are not included in diagnostics.

Deviations:

- Added two deterministic registry adapter tests beyond the three brief examples to cover injected Google transport translation, CLI-token precedence, and unsupported HTTPS host rejection.

## Review-fix round

Status: complete

Changes:

- Fixed Google Sheets and Feishu Bitable inspection adapters to retain `options` while constructing their credentialed provider connectors.
- Removed unsupported `sheet.read` and `sheet.inspect` capabilities from MaybeSheet. The Task 4 `maybe://DOCUMENT/TARGET` grammar dispatches base-table reads/inspection only, so unsupported sheet capability requests now fail in the registry before process I/O.
- Added regression coverage for both injected inspection transports and MaybeSheet capability rejection/process-call absence.

Commit:

- `b45ce3c fix: correct task 4 adapter capabilities`

Tests and results:

- Red regression run: `uv run python -m pytest packages/cli/tests/test_registry.py -q` — 5 passed, 3 failed with the two `UnboundLocalError` inspection failures and the false-positive MaybeSheet capability assertion.
- Green focused run: `uv run python -m pytest packages/cli/tests/test_registry.py -q` — 8 passed
- `uv run python -m pytest packages/cli/tests -q` — 21 passed
- `uv run python -m pytest packages/google_sheets/tests packages/feishu_bitable/tests packages/maybe_sheet/tests -q` — 15 passed
- `git diff --check` — passed

Concerns:

- MaybeSheet sheet-mode capabilities remain intentionally unavailable because the specified CLI grammar provides only base-table dispatch; no process call is made for rejected sheet capability requests.

## Final-review fix round

Status: complete

Changed files:

- `packages/cli/src/open_table_connector/cli/adapters.py`
- `packages/cli/src/open_table_connector/cli/pipeline.py`
- `packages/cli/tests/test_pipeline.py`
- `packages/cli/tests/test_registry.py`

Changes:

- Added an optional `preflight_write(endpoint, options)` adapter seam. `import_endpoint` invokes it immediately after destination capability validation and before reading the source, while test doubles without the method remain supported.
- MaybeSheet now rejects `error` and `replace` policies in preflight with `UNSUPPORTED_CAPABILITY` and safe `if_exists` details; append remains supported.
- Feishu rejects replace and invalid policies before source I/O. Error-policy imports read the destination first and raise `CONFLICT` when rows exist; empty destinations proceed to append.
- Google Sheets validates policies before source I/O. Error-policy imports read the destination first and raise `CONFLICT` when rows exist; empty destinations proceed to write. Append and replace remain supported.
- Local receipts now use Arrow content fingerprints, content-derived source revisions, and `operation_identity` over the local URI, capability, schema, and content. Read/inspect receipts use `table.read.arrow`; writes use `table.write`.
- Added regression tests for policy ordering, duplicate detection, empty destination behavior, invalid policies, injected transport/process call safety, and distinct local receipt identities.

Commit:

- `7c9181b fix: preflight connector writes and local receipts`

Tests and results:

- Red focused run: `uv run python -m pytest packages/cli/tests/test_registry.py packages/cli/tests/test_pipeline.py -q` — 20 passed, 8 failed, reproducing constant local receipts, source reads before preflight, missing duplicate conflicts, and missing empty-destination preflight.
- Green focused run: `uv run python -m pytest packages/cli/tests/test_registry.py packages/cli/tests/test_pipeline.py -q` — 28 passed
- `uv run python -m pytest packages/cli/tests -q` — 53 passed
- `uv run python -m pytest packages/google_sheets/tests packages/feishu_bitable/tests packages/maybe_sheet/tests -q` — 17 passed
- `uv run python -m compileall -q packages/cli/src/open_table_connector/cli` — passed
- `git diff --check` — passed

Concerns:

- Destination error-policy preflight intentionally performs a provider read before source I/O; injected transports/processes were used for all tests and no live network was used.
- The direct `uv run pytest` executable remains unavailable in this environment; equivalent `uv run python -m pytest` invocations passed.

Deviations:

- No output, command, packaging, or provider package files were changed.

## Final re-review limits and MaybeSheet URL fix

Status: complete

Changed files:

- `packages/cli/src/open_table_connector/cli/adapters.py`
- `packages/cli/tests/test_pipeline.py`
- `packages/cli/tests/test_registry.py`
- `packages/google_sheets/src/open_table_connector/google_sheets/connector.py`
- `packages/google_sheets/tests/test_connector.py`

Changes:

- Local adapter reads now apply `CliOptions.limit` before returning the Arrow table, so local receipts, pipeline row counts, and destination writes reflect the limited table.
- Google Sheets connector reads now apply `ResourceLimits.max_rows` after header parsing and before receipt construction, so direct reads and imports report and write only the limited rows.
- MaybeSheet HTTPS document URLs now require explicit `options.target`; missing targets produce safe `INVALID_URI` errors before source or process I/O. The opaque `maybe://DOCUMENT/TARGET` grammar remains unchanged.
- Preserved the explicit MaybeSheet write credential path introduced by `826879e`.
- Added focused registry, pipeline, and provider regressions for all three fixes.

Commit:

- `370d962 fix: enforce adapter row limits and maybe targets`

Tests and results:

- Red focused missing-target import regression: `uv run python -m pytest packages/cli/tests/test_pipeline.py::test_maybe_sheet_https_missing_target_is_rejected_before_source_or_process_io -q` — failed because source read count was 1 instead of 0.
- Green focused run: `uv run python -m pytest packages/cli/tests/test_registry.py packages/cli/tests/test_pipeline.py packages/google_sheets/tests/test_connector.py -q` — 39 passed
- `uv run python -m pytest packages/cli/tests -q` — 66 passed
- `uv run python -m pytest packages/google_sheets/tests packages/feishu_bitable/tests packages/maybe_sheet/tests -q` — 19 passed
- `uv run python -m compileall -q packages/cli/src/open_table_connector/cli packages/google_sheets/src/open_table_connector/google_sheets` — passed
- `git diff --check` — passed

Concerns:

- Local and Google limits are applied after the underlying codec/provider response is fetched, then before the returned table and receipt are built; returned/imported row counts are bounded as required.
- The direct `uv run pytest` executable remains unavailable in this environment; equivalent `uv run python -m pytest` invocations passed.

Deviations:

- No output, command, or packaging files were changed. The Google connector source and tests were updated because the requested limit behavior is part of its public read path.

## Final re-review adapter identity, modes, limits, and timeout fix

Status: complete

Changed files:

- `packages/cli/src/open_table_connector/cli/adapters.py`
- `packages/cli/tests/test_registry.py`
- `packages/maybe_sheet/src/open_table_connector/maybe_sheet/connector.py`
- `packages/maybe_sheet/src/open_table_connector/maybe_sheet/process.py`
- `packages/maybe_sheet/tests/test_connector.py`

Changes:

- Local receipts now use canonical resolved filesystem URIs and the stable `stdio://stdin` URI for stdin; no `file:///None` or malformed slash-prefixed identities are produced.
- LocalAdapter and MaybeSheetAdapter now expose `(TableMode.BASE,)` for accurate connector discovery.
- `_limits` now rounds positive fractional CLI timeouts up with `ceil`, preserving the contract's positive integer timeout requirement. Google and Feishu inspection adapters pass limits through `InspectRequest`, so row and timeout options reach their provider reads and inspection receipts.
- MaybeSheet read requests now pass per-request timeouts to compatible process clients. SubprocessProcessClient accepts a per-call timeout override while retaining its fixed default, and the connector omits the new keyword for older injected fake clients that do not support it.
- Preserved the explicit MaybeSheet write credential behavior from `826879e` and the existing Google max-row enforcement.
- Added regressions for canonical file/stdin receipts, adapter modes, bounded Google/Feishu inspection with fractional timeouts, and MaybeSheet timeout compatibility.

Commit:

- `9fe142f fix: preserve adapter modes and request limits`

Tests and results:

- Red focused run: `uv run python -m pytest packages/cli/tests/test_registry.py packages/cli/tests/test_pipeline.py packages/google_sheets/tests/test_connector.py packages/maybe_sheet/tests/test_connector.py -q` — 48 passed, 7 failed, reproducing all newly covered identity, modes, inspect-limit/timeout, and MaybeSheet timeout gaps.
- Green focused run: same command — 55 passed
- `uv run python -m pytest packages/cli/tests -q` — 71 passed
- `uv run python -m pytest packages/google_sheets/tests packages/feishu_bitable/tests packages/maybe_sheet/tests -q` — 21 passed
- `uv run python -m compileall -q packages/cli/src/open_table_connector/cli packages/google_sheets/src/open_table_connector/google_sheets packages/maybe_sheet/src/open_table_connector/maybe_sheet` — passed
- `git diff --check` — passed

Concerns:

- Local and Google row limits are applied after the underlying file/API payload is fetched, then before returned tables and receipts are built; bounded tables, receipts, inspections, and pipeline summaries are correct.
- Older injected MaybeSheet process clients without a `timeout` keyword remain supported; only timeout-capable clients receive the per-request value.
- The direct `uv run pytest` executable remains unavailable in this environment; equivalent `uv run python -m pytest` invocations passed.

Deviations:

- No output, command, packaging, or registry implementation files were changed. MaybeSheet provider/process source was updated because per-request timeout behavior is part of its public process/read path.

## Final re-review adapter identity and opaque URI fix

Status: complete

Changed files:

- `packages/cli/src/open_table_connector/cli/adapters.py`
- `packages/cli/tests/test_registry.py`
- `.superpowers/sdd/2026-08-27-open-table-connector-cli/task-4-report.md`

Changes:

- Local inspection now uses the same canonical local URI helper as local receipts: resolved filesystem paths use `Path.resolve().as_uri()`, while stdin uses `stdio://stdin`. Its base inspection convention now uses the local read receipt's content-derived source revision.
- MaybeSheet opaque URIs are now validated as exactly `maybe://DOCUMENT/TARGET`: the document/netloc and one target path segment must be non-empty, with no extra path segments, query, or fragment. Validation occurs before the injected process client is called, and explicit `options.target` does not bypass malformed URI validation.
- Preserved HTTPS MaybeSheet document behavior requiring an explicit target and preserved all existing credential, limit, timeout, capability, and transport-injection fixes.
- Added regressions for relative local paths, stdin inspection identities/source revisions, malformed opaque MaybeSheet URI forms, safe error details, and zero process calls.

Commit:

- `516f8a6 fix: validate adapter inspection identities and maybe uris`

Tests and results:

- Red focused run: `uv run python -m pytest packages/cli/tests/test_registry.py -q` — 15 passed, 7 failed, reproducing the incorrect local inspection identities/convention and malformed MaybeSheet URI acceptance.
- Green focused run: `uv run python -m pytest packages/cli/tests/test_registry.py packages/cli/tests/test_pipeline.py packages/google_sheets/tests/test_connector.py packages/feishu_bitable/tests/test_connector.py packages/maybe_sheet/tests/test_connector.py -q` — 66 passed.
- Full CLI suite: `uv run python -m pytest packages/cli/tests -q` — 79 passed.
- `git diff --check` — passed.

Concerns:

- Local stdin inspection consumes the injected stdin stream once, as local reads already do; the inspection URI and source revision remain stable and credential-free.
- MaybeSheet URI validation intentionally rejects query and fragment components because the supported opaque grammar is exact; HTTPS target handling remains unchanged.
- The direct `uv run pytest` executable remains unavailable in this environment; equivalent `uv run python -m pytest` commands passed.

Deviations:

- No output, command, packaging, or provider package files were changed; this fix was confined to the CLI adapter and registry tests plus this report.

## Final re-review registry scheme classification fix

Status: complete

Changed files:

- `packages/cli/src/open_table_connector/cli/registry.py`
- `packages/cli/tests/test_registry.py`
- `.superpowers/sdd/2026-08-27-open-table-connector-cli/task-4-report.md`

Changes:

- `ConnectorRegistry.connector_for` now tracks whether any adapter advertises the endpoint scheme. An entirely unknown scheme raises `UNSUPPORTED_CAPABILITY`, which maps to exit code 3, with only the safe scheme detail.
- Known schemes that fail provider-specific host or URI validation still raise `INVALID_URI`; the existing safe HTTPS host detail behavior is preserved.
- Added regression coverage for unknown connector schemes and retained the unknown-HTTPS-host regression.

Commit:

- `637e7b3 fix: classify unknown connector schemes`

Tests and results:

- Red regression: `uv run python -m pytest packages/cli/tests/test_registry.py::test_registry_reports_unknown_connector_scheme_as_unsupported_capability -q` — failed with `INVALID_URI` before the registry distinction was implemented.
- Green focused registry run: `uv run python -m pytest packages/cli/tests/test_registry.py -q` — 23 passed.
- Full CLI suite: `uv run python -m pytest packages/cli/tests -q` — 88 passed.
- `git diff --check` — passed.

Concerns:

- Pre-existing changes to `packages/cli/src/open_table_connector/cli/model.py` and `packages/cli/tests/test_model.py` remain in the worktree and were intentionally not staged or modified by this fix.
- The direct `uv run pytest` executable remains unavailable in this environment; equivalent `uv run python -m pytest` commands passed.

Deviations:

- No output, command, packaging, adapter, or provider files were changed; this fix was confined to the CLI registry, registry tests, and this report.
