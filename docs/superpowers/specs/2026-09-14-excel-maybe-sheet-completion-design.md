# OTC Excel and Maybe Sheet completion

Date: 2026-09-14
Status: proposed; acceptance remains open.
Baseline: OTC main `538338ee9289bbe24a1bef41bd996208b2896f52`.

## 1. Scope and precedence

Complete the remaining OTC components for local Excel and Maybe Sheet sheet-mode.
Google Sheets implementation, new capabilities and live acceptance are deferred.
Preserve existing Google behavior through regression tests; Google is not a
release dependency for this delivery.

This spec replaces the remaining OTC scope of the
[previous mixed plan](../plans/2026-09-14-spreadsheet-sessions-and-finclaw-readiness.md).
The [unified design](2026-09-13-unified-spreadsheet-operations-design.md) retains
the API vocabulary. The [artifact design](2026-09-14-finclaw-excel-artifact-readiness-design.md)
sections 6–9 and 13.3 retain normative physical-profile details; this spec controls
provider scope and completion gates. Their FinClaw integration requirements move
to `finclaw-ng/docs/superpowers/specs/2026-09-14-otc-excel-integration-design.md`.

Only OTC code, CLI, packaging, tests and documentation belong here. Application
report translation, financial semantics, publication and authenticated replay
belong to FinClaw. OTC completion alone does not authorize application cutover.

## 2. Baseline and architecture

The baseline provides workbook entry points, a local workbook module, neutral
helpers and partial provider integration. Existing methods and passing legacy
tests do not establish completion of the previous plan.

Complete these components, refactoring existing code rather than adding a second API:

- `spreadsheets`: validated arguments, bounded session state, ordered changes,
  immutable physical expectations and neutral provider protocols.
- `sdk`: resource views, Formula normalization and existing result/error adaptation.
- `local_files`: coordination, XLSX editing/preservation, artifact writing and
  independent archive/XML/decoded verification.
- `maybe_sheet`: sheet-mode binding, canonical command compilation and observation
  through the existing credential-safe process transport.
- `cli`: resource commands over the same SDK.

Providers must not import SDK. Remove upward dependencies introduced by the
foundation. Optional packages load lazily; validate core-only and isolated provider
wheel installations. Internal bind/preflight/commit/observe records are closed,
versioned and serializable. Freeze caller inputs before queueing.

## 3. Slim public interface

```python
book = client.workbook.create("file:///absolute/path/report.xlsx",
                              profile="literal-artifact/1.0")
sheet = book.worksheet.create("Report")
sheet.range("A1:B1").write([["Account", "Amount"]])
sheet.range("A1:B1").style(bold=True)
book.write()
verification = book.verify().with_results()

book = client.workbook("file:///absolute/path/model.xlsx")
sheet = book.worksheet("Model")
sheet.range("A2:B2").write([[10, 20]])
result = sheet.formulas().set("C2", "=A2+B2").with_results()
book.write()
```

Default-client `otc.workbook` mirrors this API. Use `create(uri)`, not a mode
flag. Retain canonical `file://` routing and alias identity. No public WorkbookPlan,
SheetPlan, WorkbookExpectation or new receipt family. Ordinary arguments and
existing OperationResult, Receipt and OTCError conventions are sufficient.

Direct calls require no unwrap. `.with_results()` performs no I/O and observes
that operation's immutable captured result. A queued edit reports planned state;
its result does not turn into a later write receipt. Obtain commit evidence from
`book.write().with_results()`.

`create` binds a logical new workbook without a remote mutation. `write` commits;
`close` and context-manager exit discard pending edits without implicit save.
`verify(expected=None)` may use trusted intent retained by this session's write.
A reopened strict artifact needs an explicit versioned expected mapping, never
an expectation derived from its own decoded contents. Remote verification reports
supported observations and never claims XLSX physical verification.

## 4. Session and Formula semantics

Implement states `new`, `clean`, `dirty`, `writing`, `unknown`, `partial`, `sealed`
and `closed`, with tested transitions. Track stable worksheet keys, base revision,
ordered pending changes and immutable snapshots separately. Reads identify a
committed observation or supported pending overlay; unsupported overlay reads fail
explicitly rather than silently returning stale data.

