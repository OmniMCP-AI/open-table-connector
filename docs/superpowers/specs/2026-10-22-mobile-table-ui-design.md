# OTC Mobile Table UI and HTTP Contract

> Design specification for a mobile-first table viewer and simple record editor that can run in web H5 and WeChat miniapps.

## 1. Objective

Provide a small, reusable mobile table surface for applications that need to browse an Open Table Connector (OTC) table and edit simple records from a phone. The same behavior must work in a browser H5 surface and in a native WeChat miniapp surface.

The first release is a read-first experience. It loads bounded pages, renders the fields that the table exposes, and opens one record at a time for typed edits when the server explicitly proves that the record and fields are editable. OTC remains the source of truth for schema, revisions, capabilities, mutation results, receipts, and verification state.

This specification defines both sides of the integration:

1. A versioned HTTP contract that adapts OTC table operations to mobile clients.
2. A platform-neutral controller and two renderers: an H5 renderer and a WeChat miniapp renderer.

The repository already supplies the concepts that this contract carries forward: canonical `TableURI`, `TableMode`, `TableInspection`, coordinate conventions, capability identities, bounded reads, `OperationResult`, receipts, idempotency keys, and explicit outcome/commit/verification states.

## 2. Scope and decisions

### In scope

- Capability discovery for one table.
- Schema and coordinate inspection.
- Bounded, cursor-based reads.
- Responsive mobile and iPad card/table browsing with a compact record detail view and session-only table column resizing.
- One-record typed patches with optimistic concurrency.
- Explicit conflict, unsupported, partial, and unknown states.
- A shared controller API consumed by H5 and WeChat renderers.
- Contract fixtures and renderer parity tests.
- A reference OTC adapter in an optional package in this repository.

### Out of scope for v1

- Formulas, formula editing, or formula recalculation controls.
- Cell or range formatting, charts, images, attachments, or rich objects.
- Arbitrary provider queries, custom SQL, or client-defined server-side code.
- Bulk edits, multi-row selection, drag fill, column reorder/hide/show, or column insert/delete.
- Autosave, offline queues, background synchronization, or silent retries.
- Automatic conflict resolution or a force-overwrite action.
- A browser DOM runtime inside WeChat WXML.
- A new writer implementation in a connector that has no qualified record-update capability.

### Decisions

| Area | Decision |
| --- | --- |
| Architecture | Shared mobile protocol, headless interaction core, separate H5 and WeChat renderers. |
| Contract version | `otc.mobile.table/1.0`. |
| Read pagination | Opaque cursor tokens tied to a source revision. |
| Edit unit | One record patch per mutation request. |
| Edit identity | A stable provider record ID is required. Sheet rows without one are read-only. |
| Concurrency | Expected table and record revisions are sent with every edit. |
| Conflict behavior | Preserve the draft, show the current server row, and require an explicit reload/discard decision. |
| Authentication | Host-managed headers or short-lived session tokens; credentials never belong in a table URI. |
| Responsive layout | Phones use a single-column card list; iPad uses an auto-fitting multi-column card grid and a wider table viewport. |
| Browsing controls | Immediately below the table title, place the Card / Table selector on the left, record count in the center, and sync status plus an icon-only refresh action on the right. |
| Table column widths | Allow bounded drag resizing from visible header boundaries. Apply widths to the header and every row for the current session; do not persist them in v1. |
| Renderer parity | The same controller fixtures and state transitions must pass through both renderers. |
| Repository boundary | OTC protocol and reference adapter live here; TypeScript controller and renderers live in the frontend package that consumes this contract. |

## 3. Architecture

```text
H5 renderer       WeChat renderer
      \             /
       shared mobile-table controller
                    |
             MobileTransport
                    |
        OTC mobile HTTP adapter
                    |
        OTC SDK / connector registry
                    |
       provider capability and receipts
```

### 3.1 Responsibilities

| Unit | Responsibility |
| --- | --- |
| Mobile HTTP adapter | Validate the mobile envelope, resolve the canonical table URI, call the OTC SDK, and map the SDK result to the mobile wire contract. |
| `MobileTransport` | Send capabilities, inspect, read, and update requests. It owns authentication headers and host-specific networking. |
| Headless controller | Own the table state machine, cursors, drafts, request sequencing, typed validation, and OTC result mapping. It has no DOM or WXML dependency. |
| H5 renderer | Render semantic HTML, the title control row, responsive cards or a horizontal resizable grid, keyboard behavior, focus management, and host-provided slots. |
| WeChat renderer | Render native WXML controls, the same title control row, miniapp scrolling/reach-bottom behavior, bounded column resizing, page lifecycle handling, and host-provided slots. |
| OTC connectors | Preserve existing capability, revision, idempotency, receipt, and verification guarantees. A mobile adapter cannot manufacture support. |

