# Security

OTC separates identity, credentials, physical I/O, and evidence.

## Credential handling

- Do not put credentials in Table URIs, source files, plan documents, or
  artifact paths.
- Prefer environment bindings or a deployment-owned `CredentialResolver`.
- Treat `--token` as a local experiment convenience, not an automation
  default.
- Keep process bootstrap configuration credential-free.

## Filesystem boundaries

Local temporal providers require absolute regular files and reject symlinked
sources. Managed artifacts are content-addressed and path-traversal checked.
Configuration and process bootstrap files are opened with no-follow checks
where the platform supports them, and ownership/mode checks belong to the
deployment boundary.

## Evidence and diagnostics

Receipts and process diagnostics redact common token, password, API-key, and
secret forms. Plan and descriptor hashes exclude credentials and physical URI
secrets. Do not log raw provider responses when they may contain credentials.

## Mobile table sessions

- Exchange provider credentials in the authenticated host session; browser and
  miniapp clients receive only an opaque table URI and request ID.
- Keep request envelopes closed and bound field, patch, page, and response
  sizes before provider I/O.
- Return safe error codes and details. Do not include authenticated URLs,
  patches, cell values, access tokens, or provider exception text in mobile
  responses or logs.
- Treat `unknown`, `partial`, and stale-revision outcomes as unresolved. Keep
  the user's draft for an explicit retry after canonical readback.

## Trust boundaries

Provider code is selected through installed descriptors and explicit registry
configuration. Formula text is provider-native and opaque. A capability is not
advertised merely because a provider could approximate it locally.
