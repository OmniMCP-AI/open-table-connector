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

## Trust boundaries

Provider code is selected through installed descriptors and explicit registry
configuration. Formula text is provider-native and opaque. A capability is not
advertised merely because a provider could approximate it locally.