The H5 renderer may be exposed as a Web Component and a framework wrapper. The WeChat renderer is a native miniapp component. Both consume the same controller snapshot and action names.

### 3.2 Request and response envelope

All requests use JSON and carry:

```json
{
  "contract": "otc.mobile.table/1.0",
  "request_id": "req_01J...",
  "table_uri": "https://example.invalid/table/123"
}
```

`table_uri` is the canonical OTC `TableURI` value. It may be a canonical `file://` URI for a local host or an HTTPS document URI for a remote provider, following the repository URL policy. It must not contain credentials or secret query parameters.

Responses carry the same `contract` and `request_id`. Every response that reaches a connector also carries an `operation_id` when the underlying OTC result provides one.

Errors use one closed envelope:

```json
{
  "contract": "otc.mobile.table/1.0",
  "request_id": "req_01J...",
  "error": {
    "code": "stale_revision",
    "message": "The record changed before it could be saved.",
    "details": {
      "table_revision": "sha256:...",
      "record_revision": "sha256:..."
    }
  }
}
```

`message` and `details` are safe for a client. They must not contain credentials, raw provider exception text, full authenticated URLs, or cell values unrelated to the requested record.

## 4. HTTP contract

The reference adapter exposes the following POST operations below a host-selected base URL. The exact deployment prefix is configurable; the operation paths and payloads are normative.

### 4.1 Capability discovery

`POST /otc/mobile/v1/capabilities`

Request:

```json
{
  "contract": "otc.mobile.table/1.0",
  "request_id": "req_01J...",
  "table_uri": "https://example.invalid/table/123"
}
```

Response:

```json
{
  "contract": "otc.mobile.table/1.0",
  "request_id": "req_01J...",
  "table_uri": "https://example.invalid/table/123",
  "capability": "otc.mobile.table/1.0",
  "read": {
    "support": "supported",
    "max_page_size": 100,
    "stable_record_ids": true
  },
  "record_update": {
    "support": "supported",
    "requires_expected_revision": true,
    "max_fields_per_patch": 10,
    "field_types": ["string", "integer", "number", "boolean", "date", "datetime"]
  },
  "limits": {
    "max_fields": 50,
    "max_patch_bytes": 16384
  },
  "source": {
    "connector_id": "maybe-sheet",
    "connector_version": "0.1.0"
  }
}
```

`support` is one of `supported`, `unsupported`, or `unknown`. The client treats `unknown` as read-only and displays the reason supplied by inspection or the error envelope. A capability response is not proof of field-level editability; the inspection response must also mark each field.

### 4.2 Inspection

`POST /otc/mobile/v1/inspect`

Request adds an optional field selection:

```json
{
  "contract": "otc.mobile.table/1.0",
  "request_id": "req_01J...",
  "table_uri": "https://example.invalid/table/123",
  "fields": ["status", "owner", "updated_at"]
}
```

Response:

```json
{
  "contract": "otc.mobile.table/1.0",
  "request_id": "req_01J...",
  "table_uri": "https://example.invalid/table/123",
  "mode": "base",
  "schema_fingerprint": "sha256:...",
  "row_count": 412,
  "source_revision": "sha256:...",
  "coordinate_convention": {
    "mode": "base",
    "record_id_field": "id",
    "key_fields": [],
    "ordinal_snapshot_id": "sha256:..."
  },
  "fields": [
    {
      "id": "status",
      "label": "Status",
      "type": "string",
      "nullable": false,
      "editable": true,
      "read_only_reason": null
    },
    {
      "id": "margin",
      "label": "Margin",
      "type": "number",
      "nullable": true,
      "editable": false,
      "read_only_reason": "computed_field"
    }
  ]
}
```

The field `type` is one of `string`, `integer`, `number`, `boolean`, `date`, `datetime`, or `unknown`. Dates and datetimes use the provider’s canonical JSON representation documented by the adapter. Unknown values are rendered as read-only text only when the adapter supplies a safe display value; the controller never guesses a type.

The response carries the existing OTC coordinate convention. A base table is editable only when `record_id_field`, key fields, or another stable provider identity is present and the capability response says `stable_record_ids: true`. A sheet table may be read, but it is read-only unless the adapter provides stable row IDs and a qualified record-update capability.

### 4.3 Paged read

`POST /otc/mobile/v1/read`

Request:

