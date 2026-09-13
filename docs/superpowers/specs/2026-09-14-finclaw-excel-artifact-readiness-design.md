# FinClaw Excel Artifact Readiness

**Date:** 2026-09-14

**Status:** Proposed; implementation and FinClaw cutover are not complete.

**Scope:** OTC local XLSX artifact creation and verification, plus the FinClaw integration acceptance contract.

## 1. Decision

Deliver `literal-artifact/1.0` within OTC's unified spreadsheet architecture as
the next complete consumer-facing feature. FinClaw keeps its current Excel
implementation until OTC passes requirements R1–R16 and a FinClaw adapter passes
semantic parity and publication tests.

The delivery is a working writer, independent verifier, receipts, capability
discovery and integration evidence. Shared models or passing Table tests alone
do not satisfy readiness. General Workbook/Worksheet/Range editing across Maybe
and Google is not a prerequisite for the local artifact feature. Those providers
continue to share the architecture without claiming this strict profile.

OTC owns physical workbook mechanics. FinClaw owns financial values, report
composition, source mappings, evidence, chart generation and the final semantic
publication gate. No OTC package may import FinClaw.

## 2. Relationship to existing specifications

This document specializes the
[unified spreadsheet design](2026-09-13-unified-spreadsheet-operations-design.md)
for FinClaw readiness. It retains every requirement in the
[original R1–R16 requirements](2026-09-13-excel-artifact-capability-requirements.md)
and the semantic ownership boundary in the
[replacement design](2026-09-13-otc-excel-artifact-replacement-design.md).

For this delivery, the APIs and release gates below take precedence over the
earlier foundation-only implementation plan. This does not change existing Table
or Formula contracts or authorize replacing FinClaw merely because a package
installs successfully.

Canonical operation identities are `spreadsheet.workbook.write/1.0` and
`spreadsheet.workbook.verify/1.0`. `literal-artifact/1.0` is their required profile,
not a second provider or a competing `excel-artifact/v1` implementation. Add
`workbook.write` explicitly to the unified operation catalog as a declarative
create operation, distinct from arbitrary editing of an existing workbook.

## 3. Verified baseline and gaps

OTC baseline inspected: `664b47571ee76fce947c4860f6bf054083cae90e`.
It contains spreadsheet value models and six capability identities, but no
WorkbookPlan, artifact writer/verifier, bounded archive inspection or artifact
receipts. `write_excel` creates a workbook and saves directly to its destination;
it is not the required artifact operation. The new direct-return worksheet API
is also not implemented by that baseline.

Existing models need hardening before reuse: RangeRef compares coordinate pairs
lexicographically instead of validating both axes, CellStyle lacks finite-value
and complete type validation, and ImageSpec has no expected-hash input, explicit
size bounds or placement dimensions. Only SpreadsheetTarget currently has a
closed `from_wire` method. No artifact validation may assume these models already
meet the strict contract.

FinClaw's inspected `src/finc/analysis/excel.py` creates literal `@` cells,
ordered sheets, images, merges and print layout, then checks raw semantic cell
coverage and decoded cells/images. Its expected dictionary contains `sheets`,
`sheetOrder`, `images` and `placements`; verification returns `status`,
`semanticHash`, `contentHash`, `cells` and `images`.

The inspected FinClaw file is a behavioral reference, not proof that all new
guarantees already exist there: its writer saves through `destination.open('xb')`
without an owned-stage cleanup protocol, and its verifier does not independently
compare all layout, merge and calculation properties. OTC must add those checks,
not simply transplant that implementation and call R1–R16 complete.

## 4. Public API and ownership

Use the ordinary SDK Workbook, Worksheet and Range views. A new local artifact
is an explicit create session at a bound destination:

```python
book = client.workbook.create(
    "file:///absolute/path/report.xlsx",
    profile="literal-artifact/1.0",
)
sheet = book.worksheet.create("Report")
sheet.range("A1:B2").write([["Metric", "Value"], ["Revenue", "1200"]])
sheet.range("A1:B1").style(bold=True, fill="#183245", foreground="#FFFFFF")
sheet.range("A4:B4").merge()
sheet.images.insert("/absolute/path/chart.png", anchor="A6", width=850, height=400)
book.write()
book.verify()

# Optional details use the existing post-operation result pattern.
result = book.verify().with_results()
```