Validate the whole batch before dispatch. Dry-run preserves pending changes.
Successful general writes become clean; literal-artifact writes seal the session.
Reject concurrent writes and edits after close/seal or uncertain effects.
`reconcile()` observes only, never retries; resume only after establishing a known
state, otherwise require a fresh binding.

Atomicity is the default. Reject batches without a tested atomic boundary before
mutation unless `allow_partial=True`. Partial/unknown results retain known effects,
created IDs and failure phase. Idempotency keys do not imply deduplication without
provider support. Observation hashes are not compare-and-set tokens. Coordinate
local sessions with legacy immediate Formula writes and reject stale bindings;
document the limit that external applications do not share OTC's lock.

Value writes keep formula-looking strings literal. Explicit Formula shorthand
infers the bound dialect and reuses existing validation/translation. Queue unsaved
formulas and values in the same commit. No OTC evaluation engine is introduced.
Literal-artifact sessions reject formulas. Recalculation requires a clean session
and an independently supported capability. Preserve legacy Table/Formula behavior.

## 5. General editing and preservation

Required baseline for both providers: workbook binding/creation, sheet discovery
and ordered creation/rename/delete, bounded range reads/literal writes/clear,
row/column dimensions, styles/number formats, merge/unmerge, deterministic sort,
explicit formula storage, supported image placement/readback, save and close.

Validate A1 bounds/direction, worksheet naming/collisions, matrix shape/types,
blank versus empty string, dates/epochs and finite numeric precision. Date objects
cannot silently represent Excel serial 60; explicit numeric serials remain numeric.
Define style patch/reset rules, sort keys/header exclusion/blank placement/stable
ties and tagged native units. Structural edits update supported references or fail
before mutation.

Publish per-provider operation rows for native tables, names, hyperlinks, notes,
validations, conditional formats, filters, charts, pivots, images, protection and
visibility, separating read/create/update/delete where support differs. Each row
states implemented/unsupported/deferred, restrictions and named tests. Unsupported
native pivot creation may remain a documented gap. Missing required baseline rows
block that provider's release; catalog identities alone are not implementation.
Do not claim full Excel manipulation while intended features remain gaps.

Existing XLSX editing requires a supported-part preservation matrix and independent
edit/save/reopen fixtures with unrelated formulas, tables, names, charts/pivots,
images and hidden/protected sheets. Reject unsupported objects before save when
preservation cannot be demonstrated. Atomic replacement does not prove either
preservation or concurrency safety.

## 6. Generic local literal-artifact profile

Complete `literal-artifact/1.0` against independent caller intent:

| ID | Acceptance |
| --- | --- |
| R1 | Exact ordered sheets and resolved names |
| R2 | Exact string/type/coordinate coverage, explicit `@`, text bounds and empty strings |
| R3 | Declared styles, dimensions, view and print properties verified |
| R4 | Exact merges; hidden merged-interior values rejected |
| R5 | Embedded PNG/JPEG bytes, hashes, anchors and dimensions verified |
| R6 | Trusted finite limits enforced before and during parsing/decode |
| R7 | Owned staging and atomic create-exclusive publication |
| R8 | No formula, calcPr, calculation chain or external-link parts |
| R9 | Deterministic expectation and separate byte/physical semantic hashes |
| R10 | Ownership-safe cleanup and honest post-commit state |
| R11 | Independent decoded comparison to expected intent |
| R12 | Bounded ZIP/XML/content-type/relationship checks |
| R13 | Missing, extra, malformed or unsupported coverage fails closed |
| R14 | Stable versioned reasons in existing result/error conventions |
| R15 | Write/verify discovery agrees with dispatch |
| R16 | Legacy compatibility and optional installation isolation |

Support fonts/fills/alignment/wrapping, the defined border subset, native column
widths/row heights, gridlines, freeze panes, print area, paper/orientation/fit,
centering and all six margins. Apply the exact unit normalization and border
rules in the prior artifact spec section 13.3, with no hidden numerical tolerance.
Capture image bytes at queueing, validate MIME/hash/decode limits, embed unchanged
bytes and compare stored bytes plus one-cell anchors and integer EMU dimensions.

