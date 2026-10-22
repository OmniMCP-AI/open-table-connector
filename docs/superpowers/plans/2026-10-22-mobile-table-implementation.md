# OTC Mobile Table UI and HTTP Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the versioned OTC mobile-table HTTP contract, a qualified read/update host bridge, and matching H5 and WeChat renderers for the confirmed phone/iPad card and table UI.

**Architecture:** Keep the wire contract and reference adapter in this Python repository. Add an optional record-update hook to the SDK so connectors without stable IDs, revisions, idempotency, and readback remain read-only. Put the shared TypeScript controller in a consumer package with separate H5 Web Component and WeChat WXML renderers; both renderers consume the same controller state and fixtures.

**Tech Stack:** Python 3.11+, dataclasses, `jsonschema`, pytest, Ruff, mypy, existing OTC SDK/connector protocols, TypeScript, Vitest, semantic HTML/Web Components, and native WeChat WXML/WXSS.

**Spec:** [docs/superpowers/specs/2026-10-22-mobile-table-ui-design.md](/Users/tonyzhang/Code/GitHub/open-table-connector/docs/superpowers/specs/2026-10-22-mobile-table-ui-design.md)

## Global Constraints

- The contract identity is `otc.mobile.table/1.0`.
- The default page size is 25; the maximum page size is 100 or the provider-advertised lower bound.
- A request may select at most 50 fields. A record patch may contain at most 10 fields and 16 KiB of UTF-8 JSON.
- A controller has at most one read and one mutation in flight; stale read generations must be ignored.
- Safe reads may retry once after transport failure. Mutations never retry automatically; an explicit retry reuses the original idempotency key.
- A stable provider record ID and live capability evidence are required before any record becomes editable.
- The title control row is ordered left-to-right as Card/Table selector, server-reported record count, sync status plus icon-only refresh.
- Phones use a single-column card list. iPad uses an auto-fitting multi-column card grid and a wider table viewport.
- Table column resizing is bounded, applies to header and rows for the current session, and is not persisted in v1.
- Neither renderer provides inline cell editing, bulk edits, column reorder/hide/show, column insert/delete, autosave, offline queues, or force overwrite in v1.
- Credentials never appear in `table_uri`, payload values, logs, or receipts. Logs contain request/operation IDs and safe outcome metadata only.
- A provider without qualified record-level update guarantees returns `unsupported_capability` before dispatch and remains browseable.

## Review Focus

- **Closed envelopes and redaction:** unknown request fields, unknown response fields, secret-looking keys, and provider exception text must be rejected or redacted. Test in Task 1 and Task 3.
- **Cursor/revision races:** stale continuation tokens and refresh responses must not append rows to a newer source revision. Test in Task 3 and Task 4.
- **Value fidelity:** `null`, `false`, zero, empty string, numbers, and numeric-looking strings must survive the wire and renderer unchanged. Test in Task 1 and Task 4.
- **Mutation uncertainty:** conflicts, partial results, unknown results, duplicate idempotency keys, and readback mismatches must preserve a draft and expose reconciliation. Test in Task 3 and Task 4.
- **Responsive interaction parity:** iPad multi-column cards, the three-part title control row, accessible icon-only refresh, touch column resizing, and H5/WeChat state parity must remain aligned. Test in Tasks 5–7.

## File Map

The backend work is implemented in this repository. The frontend paths below are the proposed consumer workspace; if the consuming application lives in another repository, move Tasks 4–6 there without changing the interfaces or fixtures.