These are proposed APIs. `book.write()` saves to the already bound URI;
`book.write(uri)` is not added because it introduces a second destination and
ambiguity about resource identity. `book.verify()` verifies that same target.
`otc.workbook(uri)` and `otc.workbook.create(uri, ...)` delegate to the default
client's identical operations. Use resource-local verbs consistently: workbook
creation is `client.workbook.create(...)`, worksheet creation is
`book.worksheet.create(...)`. Opening uses the callable resource accessor.
Do not add mode flags, `create_workbook(...)`, or plural creation aliases.
No public WorkbookPlan, SheetPlan, WorkbookExpectation, LiteralCell,
ImagePlacement, WorkbookWriteReceipt or WorkbookVerifyReceipt is required.
Callers use strings, matrices, paths, keyword options and existing resource views.

`client.workbook.create(uri, ...)` starts an unsaved local workbook session. Its edit
operations modify session state, not the destination file; their results carry
`outcome=planned`, `commit=not_started` and `verification=not_applicable`.
`write()` performs the one create-exclusive commit. General workbook sessions
use the same buffered lifecycle for created and opened workbooks across Excel,
Maybe sheet-mode and Google Sheets, as specified in the unified design's
cross-provider lifecycle section. `client.workbook(uri)` opens an existing workbook
and fails if absent. The strict profile allows reopening for verification only;
general existing-workbook editing is evaluated under the separate editing gate.
No implicit save on close, garbage collection or context-manager exit is allowed.
After successful write the strict artifact session is sealed against further edits and
another write; verification and reading captured results remain available.

The public facade lazily resolves the local Excel
implementation through provider registration. Shared models, validation and
canonicalization remain provider-neutral; local-files owns openpyxl, ZIP/XML
inspection and filesystem behavior. Missing provider/image dependencies produce
a structured unsupported-capability failure without breaking core imports.

Local targets use paths or standard `file:///absolute/path/report.xlsx` URIs.
Reject nonlocal hosts, remote schemes and unsupported extensions for this
profile. URI decoding and local path resolution use the same routing policy as
other OTC file operations; no new Excel scheme is introduced.

Resource methods return the ordinary operation value/summary directly and raise
`OTCError` on failure. Use existing `OperationResult`, `Receipt`, outcome, commit
and verification conventions for detailed evidence; add operation-specific
versioned fields to `Receipt.details`, not new public receipt classes. The
direct-return summary's no-I/O `.with_results()` exposes that operation's result.
It never reruns a write or verification. Reuse existing wire serialization;
attached result references must not produce recursive serialization.

Internally, `write()` captures a versioned expected-state manifest from session
intent before serialization and includes it in the write receipt's details.
`book.verify()` uses that captured manifest after write. To verify in another
process, use `client.workbook(uri).verify(expected=stored_manifest)` where the
manifest is the JSON object retained from the write receipt. There is no public
expectation class to construct. Missing expected state is an error for strict
verification: inspecting an existing file cannot establish what was intended.
The expectation must be retained through FinClaw's authenticated metadata path;
untrusted bytes cannot supply their own verification authority.

The public dispatch facade may adapt neutral provider results to SDK errors;
provider code must not import SDK error/result types. Preserve existing structured
outcome, commit and verification distinctions in that adapter.

## 5. Internal shared contract

All internal wire records have a schema version, closed field sets, explicit enum values,
strict types and round-trip serialization. Frozen models must also freeze nested
collections. Unknown fields, nonfinite dimensions, booleans used as numbers and
invalid coordinate bounds are rejected before writing.

These are internal records behind the resource operations, not additional public
classes or a second caller-authored plan language.

| Record | Required contents |
| --- | --- |
| Workbook session | Profile, ordered worksheets, naming policy, limits |
| Worksheet state | Local key, requested name, semantic cells, merges, explicit layout, images |
| Semantic cell | Uppercase A1 coordinate, exact string, supported style properties |
| Style | Versioned font/fill/alignment/border subset; semantic number format fixed to `@` |
| Image | Local image key, captured bounded bytes, expected SHA-256, MIME type, cell anchor, pixel width/height |
| Expected-state manifest | Complete resolved sheet order, cells/types/values, merges, declared layout/style properties, image placements/hashes, profile/schema identities |
| Write Receipt.details | Resolved names, complete manifest, semantic/content hashes, limits used |
| Verify Receipt.details | Verified profile, expectation hash, physical content hash, actual counts, completed checks and verification level |

