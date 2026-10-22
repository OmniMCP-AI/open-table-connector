# Mobile table HTTP contract

The `otc.mobile.table/1.0` adapter is the small HTTP surface shared by the H5
Web Component and the WeChat miniapp. Every operation is a `POST` with a JSON
body. The response always echoes `contract` and `request_id`; successful
responses use the operation-specific envelope and failures use `{ error: {
code, message, details } }`.

## Endpoints

| Endpoint | Purpose |
| --- | --- |
| `/otc/mobile/v1/capabilities` | Advertise bounded reads and whether qualified record updates are available. |
| `/otc/mobile/v1/inspect` | Return field order, types, nullability, editability, row count, and source revision. |
| `/otc/mobile/v1/read` | Read a page of records using an opaque continuation token. |
| `/otc/mobile/v1/records/update` | Apply a small field patch with expected revisions and an idempotency key. |

The request envelope is closed. It contains `contract`, `request_id`, and
`table_uri`, plus only the endpoint fields. Unknown keys are rejected. Table
URIs are resolved by the authenticated host session; credentials and bearer
tokens must never be embedded in the URI.

## Paging and limits

The client starts with `page_size: 25`. The adapter rejects a request above the
lower of 100 and the provider's advertised `read.max_page_size`. It forwards
`page_token` byte-for-byte as an opaque value. Field selection is limited to
50 unique IDs. A patch is limited to 10 fields and 16 KiB of JSON-compatible
values.

## Read-only gating

Every client loads capabilities and inspection before the first read. A table
is read-only when read support is unavailable, stable record IDs are not
advertised, expected revisions are unavailable, or the host does not implement
the optional SDK `RecordUpdater` seam. The UI keeps the read-only state visible
and never attempts an update in that state.

## Update qualification and outcomes

Hosts qualify editing only when they can preserve stable record IDs, expected
table and record revisions, idempotency keys, canonical readback, and provider
verification. The adapter maps the SDK outcome, commit, verification, receipt,
and canonical record without inferring success. `conflict`, `partial`, and
`unknown` remain unresolved in the client and keep the draft for explicit user
retry or cancellation.

## Host integration

`MobileTableAdapter` depends on the `MobileTableHost` protocol. The reference
`SdkMobileTableHost` opens a table through the SDK resolver and delegates
capabilities, inspection, reads, and the optional `Table.update_record()` call.
Provider credentials stay in the host session exchange and are never exposed
to browser or miniapp code.

## Client behavior

The shared TypeScript controller owns loading, paging, validation, conflict,
unknown-result, and retry state. H5 and WeChat render the same controller state:
card mode is one column on phones and multiple columns on iPad-sized content;
table mode uses a shared resizable column map. Editing happens in a detail
sheet with native inputs. Inline cell editing is not supported.

## Rollout metrics

Record these dimensions by connector and client surface:

- capabilities, inspect, and first-page latency;
- read retry rate and load-more failures;
- edit success rate with committed and verified outcomes;
- stale-revision conflicts and explicit retries;
- partial or unknown outcomes;
- authentication failures and unsupported-capability responses.

Release editing only for providers that pass the stable-ID, revision,
idempotency, canonical-readback, and verification fixtures. Keep the first
release read-only for all other connectors.