- Contract schemas and shared fixtures: `specification/schemas/mobile-table-*.schema.json`, `specification/fixtures/mobile_table/`
- New backend package: `packages/mobile_table/pyproject.toml`, `packages/mobile_table/src/open_table_connector/mobile_table/{__init__,models,wire,validation,host,adapter}.py`
- Backend tests: `packages/mobile_table/tests/{conftest,test_wire,test_validation,test_adapter_capabilities,test_adapter_read,test_adapter_update}.py`
- Optional SDK hook: `packages/sdk/src/open_table_connector/sdk/{connector,table,__init__}.py`, `packages/sdk/tests/test_mobile_records.py`
- Shared TypeScript controller: `clients/mobile-table/core/src/{types,transport,controller,validation}.ts`, `clients/mobile-table/core/test/`
- H5 renderer: `clients/mobile-table/h5/src/{mobile-table-element,styles}.ts`, `clients/mobile-table/h5/test/`
- WeChat renderer: `clients/mobile-table/wechat/components/mobile-table/{mobile-table.wxml,mobile-table.ts,mobile-table.wxss,mobile-table.json}`, `clients/mobile-table/wechat/test/`
- Reference and rollout docs: `packages/mobile_table/README.md`, `docs/reference/mobile-table-http.md`, `docs/operations/security.md`

## Task 1: Freeze the mobile wire contract and fixtures

**Files:**

- Create `specification/schemas/mobile-table-capabilities-v1.schema.json`
- Create `specification/schemas/mobile-table-inspect-v1.schema.json`
- Create `specification/schemas/mobile-table-read-v1.schema.json`
- Create `specification/schemas/mobile-table-update-v1.schema.json`
- Create `specification/schemas/mobile-table-error-v1.schema.json`
- Create `specification/fixtures/mobile_table/{capabilities-supported.json,capabilities-unknown.json,inspect-base.json,inspect-sheet-read-only.json,read-first-page.json,read-continuation.json,read-empty.json,update-success.json,update-conflict.json,update-unknown.json}`
- Create `packages/mobile_table/pyproject.toml`
- Create `packages/mobile_table/README.md`
- Create `packages/mobile_table/src/open_table_connector/mobile_table/{__init__,models,wire,validation}.py`
- Create `packages/mobile_table/tests/{conftest,test_wire,test_validation}.py`
- Modify root `pyproject.toml` to add `packages/mobile_table` to the uv workspace.

**Interfaces:**

- `MobileField(id: str, label: str, type: Literal["string", "integer", "number", "boolean", "date", "datetime", "unknown"], nullable: bool, editable: bool, read_only_reason: str | None)`.
- `MobileRecord(record_id: str, record_revision: str, values: Mapping[str, object])`.
- `MobileError(code: str, message: str, details: Mapping[str, object])`.
- `parse_request(payload: Mapping[str, object], allowed_keys: frozenset[str]) -> MobileRequestEnvelope` rejects unknown keys and validates `contract`, `request_id`, and credential-free `table_uri`.
- Every model has closed `to_wire()` / `from_wire()` methods and preserves JSON scalar distinctions.

- [x] **Step 1: Write failing schema and round-trip tests**

  Add tests for all ten fixture families, closed envelopes, supported/unsupported/unknown capability values, exact update outcome vocabularies, and preservation of `null`, `false`, zero, empty string, and numeric-looking strings.

- [x] **Step 2: Run the contract tests to verify the red phase**

  Run `uv run --frozen python -m pytest packages/mobile_table/tests/test_wire.py packages/mobile_table/tests/test_validation.py -q`.

  Expected: FAIL because the new package and schemas do not exist.

- [x] **Step 3: Implement the frozen models and JSON schemas**

  Keep the schemas closed at the envelope boundary, use `additionalProperties: false` where the spec defines a closed object, and make `details` safe JSON only. Keep the page token opaque and do not normalize it. Declare the package's dependencies on the existing contract and SDK packages without importing any renderer code.

- [x] **Step 4: Run the contract tests to verify the green phase**

  Run the same command. Expected: PASS, with every fixture validating against its corresponding schema and every model round-tripping without changing scalar values.

- [x] **Step 5: Commit**

  ```bash
  git add pyproject.toml packages/mobile_table specification/schemas specification/fixtures/mobile_table
  git commit -m "feat: add mobile table wire contract"
  ```