The expected-state manifest is prepared from validated caller intent before persistence.
The writer may return that expectation, but the verifier must independently
observe physical bytes. A write receipt or echoed provider response is never
evidence that the file matches the expectation.

Naming supports strict names and explicit deterministic sanitization. Reject
empty workbooks, invalid Excel names and case-insensitive collisions in strict
mode. Sanitization matches FinClaw's existing replacement, 31-character truncation
and ` (2)` suffix behavior when its adapter requests that policy. The adapter
reserves `Exact values` and `Evidence and scope` before naming report sheets.
The resolved map is part of the expectation and receipt.

Coordinates must be within `A1:XFD1048576`. Validate each rectangle axis
independently, reject duplicates and overlapping merges, and reject semantic
cells inside merged ranges except at their anchors. Empty string is a semantic
value; style-only cells carry no semantic value. Strings over 32,767 characters
or invalid XML characters fail without truncation or substitution.

## 6. Layout and image parity

The first profile implementation MUST support every property used by the
inspected FinClaw renderer:

- Fonts: family, point size, bold and sRGB color; solid fills; top alignment and
  wrapped text, plus the explicitly supported border subset.
- Explicit row heights in points and column widths in Excel character units.
  These units are tagged native layout options; they must not pass through a
  lossy pixel conversion when matching FinClaw output.
- Gridline visibility, freeze panes, print area, landscape/portrait, A4 paper,
  fit-to-page, fit width/height, horizontal centering and all six page margins.
- Ordered merges and one-cell PNG/JPEG placements with zero offsets and explicit
  dimensions. FinClaw supplies its 850-pixel chart width and proportional height;
  OTC does not choose chart/report dimensions.

FinClaw retains row-height calculations and report layout decisions and supplies
the resulting properties. OTC validates and writes them. The verifier compares
every declared property after documented unit normalization. Pixel dimensions
normalize to integer EMUs at 9,525 EMUs per pixel; physical expectations contain
the normalized dimensions. There is no unspecified global tolerance.

Read and hash image bytes before writing. Reject mismatch with the supplied
expected hash and invalid declared MIME/decode combinations. The output embeds
those bytes without external links or transcoding. Reopen image relationships
and hash stored media bytes for verification. Reject extra, missing, relocated,
resized or changed images and unreferenced media. Repeated identical images may
share media only if the manifest explicitly permits that storage representation;
placement coverage remains exact.

## 7. Limits and deterministic evidence

A validated `limits` keyword mapping on workbook binding provides positive finite ceilings for sheets, semantic cells,
total UTF-8 text bytes, image count, per-image/total image bytes, decoded image
pixels, compressed file bytes, ZIP member count, per-member decompressed bytes
and total decompressed bytes. Baseline defaults are:

| Limit | Default |
| --- | ---: |
| Sheets | 128 |
| Semantic cells | 250,000 |
| Text bytes | 64 MiB |
| Images | 128 |
| Bytes per image / total image bytes | 16 MiB / 128 MiB |
| Decoded pixels per image | 40 million |
| Compressed workbook | 256 MiB |
| ZIP members | 10,000 |
| Decompressed bytes per member / total | 128 MiB / 512 MiB |

These are operational defaults to validate against the parity corpus, not Excel
format limits. Callers may supply explicit bounded overrides. Verification uses
its own trusted limits, never larger limits read from an untrusted workbook or
receipt. Check metadata before decode and enforce actual streamed byte ceilings;
do not trust ZIP central-directory sizes alone. Limit errors include the limit
name, bound and observed count without workbook contents.

Use canonical versioned UTF-8 JSON, sorted object keys, preserved semantic array
order and no nonfinite numbers. Hashes use `sha256:<hex>`. Exclude paths, timestamps,
operation IDs, raw bytes and ZIP ordering from the semantic hash; include resolved
names, semantic cells, declared layout/styles, merges and image hashes/placements.
The receipt records limits separately. Hash exact saved bytes independently for
content identity. Repeated plans must have the same semantic hash; XLSX byte
identity across library versions is not required.

OTC semantic hashes describe the physical expectation. FinClaw's existing
semanticHash covers its own expected dictionary, including placements/mapping
information. Preserve both identities under distinct fields; do not substitute
OTC's hash for FinClaw's hash or claim their algorithms are equivalent.

## 8. Exclusive write lifecycle

1. Validate and resolve the entire session state, layout, names, assets and limits without
   creating the requested destination.
