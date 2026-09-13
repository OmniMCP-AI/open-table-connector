# Excel Artifact Capability Requirements

**Date:** 2026-09-13
**Status:** Proposed requirement for `open-table-connector-local-files`
**Capability:** `excel-artifact/v1`
**Consumer:** FinClaw analysis Excel adapter

## 1. Purpose

Add a reusable OTC capability that owns the mechanical construction and
physical verification of local `.xlsx` artifacts. The capability replaces the
generic workbook responsibilities currently implemented in FinClaw's
`src/finc/analysis/excel.py`, while leaving FinClaw in charge of financial
semantics and report composition.

The capability is deliberately separate from OTC's existing Arrow table
writer and Excel source connector. Existing callers of `write_excel(table,
path, sheet)` and existing Excel reads must continue to work without a
behavior change.

## 2. Normative boundary

OTC **MUST** provide provider-neutral workbook mechanics. OTC **MUST NOT**
import FinClaw, interpret metric IDs, calculate financial values, select
evidence, or decide report layout. FinClaw **MUST** provide a translation from
its authenticated report sections to the OTC plan and a semantic verification
step after OTC physical verification.

The capability is local-only and produces a new workbook. It is not an Excel
calculation engine, an editable model builder, or a remote spreadsheet API.

## 3. Public contract

The implementation may choose concrete class names, but the following API
shape and behavior are required:

```python
write_workbook(
    plan: WorkbookPlan,
    destination: Path,
) -> WorkbookWriteReceipt

verify_workbook(
    path: Path,
    expected: WorkbookExpectation,
) -> WorkbookVerifyReceipt
```

The capability must be discoverable through the local-files manifest and use
stable versioned identifiers for both operations. Receipts must be JSON
serializable and credential-free.

## 4. `WorkbookPlan` requirements

### R1 — Ordered sheets

The plan **MUST** contain at least one sheet and preserve caller order. Each
sheet name **MUST** be non-empty after trimming, no longer than 31 characters,
and unique case-insensitively. If a caller requests sanitization and collision
suffixes, the algorithm **MUST** be deterministic and the resulting names
**MUST** be returned in the receipt.

### R2 — Literal cells

Each semantic cell **MUST** contain an uppercase A1 coordinate and a string
value. Coordinates **MUST** be unique per sheet. Values **MUST** be stored as
literal string cells with text number format (`@`), including strings that
begin with `=`, `+`, `-`, or `@`. Values longer than 32,767 characters **MUST**
be rejected. Style-only empty cells may exist but are not part of semantic
coverage.

### R3 — Layout properties

The plan **MAY** declare column widths, row heights, freeze panes, gridline
visibility, print area, page orientation, paper size, fit-to-page settings,
margins, merges, fonts, fills, alignment, and number format. The supported
subset **MUST** be explicit and versioned. Unsupported or malformed property
values **MUST** fail validation instead of being silently dropped.

### R4 — Merges

Merge ranges **MUST** be valid A1 rectangles within the sheet, non-overlapping
unless the workbook library explicitly supports the combination, and listed
in deterministic order. The verifier **MUST** compare the physical merge map
with the expectation.

### R5 — Images

An image placement **MUST** identify a sheet, a zero-offset one-cell anchor,
bounded image bytes, and a SHA-256 content hash. The writer **MUST** embed the
bytes and the verifier **MUST** report the physical image hash and reject
missing, extra, relocated, or modified images. File paths, if accepted as an
input convenience, **MUST** be read before writing and **MUST NOT** be stored
as external workbook links.

### R6 — Resource limits

The plan and writer **MUST** enforce configurable limits for sheet count,
semantic-cell count, text bytes, image bytes, and output/archive bytes. A
limit failure **MUST** identify the limit and observed value without exposing
credentials or arbitrary workbook contents.

## 5. Writer requirements

### R7 — Exclusive staged creation

`write_workbook` **MUST** create a new destination and fail when the path
already exists. Callers can therefore stage, verify, and publish explicitly.
The writer **MUST NOT** overwrite a source workbook or mutate an existing
workbook in place.

### R8 — No calculation

The generated workbook **MUST** contain no formula cells and **MUST** disable
calculation-on-open behavior. OTC **MUST NOT** invoke Excel or another
calculation engine. Formula-looking input text remains literal text.

### R9 — Deterministic manifest

The write receipt **MUST** include capability identity, schema version, sheet
order, semantic cell manifest, merge manifest, image manifest, resource
limits, and a stable semantic hash. The raw file content hash is recorded
after the bytes are saved. The requirement is semantic determinism; byte
identity across different library or runtime versions is not required.

### R10 — Failure cleanup

If writing fails, OTC **MUST** close workbook resources and remove only the
new staged path it created. It **MUST NOT** delete or alter a pre-existing
path.

## 6. Physical verification requirements

### R11 — Decoded readback

`verify_workbook` **MUST** reopen the workbook and compare sheet names/order,
semantic cell coordinate/type/value coverage, merge ranges, supported layout
properties, and image sheet/anchor/hash coverage with the expectation. Any
extra semantic cell is a failure.

### R12 — Raw XML checks

The verifier **MUST** inspect the XLSX archive and reject duplicate ZIP
members, invalid worksheet relationships, external worksheet relationships,
formula elements, nonliteral semantic cell types, invalid/duplicate cell
coordinates, and semantic cells that are absent from the decoded readback.

Style-only cells created by merge borders or workbook formatting may be
present when they carry no semantic value. The verifier must distinguish them
from unexpected populated cells.

### R13 — Closed failure semantics

Verification **MUST** return a structured success receipt only after every
check passes. It **MUST** fail closed on malformed archives, unsupported
features, hash mismatches, or unexpected normalization. It **MUST NOT** repair
or rewrite the workbook during verification.

## 7. Errors, packaging, and compatibility

### R14 — Stable errors

All failures use existing OTC connector error machinery where applicable and
stable capability-specific codes for invalid plans, collisions, limits,
unsupported features, malformed archives, and readback mismatches. Error
contexts are bounded and credential-free.

### R15 — Capability discovery

The local-files package manifest and documentation **MUST** describe the
capability, supported plan features, limits, optional dependencies, and
whether image support is available. A caller can detect support before
submitting a plan.

### R16 — Backward compatibility

The existing Arrow table writer and Excel connector read path **MUST** retain
their current signatures and behavior. The new capability may share internal
helpers, but changing table value typing, sheet defaults, formula handling, or
receipt shapes requires a separate versioned change.

## 8. Test and acceptance requirements

The OTC pull request **MUST** include:

- unit tests for plan validation, deterministic names, literal formula-like
  strings, limits, merges, styles, and image placement;
- golden workbook tests covering multiple sheets, merges, layout settings,
  literal cells, and images;
- raw-archive corruption fixtures for formulas, typed cells, duplicate
  coordinates, duplicate ZIP members, relationship violations, and image
  tampering;
- failure-cleanup and destination-collision tests;
- existing table-writer and Excel connector regression tests; and
- a public capability-manifest/receipt example.

FinClaw's follow-up pull request **MUST** add an end-to-end fixture proving
that its current `render_excel()`/`verify_excel()` semantic behavior is
preserved through the OTC capability. Both repositories must pass their
normal test suites before the OTC revision is pinned for release.

## 9. Implementation constraints and non-goals

Use the package's existing optional-import and `ConnectorError` patterns for
`openpyxl`. Do not add formula evaluation, macro preservation, remote storage,
chart rendering, Dash, financial formatting rules, or domain-specific report
schemas to this capability. Those concerns belong to their owning layers.