```json
{
  "contract": "otc.mobile.table/1.0",
  "request_id": "req_01J...",
  "table_uri": "https://example.invalid/table/123",
  "page_size": 25,
  "page_token": null,
  "fields": ["id", "status", "owner", "updated_at"]
}
```

`page_size` defaults to 25 and may not exceed the lower of 100 and the capability response’s `max_page_size`. `page_token` is opaque. The client must not parse, alter, or persist it beyond the current table session.

Response:

```json
{
  "contract": "otc.mobile.table/1.0",
  "request_id": "req_01J...",
  "table_uri": "https://example.invalid/table/123",
  "mode": "base",
  "source_revision": "sha256:...",
  "fields": [
    {"id": "status", "label": "Status", "type": "string", "nullable": false, "editable": true},
    {"id": "owner", "label": "Owner", "type": "string", "nullable": true, "editable": true}
  ],
  "rows": [
    {
      "record_id": "rec_123",
      "record_revision": "sha256:...",
      "values": {"status": "Open", "owner": "Ava"}
    }
  ],
  "next_page_token": "cursor_opaque_value"
}
```

The server must keep all rows in a page at the same `source_revision`. If a continuation cannot be honored against that revision, return `stale_cursor`; the controller resets to the first page after the user confirms or invokes refresh.

The adapter returns only requested and permitted fields. It must preserve null, false, zero, empty string, and numeric-looking strings as distinct values. It must not leak raw formula text into a safe mobile value surface.

### 4.4 Record update

`POST /otc/mobile/v1/records/update`

Request:

```json
{
  "contract": "otc.mobile.table/1.0",
  "request_id": "req_01J...",
  "table_uri": "https://example.invalid/table/123",
  "record_id": "rec_123",
  "patch": {
    "status": "Done",
    "owner": null
  },
  "expected_table_revision": "sha256:...",
  "expected_record_revision": "sha256:...",
  "idempotency_key": "mobile-edit-01J..."
}
```

The patch is closed to the inspected field IDs, contains at most 10 fields, and is at most 16 KiB when serialized as UTF-8 JSON. The adapter validates field types and field editability before dispatch. A client cannot add a formula, computed value, or provider-owned field by bypassing the renderer.

Successful response:

```json
{
  "contract": "otc.mobile.table/1.0",
  "request_id": "req_01J...",
  "operation_id": "op_01J...",
  "outcome": "succeeded",
  "commit": "committed",
  "verification": "passed",
  "table_revision": "sha256:new-table-revision",
  "record": {
    "record_id": "rec_123",
    "record_revision": "sha256:new-record-revision",
    "values": {"status": "Done", "owner": null}
  },
  "receipts": [
    {"kind": "table.record.update", "operation_id": "op_01J..."}
  ]
}
```

The response uses the OTC SDK wire values for `outcome`, `commit`, and `verification`: `succeeded`, `rejected`, `failed`, `partial`, `unknown`, or `planned`; `not_applicable`, `not_started`, `not_committed`, `committed`, `partial`, or `unknown`; and `passed`, `failed`, `skipped`, `unavailable`, or `not_applicable`, respectively. The adapter must preserve the legal combinations defined by `OperationResult`.

For a stale expected revision, return HTTP 409 and this error shape:

```json
{
  "contract": "otc.mobile.table/1.0",
  "request_id": "req_01J...",
  "error": {
    "code": "stale_revision",
    "message": "The record changed before it could be saved.",
    "details": {
      "current_table_revision": "sha256:current-table",
      "current_record": {
        "record_id": "rec_123",
        "record_revision": "sha256:current-record",
        "values": {"status": "In progress", "owner": "Ava"}
      }
    }
  }
}
```

The adapter must not implement update by downloading, modifying, and replacing a whole table unless that connector already provides the required record-level guarantees. If a connector has no qualified record-update capability, return `unsupported_capability` before dispatch.

## 5. Headless controller contract

The frontend package provides a controller with the following conceptual API. The exact TypeScript types belong to the frontend implementation, but names and behavior are normative:

```ts
type MobileTableController = {
  state: MobileTableState;
  load(): Promise<void>;
  loadMore(): Promise<void>;
  refresh(): Promise<void>;
  beginEdit(recordId: string): void;
  setDraft(recordId: string, fieldId: string, value: unknown): void;
  save(recordId: string): Promise<void>;
  cancel(recordId: string): void;
  retry(): Promise<void>;
};
```

`MobileTableTransport` has four methods corresponding to the four HTTP operations. It receives an already configured request function or host client; it does not own token storage.

The state snapshot contains:

- `phase`: `idle`, `loading`, `ready`, `refreshing`, `loading_more`, `error`, or `read_only`.
- `capabilities` and `inspection`, when available.
- `fields`, `rows`, `nextPageToken`, and the current source revision.
- `drafts` keyed by record ID, including field validation errors.
- `mutationStates` keyed by record ID: `idle`, `saving`, `conflict`, `unknown`, or `error`.
- `lastError`, with the safe contract error and request ID.

The controller enforces these rules:

1. `load()` obtains capabilities and inspection before the first read.
2. It never starts more than one read or mutation for a table at a time.
3. A new `refresh()` invalidates cursors and ignores stale responses from older request generations.
4. `save()` submits only changed fields and includes both expected revisions.
5. On success, it replaces the local row with the canonical returned row and updates the source revision.
6. On conflict, it keeps the draft and stores the current server row for the renderer.
7. On `unknown` or `partial`, it keeps the row marked unresolved and exposes an explicit retry/reconcile action. It never marks the row saved from an acknowledgment alone.
8. `retry()` for a mutation reuses the same idempotency key; it is user initiated.

## 6. Mobile UX

### 6.1 Browsing

The default narrow-screen layout is a list of compact record cards. Each card shows the stable identity field and the first useful fields in schema order. A record detail sheet exposes every permitted field. Directly below the title, one compact row places the `Card / Table` selector on the left, the server-reported record count in the center, and sync status plus an icon-only refresh action on the right. The refresh icon has an accessible name and a touch target that meets the 44 CSS pixel minimum; the sync status may retain a short text label beside its status dot. Do not put the field count in this row. The Table view is for people familiar with Excel who need to scan more rows and columns quickly: it uses compact column headers, horizontal scrolling, and the same field order and values. Each visible column boundary provides a touch-friendly drag handle with bounded minimum and maximum widths; the chosen widths apply to the header and all rows for the current session. Table view is a reading mode, and tapping a row still opens the same record detail sheet for editing.

Table view is available in both H5 and WeChat. H5 may use a horizontal grid directly in a wide or landscape container. WeChat uses a native horizontal scroll surface. On iPad, the renderer uses a wider canvas, an auto-fitting multi-column card grid with a practical minimum card width of about 210 CSS pixels, and a larger table viewport while preserving the same row tap and column resize behavior. The grid should use as many columns as the available width allows and fall back to fewer columns only when the minimum card width cannot be met. Neither renderer makes cells inline-editable in v1.

The header shows the table title, read-only/editable status, and sync state. The renderer provides loading, empty, and error slots so the host can apply product branding without changing controller behavior.

The default page size is 25. H5 loads more through an intersection sentinel; WeChat uses the native reach-bottom event. Renderers must not render an unbounded full table. A list virtualization strategy is required once more than 100 rows are retained in the visible session.

### 6.2 Editing

The list remains read-only. A row action opens a record detail sheet. Typed controls are:

| Field type | Default control | Rules |
| --- | --- | --- |
| `string` | Text input | Preserve empty string and null as distinct values. |
| `integer` | Numeric input | Reject non-integral values before dispatch. |
| `number` | Numeric input | Reject non-finite values before dispatch. |
| `boolean` | Switch or checkbox | Preserve false; do not treat omission as false. |
| `date` / `datetime` | Host date picker | Serialize using the inspected contract representation. |
| `unknown` | Read-only value | Never infer an editor from the display text. |

Computed, formula, provider-owned, and otherwise non-editable fields show their `read_only_reason` when the host requests it. Save and cancel are explicit. There is no autosave, optimistic local success, or force overwrite.

### 6.3 State and failure presentation

The renderers map controller state to these visible states:

| State | Required behavior |
| --- | --- |
| Loading | Show skeleton rows and preserve the host title. |
| Empty | Show a clear empty message and a refresh action. |
| Read-only | Keep browsing enabled and explain the capability reason near the edit affordance. |
| Validation error | Keep the sheet open and place the error beside the field. |
| Saving | Disable duplicate save for that record and show progress. |
| Conflict | Keep the draft, show the current server row, and offer reload/discard. |
| Unknown or partial | Show unresolved status, request ID, and an explicit reconciliation action. |
| Network/auth error | Preserve loaded rows when safe and offer retry or host re-authentication. |

H5 uses semantic labels, keyboard focus management, focus return after closing a sheet, screen-reader announcements for loading/save/conflict, and touch targets of at least 44 CSS pixels. WeChat maps the same labels and focus order to native WXML controls.

## 7. Security, limits, and privacy