## Task 2: Add the optional SDK record-update seam

**Files:**

- Create `packages/sdk/src/open_table_connector/sdk/mobile_records.py`
- Modify `packages/sdk/src/open_table_connector/sdk/connector.py`
- Modify `packages/sdk/src/open_table_connector/sdk/table.py`
- Modify `packages/sdk/src/open_table_connector/sdk/__init__.py`
- Create `packages/sdk/tests/test_mobile_records.py`

**Interfaces:**

- `RecordUpdateRequest(record_id: str, patch: Mapping[str, object], expected_table_revision: str, expected_record_revision: str, idempotency_key: str)`.
- `RecordUpdateValue(record_id: str, record_revision: str, table_revision: str, values: Mapping[str, object])`.
- `RecordUpdater` protocol method `update_record(binding: TableBinding, request: RecordUpdateRequest) -> OperationResult[RecordUpdateValue]`.
- `Table.update_record(record_id: str, patch: Mapping[str, object], *, expected_table_revision: str, expected_record_revision: str, idempotency_key: str) -> OperationResult[RecordUpdateValue]` delegates only when the bound connector exposes `RecordUpdater`; otherwise it returns `UNSUPPORTED_CAPABILITY` without connector I/O.

- [x] **Step 1: Write failing SDK tests**

  Cover delegation with both revisions and the idempotency key intact, fail-closed behavior for connectors without `RecordUpdater`, and pass-through of succeeded, conflict, partial, and unknown `OperationResult` states.

- [x] **Step 2: Run the focused SDK tests to verify the red phase**

  Run `uv run --frozen python -m pytest packages/sdk/tests/test_mobile_records.py -q`.

  Expected: FAIL because the protocol and `Table.update_record` method are absent.

- [x] **Step 3: Implement the optional seam**

  Do not add a required method to every existing connector. Detect the optional protocol at runtime, preserve existing `TableConnector` implementations, and reuse existing `OperationResult`, `ErrorCode`, receipt, and revision types.

- [x] **Step 4: Run focused SDK and regression tests**

  Run `uv run --frozen python -m pytest packages/sdk/tests/test_mobile_records.py packages/sdk/tests/test_table.py packages/sdk/tests/test_result.py -q`. Expected: PASS.

- [x] **Step 5: Commit**

  ```bash
  git add packages/sdk/src packages/sdk/tests/test_mobile_records.py
  git commit -m "feat: expose optional record update hook"
  ```

## Task 3: Implement the reference HTTP adapter

**Files:**

- Create `packages/mobile_table/src/open_table_connector/mobile_table/host.py`
- Create `packages/mobile_table/src/open_table_connector/mobile_table/adapter.py`
- Extend `packages/mobile_table/src/open_table_connector/mobile_table/validation.py`
- Create `packages/mobile_table/tests/test_adapter_capabilities.py`
- Create `packages/mobile_table/tests/test_adapter_read.py`
- Create `packages/mobile_table/tests/test_adapter_update.py`
- Create `packages/mobile_table/tests/fakes.py`

**Interfaces:**

- `MobileTableHost` protocol:
  - `capabilities(table_uri: TableURI) -> OperationResult[MobileCapabilities]`
  - `inspect(table_uri: TableURI, fields: tuple[str, ...] | None) -> OperationResult[MobileInspection]`
  - `read(table_uri: TableURI, *, page_size: int, page_token: str | None, fields: tuple[str, ...]) -> OperationResult[MobileReadPage]`
  - `update(request: RecordUpdateRequest) -> OperationResult[MobileUpdateResult]`
- `MobileHttpResponse(status: int, body: Mapping[str, object])`.
- `MobileTableAdapter(host: MobileTableHost).dispatch(method: str, path: str, payload: Mapping[str, object]) -> MobileHttpResponse`.
- Normative paths: `/otc/mobile/v1/capabilities`, `/otc/mobile/v1/inspect`, `/otc/mobile/v1/read`, `/otc/mobile/v1/records/update`.

