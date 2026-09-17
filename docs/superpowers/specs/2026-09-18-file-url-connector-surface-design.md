# File URL connector surface design

## Objective

Make ordinary local files the canonical OTC address while retaining MaybeSheet
through its canonical HTTPS document URL.

The public URL policy after this change is:

- Local CSV, Excel, JSON, JSONL, Markdown, and workbook operations use
  `file://` URLs.
- MaybeSheet uses `https://www.maybe.ai/docs/spreadsheets/d/<document>` URLs.
- CSV-, Excel-, XLSX-, and MaybeSheet-specific schemes are not public connector
  routes.

CSV and Excel remain supported file formats. This change removes their
provider-specific connector identities and URL aliases; it does not remove
CSV/Excel codecs, CLI format selection, local workbook operations, or managed
snapshot implementations. Managed CSV snapshots use canonical file URLs while
retaining CSV encoding.

## Architecture

### Local files

`LocalFilesConnector` remains the sole local provider and continues to infer a
file's format from its extension. Its CSV and Excel branches will call the
existing readers directly (or through private helpers) instead of constructing
public `CsvConnector` or `ExcelConnector` instances. Receipts retain the
original `file://` URI supplied by the caller.

The public local CLI descriptor remains registered for `file`, `json`, and
`jsonl`. Dedicated CSV and Excel CLI descriptors, exports, and entry points are
removed. CSV/Excel continue to be valid format names for explicit conversion
and output selection where the local adapter already supports them.

Excel formula operations remain local-file operations. `ExcelFormulaExtension`
will resolve and validate `file://` targets directly, without depending on an
`ExcelConnector` object. Existing workbook, formula, and safety behavior stays
unchanged apart from URI validation and connector identity metadata.

### MaybeSheet

MaybeSheet remains a provider and package, but its only advertised URI scheme
is HTTPS and its only accepted host is `www.maybe.ai`. Canonical document URLs
are validated consistently at the CLI and Spreadsheet boundaries.

The connector passes the canonical document URL to `mbs` unchanged after
removing OTC-only query/fragment metadata. Named targets are supplied through
the existing explicit target option. A `table_id` query remains supported for
stable base-table binding, but is treated as request metadata rather than part
of the process target.

Newly created MaybeSheet workbooks return canonical HTTPS document URLs.
Parsing, conversion, validation, error messages, and generated bindings for
the retired MaybeSheet-specific scheme are removed.

### Contract and process surfaces

Remove `SCHEME_MAYBE` and the direct local `csv`/`excel` URI registrations from
public manifests and adapter discovery. Keep provider names that are still
needed as format or managed-temporal identifiers, but no provider descriptor
may advertise the retired direct URL schemes.

Temporal process configuration for local CSV/Excel sources will accept the
canonical file target where source access is required. Managed CSV snapshots
also use canonical file targets while retaining their CSV codec and extension.
MaybeSheet temporal bindings continue to use the canonical HTTPS target.

## Tests and documentation

Add or update regression coverage for:

1. CSV and Excel reads through `LocalFilesConnector` with `file://` URIs.
2. Rejection/non-discovery of the retired CSV, Excel, XLSX, and
   MaybeSheet-specific routes.
3. MaybeSheet CLI, connector, spreadsheet, formula, and temporal behavior with
   canonical HTTPS URLs, including stable `table_id` binding.
4. No leaked retired schemes in plugin descriptors, manifests, generated
   bindings, conformance fixtures, or package metadata.

Update package READMEs, reference/conformance docs, and `AGENTS.md` to state
the URL policy so future changes do not reintroduce the aliases.

## Compatibility boundary

This is an intentional breaking change for callers that instantiate the
dedicated CSV/Excel connector classes or pass scheme-specific CSV/Excel/XLSX or
MaybeSheet endpoints. Callers should use `file:///absolute/path/...` for local
files and the canonical MaybeSheet HTTPS document URL for MaybeSheet.