2. Create an exclusively owned temporary file in the destination directory.
   Write literal string cells with `@`, suppress calculation-on-open, and close
   workbook/image resources on every exit path.
3. Verify the staged bytes against the independent expectation before publication.
4. Publish through an atomic no-clobber primitive on the same filesystem, such as
   linking the closed staged inode to a previously absent destination. Reject
   unsupported publication guarantees; never emulate this with exists-then-replace.
5. Remove the owned staging name and return the receipt. Concurrent creators must
   yield exactly one success; the loser cannot truncate or delete the winner.

The no-clobber publication is the commit point. Before it, failures leave the
destination absent and clean only owned staging files. After it, a cleanup or
acknowledgement failure retains committed/uncertain state and identifies the
created artifact for reconciliation; do not report not-committed or blindly retry.
Pre-existing files, directories and symlinks must never be removed or overwritten.

The caller's destination remains a staged application artifact: FinClaw must
still complete semantic verification before assigning its published identity.
OTC's atomic local creation is not FinClaw's publication approval.

## 9. Independent fail-closed verification

Read a bounded byte snapshot once. Raw checks, decoded checks and content hashing
must operate on those same bytes to avoid verifying one file version and hashing
another. Verification never modifies or repairs its input.

Perform bounded raw validation before loading openpyxl:

- Reject duplicate archive members, duplicate relationship IDs, invalid or
  escaping relationship targets, missing parts and malformed XML. Disable DTD
  and external entity processing; validate a documented profile part allowlist.
- Resolve workbook sheet relationships and check names/order/type/coverage.
  Reject external relationships throughout the allowed workbook graph, including
  drawings and external workbook links, and reject macros/unsupported active parts.
- Reject formula elements, disallowed calculation settings, invalid/duplicate
  coordinates, invalid shared-string references, nonliteral populated cells,
  and hidden semantic cells discarded by merged-cell decoding.
- Validate raw merge and drawing coverage, one-cell anchors, offsets/dimensions,
  relationship integrity and stored media hashes. Do not infer media correctness
  solely from openpyxl's decoded object list.

Then compare decoded sheet order, exact coordinate/type/value coverage, `@`
formats, declared styles/layout, merges and image placements to the expectation.
Normalize only documented equivalent representations, including explicit empty
inline strings. Style-only cells may exist but cannot conceal extra values.
Missing or unsupported observations cause failure, never partial success.

A success receipt requires every check and complete coverage. Stable error
details distinguish validation, collision, resource-limit, malformed archive,
unsupported feature and readback mismatch. Use existing ConnectorError categories
with versioned artifact reason codes; SDK adaptation retains commit/verification
state and does not expose arbitrary parser text or workbook contents.

## 10. Discovery and packaging gate

The shared package owns internal validated records, profile and operation identities;
the SDK exposes the resource methods. It does not require caller-authored plan types.
Local-files registers the implementation and advertises write/verify plus
`literal-artifact/1.0` only when its full implementation and dependencies are
available. Binding details list layout/image support, limits, version and
`xlsx-physical` verification. The closed core manifest wire shape is unchanged.

Declare Pillow/image dependencies and supported openpyxl versions explicitly;
clean wheel installation must run an image round trip. Add the new package to
workspace build, metadata, typing, dependency-boundary and independence checks.
OTC packages must resolve from one compatible revision for FinClaw pinning.

Correct provider documentation that currently describes unimplemented Spreadsheet
operations as available. Keep advertised capability IDs and executable examples
aligned with actual implementation. Do not alter `write_excel`, Table receipts,
managed temporal Excel or Formula activation behavior to implement this profile.

## 11. FinClaw adapter and cutover

FinClaw translates authenticated report sections into workbook/worksheet/range
operations and retains an independent semantic expectation. It preserves naming, sheet order,
cell formatting, exact values, evidence leaves, ranking/pivot projections, chart
error rows, chart dimensions and chart-to-source mappings.

`render_excel(sections, destination=...)` keeps its external expected-dictionary
contract. `verify_excel(path, expected)` first runs OTC physical verification,
then FinClaw semantic verification. Financial IDs, placements and mapping hashes
remain exclusively in FinClaw. An OTC success receipt alone cannot publish an
artifact. Preserve existing exception-facing behavior through explicit error
translation where callers depend on it.

Persist the versioned physical expectation alongside FinClaw metadata using a
documented versioned envelope; do not silently change the canonical legacy
expected dictionary or its hash. Retained legacy artifacts remain verifiable
through a version-selected legacy reader until an independently tested migration
exists. No rerender/recalculation is required for replay.