- [x] **Step 1: Write failing adapter tests**

  Assert exact routing, request ID echo, HTTP 409 for stale revisions, HTTP 4xx for closed-envelope/limit/type failures, HTTP 200 for supported reads, and `unsupported_capability` before `host.update()` when the host has no qualified updater.

- [x] **Step 2: Run adapter tests to verify the red phase**

  Run `uv run --frozen python -m pytest packages/mobile_table/tests/test_adapter_capabilities.py packages/mobile_table/tests/test_adapter_read.py packages/mobile_table/tests/test_adapter_update.py -q`.

  Expected: FAIL because the adapter and host protocol are absent.

- [x] **Step 3: Implement dispatch and validation**

  Validate contract/request/table URI on every operation; clamp only by rejecting page sizes above `min(100, max_page_size)`; enforce 50-field, 10-patch-field, and 16 KiB limits; map SDK result outcome/commit/verification and receipts without inventing success; redact unsafe error details.

- [x] **Step 4: Implement the SDK-backed host bridge**

  Open tables through the existing SDK registry/client, reuse `capabilities()`, `inspect()`, and `read_page()`, and call `Table.update_record()` only when the optional record updater is available. Convert connector errors to the closed mobile error envelope while retaining request/operation IDs.

- [x] **Step 5: Run adapter and package tests**

  Run `uv run --frozen python -m pytest packages/mobile_table/tests packages/sdk/tests/test_mobile_records.py -q`. Expected: PASS, including safe read-only behavior for connectors that lack record updates.

- [x] **Step 6: Commit**

  ```bash
  git add packages/mobile_table packages/sdk/src/open_table_connector/sdk
  git commit -m "feat: expose otc mobile table http adapter"
  ```

## Task 4: Build the shared TypeScript controller

**Files:**

- Create `clients/mobile-table/core/package.json`
- Create `clients/mobile-table/core/src/{types,transport,validation,controller}.ts`
- Create `clients/mobile-table/core/test/{controller-loading,controller-pagination,controller-editing,controller-errors}.test.ts`
- Copy the JSON fixtures from `specification/fixtures/mobile_table/` into the core test fixture loader; do not fork their values.

**Interfaces:**

- `MobileTableTransport.capabilities(request): Promise<CapabilitiesResponse>`.
- `MobileTableTransport.inspect(request): Promise<InspectionResponse>`.
- `MobileTableTransport.read(request): Promise<ReadResponse>`.
- `MobileTableTransport.update(request): Promise<UpdateResponse>`.
- `MobileTableController.state: MobileTableState` with `phase`, `capabilities`, `inspection`, `fields`, `rows`, `nextPageToken`, `sourceRevision`, `drafts`, `mutationStates`, and `lastError`.
- Methods: `load()`, `loadMore()`, `refresh()`, `beginEdit(recordId)`, `setDraftField(recordId, fieldId, value)`, `cancel(recordId)`, `save(recordId)`, and `retry(recordId)`.

- [x] **Step 1: Write failing controller tests**

  Cover capabilities/inspection before first read, page size 25, opaque cursor forwarding, refresh generation invalidation, one-read/one-mutation concurrency, changed-fields-only patches, field validation, draft preservation on conflict, canonical row replacement on success, and idempotency-key reuse only on explicit retry.

- [x] **Step 2: Run the core tests to verify the red phase**

  Run `npm --prefix clients/mobile-table/core test -- --run test`. Expected: FAIL because the controller package is absent.

- [x] **Step 3: Implement the state machine**

  Keep transport concerns out of rendering. Treat `unknown` and `partial` mutation results as unresolved; never infer saved state from an acknowledgment without canonical readback and verification. Ignore unknown response fields and reject unknown request fields.

- [x] **Step 4: Run the core tests to verify the green phase**

  Run `npm --prefix clients/mobile-table/core test -- --run test`. Expected: PASS for all controller state and failure transitions, including one safe-read retry and no automatic mutation retry.