Use one bounded immutable byte snapshot for raw validation, decoded verification
and content hashing. Enforce actual decompression counters, not metadata alone.
Disable DTD/entities and enforce the exact allowed part/content-type/relationship
graph from section 13.3. Reject duplicates, escaping/missing targets, orphan media,
external links, hidden merged values and unexpected populated cells. Verify every
declared property; never repair/resave verification input.

Retain section 7's trusted defaults: 128 sheets, 250,000 semantic cells, 64 MiB
text, 128 images, 16 MiB per image/128 MiB total, 40 million pixels per image,
256 MiB compressed file, 10,000 ZIP members, 128 MiB per expanded member/512 MiB
total. Bounded caller overrides are allowed; untrusted receipts never raise limits.

Use canonical versioned JSON with sorted mapping keys and preserved semantic
array order. Physical semantic hashes include intent, layout and image identities,
but exclude paths/timestamps/ZIP order. Hash exact saved bytes separately. Existing
Receipt.details holds expectation schema, hashes, limits and resolved identities;
receipts must serialize and round-trip without cycles.

Validate first, write an owned sibling temporary file, close and independently
verify it, then publish with a tested no-clobber primitive. Never exists-then-replace.
Preserve pre-existing paths and competing outputs. After commit, retain the
destination on cleanup/acknowledgement failure and report committed/unknown state.

Optional `failure_directory` is generic caller-owned diagnostic quarantine:
retain bounded failed owned bytes under exclusive unique names before cleanup;
report path/hash/size/phase/completeness. Report retention failure alongside the
primary error. Diagnostic bytes do not receive successful verification. Application
attempt bookkeeping remains outside OTC.

## 7. Maybe Sheet sheet-mode

Pin/negotiate the tested canonical `mbs` CLI contract before enabling operations.
Map actual commands, target flags and validated JSON envelopes; do not invent
commands. Normalize range formats through supported local style operations.
Validate URI and sheet-mode gid before dispatch, including target overrides.
Use stable worksheet identities and preserve Base worksheets in mixed documents;
Base targets must reject sheet-mode operations before mutation.

Queue until write. Compile an atomic batch only if the tested CLI provides that
boundary; otherwise reject by default and require explicit partial opt-in. Cover
creation-plus-population, per-command timeout, stale bindings, idempotency conflicts
and created-ID retention. Unknown mutations never trigger fallback/retry. Translate
native units, references and single-cell notes restrictions explicitly.

Each advertised operation needs recorded-process positive/negative tests. Live
acceptance uses disposable authorized sheet-mode documents and mixed-document
preservation. Missing credentials leave the live gate pending, independently of
local artifact release. Remote write success never establishes XLSX guarantees.

## 8. CLI, discovery, packaging and release gates

Expose `otc spreadsheet` resource commands through SDK. Standalone mutations
explicitly commit once. A versioned command-file workflow supports batches,
dry-run and partial opt-in with existing JSON envelopes, without public plan
classes. Errors redact secrets and reject invalid inputs before dispatch.

Enable capabilities only after dispatch/preflight tests. Update documentation and
operation matrix together. Test core-only imports, each optional provider alone,
SDK/CLI URI equivalence, clean wheel artifact/image round-trips and dependency
boundaries. Keep Google regressions without new Google implementation requirements.

Required gates:

1. Shared recording-provider tests: every transition, immutable results, overlays,
   dry-run, concurrency, reconciliation and dependency isolation.
2. Local R1–R16: golden/corruption fixtures plus duplicate members/IDs/cells, forged
   sizes, DTD, external relationships, calcPr, changed layout/images, orphan media,
   race/symlink/collision and save/verify/publish/cleanup/retention fault injection.
3. General Excel: required baseline and preservation corpus, with explicit gaps.
4. Maybe: advertised matrix, process failure corpus and separate live acceptance.
5. Distribution: complete supported-Python suite, lint/type/package checks, CLI
   and wheel tests on the exact candidate. Compare failures to an actual baseline
   before labeling them pre-existing; a merged PR is not release evidence.

Update readiness docs and a future implementation plan with per-gate status,
revision, commands, environment and exact counts. This spec does not perform
implementation or application cutover.