First run parity with the current renderer retained as a test oracle. Switch
rendering and remove direct workbook manipulation only after the acceptance gate.
Keep the previous dependency pin and verification path recoverable for rollback.
There must be no automatic fallback to the old writer after an uncertain new
write, since that could duplicate or overwrite effects.

## 12. Acceptance matrix and release gates

The additional requirements in section 13 are part of these gates, not optional
follow-up work. They resolve failure-retention, replay and raw-format ambiguities.

Every row requires test evidence on the exact candidate OTC and FinClaw revisions.

| Requirements | Required evidence |
| --- | --- |
| R1 | Ordered multi-sheet fixture; invalid names; reserved names; deterministic collisions |
| R2 | Formula-like strings, empty strings, Unicode, 32,767/32,768 boundaries, out-of-bounds and duplicate coordinates, invalid XML text; raw string type plus `@` |
| R3–R4 | All FinClaw layout properties round-trip; tampered style/page/merge fixtures fail; overlapping and populated non-anchor merges rejected |
| R5 | PNG/JPEG embedding, dimensions, anchors and exact stored hashes; extra/missing/transcoded media and moved images rejected |
| R6 | Every limit at boundary and over boundary; decompression bombs, forged sizes and oversized decoded images rejected before unbounded allocation |
| R7 | Existing destination and symlink preservation; concurrent create race; no partial destination visible before commit |
| R8 | Raw formula/calculation-property corruption rejected, including formulas hidden beneath merges; no calculation engine invoked |
| R9 | Closed receipt round-trip, canonical hash fixtures, semantic determinism, independent byte hashes, FinClaw/OTC hash distinction |
| R10 | Failure injection at asset load/save/verify/publish/cleanup; resource closure; ownership-safe cleanup and honest post-commit state |
| R11–R13 | Independent expected-versus-actual comparison; duplicate ZIP/relationship/cell entries, bad targets, nonliteral/extra cells, corrupt shared strings and malformed XML all fail closed |
| R14–R15 | Stable bounded errors, clean install with images, profile discovery and missing-dependency rejection |
| R16 | Existing Table reader/writer, Formula, temporal and provider-independence suites unchanged |
| FinClaw parity | Existing analysis Excel suite plus golden multi-section, chart, pivot, ranking and evidence fixtures; equal legacy expected semantics; required visual/layout properties preserved |
| Publication/replay | Cell/image/source-mapping tampering blocks publication; committed-but-unverified output is never published; old retained artifacts replay without rerender |

Gate A: complete OTC writer/verifier with R1–R16 green, install/discovery evidence
and zero advertised unsupported guarantees. Gate B: FinClaw translation, golden
parity, semantic/publication/replay tests pass against a pinned OTC revision.
Only after both gates may FinClaw replace its current mechanics.

Track evidence in a readiness record containing candidate revisions, dependency
versions, commands, results, fixture identities and unresolved failures. A full
suite failure must be classified and resolved or explicitly accepted by the
maintainer before release; focused tests alone cannot establish readiness.

## 13. Critical-review closure requirements

### 13.1 FinClaw failure evidence

FinClaw currently tests retention of failed attempts, original output and partial
artifacts. Cleanup must not erase that evidence. Add an optional
`failure_directory` keyword to workbook creation, identifying a caller-owned
quarantine location distinct from the intended output path. FinClaw supplies its
attempt directory; ordinary callers retain cleanup-only behavior by default.

Before deleting a failed owned staging file, OTC preserves its bounded bytes
under an exclusively created, unique name in that directory. Record content hash,
byte count, failure phase, whether bytes are complete, and the evidence path in
structured error details. These bytes are unverified diagnostic artifacts and
must never receive a successful workbook receipt or published artifact identity.
Do not retain pre-existing destination contents implicitly. If retention fails,
report both the primary failure and evidence-retention failure; never claim that
evidence was preserved. Cleanup and retention have separate fault-injection tests.

After the commit point, do not delete the destination as failure cleanup. Return
committed/uncertain evidence so FinClaw can retain it through its attempt lifecycle.
The adapter preserves existing attempt/error bookkeeping and proves that physical
or semantic verification failure still blocks publication while keeping the
expected diagnostic records and bytes. Test the actual existing failure-retention
cases in `tests/test_analysis_excel.py`, not only a new success-path fixture.

### 13.2 Authenticated replay