- [x] **Step 5: Commit**

  ```bash
  git add clients/mobile-table/core
  git commit -m "feat: add mobile table controller"
  ```

## Task 5: Implement the H5 renderer and confirmed responsive UI

**Files:**

- Create `clients/mobile-table/h5/package.json`
- Create `clients/mobile-table/h5/src/mobile-table-element.ts`
- Create `clients/mobile-table/h5/src/styles.ts`
- Create `clients/mobile-table/h5/test/mobile-table-element.test.ts`
- Create `clients/mobile-table/h5/test/mobile-table-responsive.test.ts`
- Keep `opendesign/mockups/otc-mobile-table/otc-mobile-table.html` as the visual reference; do not make it the production component.

**Interfaces:**

- `<otc-mobile-table>` accepts a `MobileTableController` and host slots for loading, empty, error, read-only, and conflict states.
- The renderer emits controller actions, never direct provider calls.
- The title control row renders Card/Table on the left, server record count in the center, and sync status plus an icon-only refresh button with an accessible name on the right.
- Card mode is single-column on phone and `repeat(auto-fit, minmax(210px, 1fr))` on iPad-sized content.
- Table mode uses one shared column-width map for header and rows, horizontal scrolling, and bounded pointer/touch resize handles. Rows open the detail sheet; cells remain non-editable.

- [x] **Step 1: Write failing DOM and responsive tests**

  Assert semantic tabs, no field-count text in the control row, accessible refresh labeling, phone single-column cards, iPad multi-column cards, table horizontal overflow, aligned header/row columns after a resize, and row tap opening the same edit sheet.

- [x] **Step 2: Run the H5 tests to verify the red phase**

  Run `npm --prefix clients/mobile-table/h5 test -- --run test`. Expected: FAIL because the Web Component is absent.

- [x] **Step 3: Implement the renderer**

  Use semantic buttons and labels, keyboard focus return after the sheet closes, screen-reader announcements for loading/save/conflict, 44 CSS pixel hit areas, and CSS that keeps the control row usable on narrow phones. Persist column widths only in component session state.

- [x] **Step 4: Run H5 tests and a browser smoke check**

  Run `npm --prefix clients/mobile-table/h5 test -- --run test`, then load the component in a local fixture page and verify H5 phone, H5 iPad, table resize, refresh, load-more, edit, conflict, and unknown-result states. Expected: PASS and no visible “能力说明” or “左右滚动查看更多列” copy.

- [x] **Step 5: Commit**

  ```bash
  git add clients/mobile-table/h5
  git commit -m "feat: add h5 mobile table renderer"
  ```

## Task 6: Implement the WeChat miniapp renderer with parity

**Files:**

- Create `clients/mobile-table/wechat/components/mobile-table/mobile-table.wxml`
- Create `clients/mobile-table/wechat/components/mobile-table/mobile-table.ts`
- Create `clients/mobile-table/wechat/components/mobile-table/mobile-table.wxss`
- Create `clients/mobile-table/wechat/components/mobile-table/mobile-table.json`
- Create `clients/mobile-table/wechat/test/mobile-table.test.ts`

**Interfaces:**

- Consume the same `MobileTableController` actions and state types as H5; do not duplicate pagination, validation, conflict, or retry logic.
- Use `scroll-view` for Table mode, `bindscrolltolower` for `loadMore()`, native input controls for the detail sheet, and touch gesture events for bounded column resizing.
- Preserve the same title control row, icon-only refresh accessible label, card/table semantics, and read-only gating.

- [x] **Step 1: Write failing parity tests**

  Feed the shared fixture sequence through the miniapp adapter and assert the same visible state labels, record order, draft preservation, conflict state, unknown outcome, and refresh behavior as the H5 renderer.

- [x] **Step 2: Run the WeChat tests to verify the red phase**

  Run `npm --prefix clients/mobile-table/wechat test -- --run test`. Expected: FAIL because the WXML component is absent.