- Authorization is enforced by the mobile API and underlying connector for every operation. UI configuration is not a permission boundary.
- H5 deployments using cookies require exact-origin CORS and CSRF protection. Bearer tokens use the host’s existing secure storage and transport.
- WeChat clients use a host session exchange. Provider credentials and long-lived secrets must never be bundled in the miniapp.
- The API returns only requested and permitted fields. Logs contain request ID, operation ID, table mode, capability, latency, outcome, commit, verification, and conflict counts; they never contain values, patches, tokens, or authenticated URLs.
- Default page size is 25; maximum page size is 100 or the provider-advertised lower bound.
- A request may select at most 50 fields. A record patch may contain at most 10 fields and 16 KiB of UTF-8 JSON.
- A controller has at most one read and one mutation in flight. A renderer must cancel or ignore stale read generations.
- Safe reads may retry once after a transport failure. Mutations never retry automatically. An explicit mutation retry reuses the original idempotency key.
- The API adapter applies its normal resource and timeout limits before connector dispatch. It must return `resource_limit` or `timeout` without partial client-side fabrication.

## 8. Versioning and compatibility

The contract identity is `otc.mobile.table/1.0`. Additive response fields are compatible within 1.0. Changing field identity, record identity, revision semantics, patch semantics, or the meaning of outcome/commit/verification requires a new major version.

The controller must ignore unknown response fields and reject unknown request fields. The adapter must validate closed envelopes before connector dispatch. The HTTP status is transport information; clients use the contract error code and OTC result states for product behavior.

The mobile adapter is optional. Existing OTC CLI, SDK, connectors, and URI behavior remain compatible when the optional package is absent. A provider that does not implement qualified record updates continues to work as a read-only target.

## 9. Testing and acceptance

### 9.1 Contract fixtures

Create shared JSON fixtures for:

1. Supported read and supported record update.
2. Unsupported and unknown capability states.
3. Base-mode inspection with a stable record ID.
4. Sheet-mode inspection without a stable record ID.
5. A first page, a continuation page, an empty page, and a stale cursor.
6. Null, false, zero, empty string, integer, number, date, and datetime values.
7. Successful update with canonical readback and receipts.
8. Schema/type/field editability rejection before dispatch.
9. Stale revision conflict with a current server row.
10. Failed, partial, unknown, and idempotent replay outcomes.

The same fixtures drive the reference adapter, controller, H5 renderer, and WeChat renderer. A parity failure is a release blocker.

### 9.2 Controller tests

Test that the controller:

- loads capabilities and inspection before the first read;
- honors the server page-size limit and treats cursors as opaque;
- preserves drafts across refresh warnings and conflicts;
- sends only changed, editable fields with both expected revisions;
- replaces a row only from a succeeded, verified response;
- preserves unresolved state for partial and unknown results;
- reuses an idempotency key only for an explicit mutation retry;
- ignores stale responses from older request generations.

### 9.3 Renderer tests

The H5 suite covers semantic labels, keyboard navigation, focus return, screen-reader state announcements, touch target size, the title control row (including the icon-only refresh label and record-count placement), responsive single-column phone cards, iPad multi-column cards, resizable grid columns with header/row alignment, and the intersection-based page trigger. The WeChat suite covers native input controls, the same control-row semantics, touch resizing on the horizontal table surface, reach-bottom paging, page lifecycle refresh, session expiry, and the same visible state mappings.

### 9.4 Release gates

The feature is ready for a release candidate when:

- every contract fixture passes through both renderers;
- no target becomes editable without stable identity and live capability evidence;
- successful updates replace the row with server-canonical values;
- conflicts preserve drafts and display current server state;
- partial and unknown outcomes retain reconciliation evidence;
- no test or log fixture contains credentials, secret query parameters, or unredacted cell data;
- existing OTC package tests and package-independence checks remain green with the mobile package absent and present.

## 10. Delivery sequence

1. Add the versioned schemas, error map, and reference adapter with read-only capabilities.
2. Add the controller and contract fixture suite.
3. Ship the H5 renderer and verify read-only parity.
4. Qualify base-mode record updates for connectors that already provide stable IDs, revisions, idempotency, and readback.
5. Add the WeChat renderer using the same controller fixtures.
6. Add sheet-mode read-only support where the provider can return a stable revision and bounded pages.
7. Enable edit controls only per live capability evidence and publish metrics for load latency, edit success, conflict rate, unknown outcomes, and auth failures.

No step adds new provider semantics, silently replaces a table, or falls back to a second writer. Unsupported capability remains a visible product state until the provider is qualified.