FinClaw must authenticate saved results, templates, evidence and chart mappings,
rederive semantic expected values from those saved inputs, and compare them with
the retained placement map and physical manifest before accepting replay. Merely
trusting a stored manifest or a matching workbook/manifest pair is insufficient.
OTC compares physical bytes; it cannot authenticate financial meaning.

Require separate corruption tests for a modified workbook, modified manifest,
modified semantic placement, and a coordinated workbook/manifest modification.
All must fail unless the authenticated source-derived expectation matches.
Keep legacy expected-dictionary hashing unchanged and identify the physical
manifest's schema/hash separately. Both old and new envelope versions must replay
offline without rerendering charts, recalculating formulas, or accessing providers.

### 13.3 Exact physical profile rules

The writer emits no `calcPr` element, matching the inspected FinClaw writer's
calculation suppression, and no calculation chain or formula elements. The
profile verifier rejects any `calcPr`, `calcChain`, formula or external-link part.
This is an artifact-shape rule, not a guarantee about arbitrary client behavior
when a user later opens and edits the file.

Allow only the package content-types part, package relationships, core/app document
properties, workbook and its relationships, referenced worksheets and their
relationships, styles, theme, optional shared strings, referenced drawings and
their relationships, and PNG/JPEG media. All relationships must be internal,
correctly typed and resolve to allowed existing parts. Reject orphan drawings,
unreferenced media, unlisted parts, OLE/ActiveX, macros and external connections.
Writer-version fixtures define the allowed namespaces/content types for these
parts; expanding the allowlist requires new corruption tests and profile review.

Supported borders are none, thin, medium, thick, dashed, dotted and double on
left/right/top/bottom edges with explicit sRGB color. Diagonal, theme and automatic
color borders are rejected in this profile. Font/fill colors normalize opaque
ARGB to sRGB; opacity other than fully opaque is unsupported. Persisted dimensions
and margins normalize through decimal text at six fractional digits; compare
those normalized values exactly and reject nonfinite/out-of-range inputs.
Column widths retain tagged Excel character units, row heights use points, margins
use inches and image dimensions use integer EMUs. Golden fixtures must demonstrate
normalization on every supported openpyxl version; do not introduce a hidden
catch-all numerical tolerance.

### 13.4 Local versus remote coverage

The resource API and buffered session lifecycle apply to local Excel, Maybe
sheet-mode and Google Sheets. The strict artifact gate applies to local `.xlsx`
bytes. Maybe/Google must pass the general editing baseline and their advertised
feature gates in the unified spec before those capabilities are described as ready.
Neither provider inherits physical XLSX guarantees from a successful remote write.

Google image insertion/readback, provider print features, native tables, pivots,
protection and recalculation require explicit per-provider capability evidence.
Mixed Maybe documents must preserve Base worksheets while editing sheet-mode
worksheets. Unsupported operations fail before dispatch; unsupported features
already present must be preserved or cause preflight rejection, never silent loss.

Add general-editing acceptance for sorting, native tables, hyperlinks, protection,
sheet visibility, date/epoch and precision semantics, formula reference updates,
and unrelated-object preservation. A published three-provider matrix must distinguish
implemented, unsupported and deferred operations. Passing R1–R16 does not mean
this broader matrix is complete. “Full Excel manipulation” must not be claimed
while any intended feature remains merely listed or deferred.

## 14. Delivery boundaries

The implementation plan must cover four complete deliverables with explicit
dependencies: validated shared contracts; bounded writer plus independent raw
and decoded verifier; discovery/packaging and R1–R16 conformance; FinClaw adapter
and dual-repository parity/cutover. No deliverable may be labeled FinClaw-ready
before Gates A and B pass. Broad remote spreadsheet editing remains separately
tracked rather than silently dropped from the unified design.

## 15. Inspected source references

- OTC `packages/spreadsheets/src/open_table_connector/spreadsheets/model.py`
  and `capabilities.py` at the baseline above.
- OTC `packages/local_files/src/open_table_connector/local_files/excel_writer.py`,
  `manifest.py` and `packages/local_files/pyproject.toml`.
- FinClaw local worktree
  `/Users/admin/Code/GitHub/finclaw-ng/.worktrees/plotly-static-renderer`,
  `src/finc/analysis/excel.py` and `tests/test_analysis_excel.py`, inspected
  2026-09-14. This source snapshot informs requirements; it is not recorded
  release acceptance evidence.