- [x] **Step 3: Implement WXML/WXSS bindings**

  Map lifecycle refresh and reach-bottom paging to controller methods; keep provider credentials in the host session exchange; make unsupported capability visibly read-only.

- [x] **Step 4: Run WeChat parity tests and the miniapp preview smoke check**

  Run `npm --prefix clients/mobile-table/wechat test -- --run test`, then open the component in the WeChat developer preview. Expected: PASS with H5 fixture parity and no inline cell editing.

- [x] **Step 5: Commit**

  ```bash
  git add clients/mobile-table/wechat
  git commit -m "feat: add wechat mobile table renderer"
  ```

## Task 7: Add conformance, documentation, rollout gates, and full verification

**Files:**

- Create `packages/mobile_table/tests/test_conformance_fixtures.py`
- Modify `packages/contract/tests/test_schema.py`
- Modify `packages/sdk/tests/test_registry.py` if optional package registration needs coverage
- Create `docs/reference/mobile-table-http.md`
- Modify `packages/mobile_table/README.md`
- Modify `docs/operations/security.md`
- Modify `docs/superpowers/specs/2026-10-22-mobile-table-ui-design.md` only when implementation reveals a contract correction.

- [x] **Step 1: Add fixture parity tests**

  Run every shared fixture through the reference adapter, controller transport mock, H5 renderer, and WeChat renderer. Fail if any renderer changes field order, scalar values, state labels, or outcome semantics.

- [x] **Step 2: Add package-independence and security checks**

  Assert the optional mobile package can be absent without changing existing OTC package imports; assert logs and error envelopes contain no credentials, authenticated URLs, patches, or unrelated cell values.

- [x] **Step 3: Document the endpoint, host integration, read-only gating, and rollout metrics**

  Document the four POST paths, closed envelopes, page/revision rules, record-update qualification requirements, iPad/card/table behavior, and metrics for load latency, edit success, conflicts, unknown outcomes, and auth failures.

- [x] **Step 4: Run focused verification**

  ```bash
  uv run --frozen python -m pytest packages/mobile_table/tests packages/sdk/tests/test_mobile_records.py packages/contract/tests/test_schema.py -q
  npm --prefix clients/mobile-table/core test -- --run test
  npm --prefix clients/mobile-table/h5 test -- --run test
  npm --prefix clients/mobile-table/wechat test -- --run test
  git diff --check
  ```

  Expected: all tests pass and the diff is whitespace-clean.

- [x] **Step 5: Run repository quality gates**

  ```bash
  uv run --frozen ruff check packages/mobile_table packages/sdk/src packages/contract/src
  uv run --frozen mypy packages/mobile_table packages/sdk/src
  uv run --frozen python -m pytest -q
  uv run --frozen python scripts/check_package_metadata.py
  uv run --frozen python scripts/check_package_boundaries.py
  uv run --frozen python scripts/check_package_independence.py --build
  ```

  Expected: existing OTC package tests remain green with the optional mobile package present and absent where the check supports both modes.

- [x] **Step 6: Refresh the repository graph and commit the release gate**

  Run `graft build`, inspect the changed nodes, then commit:

  ```bash
  git add packages/mobile_table packages/sdk packages/contract specification docs/reference docs/operations
  git commit -m "test: qualify mobile table contract and renderer parity"
  ```

## Delivery Order and Handoff

Tasks 1–3 are the backend contract and adapter work in this repository. Task 4 is the shared client dependency. Tasks 5 and 6 can proceed in parallel after Task 4, but both must consume the same fixtures and controller. Task 7 is the release gate.

The first release should ship read-only browsing for every connector that passes capabilities, inspection, and bounded-read checks. Enable editing only for connectors that implement the optional `RecordUpdater` seam and pass stable-ID, expected-revision, idempotency, canonical-readback, and verification fixtures. Unsupported capability remains a visible state until a provider is qualified.
