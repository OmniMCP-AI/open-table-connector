# CSV File URL Scope Correction

## Goal

Retain CSV as a supported format and codec while removing the retired
`csv` and `managed+csv` URI schemes. Every local CSV source and managed
CSV temporal target uses a canonical `file://` URL.

## Decisions

- `PROVIDER_CSV`, `AdapterFormat.CSV`, CSV parsing, CSV CLI format selection,
  CSV receipts, and `.csv` managed snapshot encoding remain supported.
- The `csv` scheme is not a supported connector URI. The CSV connector accepts only
  canonical `file://` URIs, and the local-file adapter continues to infer CSV
  from a file URL or path.
- The `managed+csv` scheme is removed completely. Managed CSV logical and physical
  targets are canonical `file://` URIs; the managed snapshot store continues
  to use the `.csv` extension and CSV codec.
- MaybeSheet remains HTTPS-only. No MaybeSheet-specific URI route is reintroduced.
- Process registration, capability allowlists, SDK URI helpers, conformance
  fixtures, documentation, and literal-checker rules must describe the same
  URL surface.

## Compatibility and errors

Existing callers that pass either retired CSV scheme must receive the
repository's normal unsupported-scheme/invalid-target error before file I/O.
Callers that pass `file://.../*.csv` retain the current CSV read and temporal
lifecycle behavior.

## Verification

Targeted tests cover direct CSV resolution, temporal CSV execution, SDK target
construction, process bootstrap, and rejection of the retired schemes. The
full pytest suite, package-quality checks, URL-literal checker, and graft
rebuild must pass before the change is committed and pushed.
