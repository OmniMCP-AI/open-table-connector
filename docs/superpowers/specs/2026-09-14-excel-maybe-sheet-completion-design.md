# OTC Excel and Maybe Sheet completion

Date: 2026-09-14. Status: implemented for the documented supported subset;
Maybe typed-value and catalog acceptance remain open. See the
[readiness evidence](../../spreadsheet-readiness.md) for tested gates and restrictions.
Implementation baseline: `538338ee9289bbe24a1bef41bd996208b2896f52`.

## 1. Scope and authority

Complete OTC local Excel and Maybe Sheet **sheet-mode** by consolidating existing
code. Google implementation/live acceptance is deferred; preserve existing Google
behavior. Financial semantics, application publication and authenticated replay
belong to the separate FinClaw integration spec, not OTC.

This replaces the remaining OTC scope/file decomposition of the
[old mixed plan](../plans/2026-09-14-spreadsheet-sessions-and-finclaw-readiness.md).
The [unified design](2026-09-13-unified-spreadsheet-operations-design.md) supplies
operation vocabulary. The [physical artifact design](2026-09-14-finclaw-excel-artifact-readiness-design.md)
sections 6–9 and 13.3 remain normative for exact layout, limits, hashing,
publication and ZIP/XML rules. This spec controls scope and consolidation; it does
not drop those guarantees. Follow the [four-task plan](../plans/2026-09-14-excel-maybe-sheet-completion.md).

## 2. Reuse and consolidate

| Existing code | Intended change |
| --- | --- |
| `sdk/workbook.py`, `sdk/result.py` | One Excel/Maybe resource facade and existing result adaptation; remove replaced duplicate wrappers |
| `spreadsheets/_operations.py`, `_protocols.py`, `_limits.py` | Harden existing contracts; one private `_session.py` for shared buffering/intent |
| `local_files/spreadsheet_workbook.py` | Keep loading/editing/staging/preservation together; extract only independent verification to `spreadsheet_verify.py` |
| Maybe connector/CLI/Formula/process helpers | Reuse targets, validation and transport; at most one `spreadsheet.py` for batch compilation |
| Existing CLI/conformance modules | Extend dispatch and tests; one command module if needed |

No per-resource module tree, generic grid/style engine, result-wrapper hierarchy,
plugin framework or second command schema. Keep expectation helpers in the session;
version persisted manifests/command files rather than every in-process record.
The two justified seams are session/provider storage and writer/independent verifier.
Providers use neutral values/errors; SDK adapts once. Preserve deferred Google
compatibly without treating it as proof of the new buffered contract.

## 3. Public behavior

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
result = sheet.formulas().set("C2", "=A2+B2").with_results()
book.write()
```

Default-client `otc.workbook` mirrors this. Keep canonical `file://` aliases and
creation defaults; choose `general/1.0` explicitly for a new editable workbook.
No public plan/expectation classes, receipt family or unwrap calls.
`.with_results()` returns that operation's immutable result without I/O; a planned
edit never becomes a later commit receipt. Use `write().with_results()` for commit evidence.

Create/edits buffer until write. Close/context exit never saves. Dry-run retains
pending edits. Track new/clean/dirty, writing, sealed/closed and unresolved effects
privately; derive state where possible and reuse existing commit-result statuses.
Reads label committed versus supported pending state; unsupported overlay reads
fail explicitly. Freeze caller inputs and results. Reject concurrent writes,
closed/sealed edits and stale bindings. Partial/unknown effects block further
mutation; reconciliation observes only and must establish known state or require rebind.

Default writes require a tested atomic boundary, otherwise reject before dispatch
unless `allow_partial=True`. Retain every known effect/created ID and uncertainty;
no automatic fallback/retry or invented idempotency/CAS guarantees. Coordinate local
sessions with existing immediate Formula writes; external applications do not share OTC locks.

Value strings remain literal. Formula shorthand infers bound dialect and reuses
Formula validation/translation. Queue unsaved formulas and values in the same
commit. No evaluation engine; literal profile rejects formulas. Recalculation needs
a clean session and supported capability. Preserve legacy Table/Formula contracts.

Strict `verify(expected=None)` uses independently captured session intent. Reopened
strict verification requires a supplied versioned expectation, never one derived
from the file itself. Remote verification describes observations, not XLSX guarantees.

## 4. Editing and Maybe support

Both providers require binding/creation, ordered sheet discovery/create/rename/delete,
bounded range read/literal write/clear, dimensions, styles/formats, merges/unmerge,
stable sorting, formula storage, supported image placement/readback, save and close.
Validate A1 bounds/direction, names, matrix types/shape, blank versus empty string,
finite numeric precision, date epochs and serial-60, patch/reset rules, sort
keys/header/blank/tie behavior and native units. Update supported references or
reject structural edits before mutation.

Publish operation rows for tables, names, links, notes, validation, conditional
formats, filters, charts, pivots, images, protection and visibility, separating
read/create/update/delete where needed. Each row states support, restrictions and
named tests. Unsupported native pivot creation may remain a gap. Missing required
baseline rows block that provider; never claim full catalog coverage from identities.

Existing XLSX edits must preserve unrelated formulas, tables/names, charts/pivots,
images and hidden/protected sheets. Test supported-part preservation and reject
unsafe unsupported parts before save. Atomic replacement alone proves neither
preservation nor external-writer concurrency protection.

Pin/negotiate actual `mbs` commands, flags and JSON envelopes using existing process
helpers. Validate URI/override and sheet-mode gid before dispatch; preserve Base
worksheets in mixed documents and stable identities across rename. Translate units,
references and single-cell note restrictions explicitly; never invent CLI commands.
Without a tested atomic batch, reject by default and require partial opt-in. Test
creation-plus-population, each dispatch timeout, stale bindings and retained created
IDs. Recorded tests cover every advertisement; disposable authorized live cases
have a separate gate. Missing credentials do not block local artifact completion.

## 5. Local physical acceptance

| ID | Required evidence |
| --- | --- |
| R1–R3 | Exact ordered sheets, names, literal `@` cells including empty strings, declared styles/native layout/print/view settings |
| R4–R5 | Exact merges with no hidden interior values; unchanged PNG/JPEG bytes, hashes, one-cell anchors and EMU dimensions |
| R6 | Trusted finite bounds enforced before/during parsing, decompression and image decode |
| R7–R10 | Owned staging, exclusive atomic publication, no formulas/calcPr/chains/links, deterministic intent/byte hashes, safe cleanup |
| R11–R13 | Independent raw and decoded checks against caller intent; missing/extra/malformed/unsupported coverage fails closed |
| R14–R16 | Stable reasons in existing results/errors, truthful capability discovery, compatibility and isolated installs |

Keep all individual R1–R16 rows in release evidence. Use one bounded immutable byte
snapshot for raw checks, decoded checks and content hash. Actual expansion counters,
DTD/entity rejection and exact allowed parts/content-types/relationships are mandatory.
Reject duplicate members/IDs/cells, escaping/missing targets, orphan media and extra
values. Never repair verifier input. Original image bytes are captured at queueing;
compare stored bytes and all declared properties using only documented normalization.
The referenced artifact spec defines precise limits, supported styles and units.

Canonical physical expectations include intended cells/layout/merges/images, exclude
paths/timestamps/ZIP ordering, and live in existing Receipt.details. Keep physical
semantic and exact byte hashes separate; receipts round-trip without cycles.
Validate -> owned sibling staging -> close -> independent verification -> no-clobber
publication. Preserve existing files/directories/symlinks and race winners. After
commit, retain the destination on subsequent failure and report honest state.

Optional `failure_directory` retains bounded failed owned bytes under exclusive
names before cleanup, with hash/size/phase/completeness. Record retention failure
separately from the primary error; diagnostic bytes are not verified artifacts.
Application attempt bookkeeping stays outside OTC.

## 6. Delivery and deletion gates

CLI calls the SDK, commits standalone mutations once and supports versioned batch
commands with dry-run/partial opt-in using existing envelopes/Change arguments.
Advertise only positively tested dispatch. Verify core-only and separate provider
wheel installs, image round-trips, secret redaction, URI routing and dependency direction.

Extend existing suites with independent corruption, collision/symlink/race,
cleanup/retention fault injection, preservation and recorded/live Maybe cases.
Delete replaced wrappers/helpers after those tests pass. Avoid tests per helper or
a separate evidence-document tree: one readiness matrix links exact tests/commands,
revision, environment and counts for local artifact, general Excel, Maybe and packaging.
Run supported-Python tests and repository lint/type/package jobs; compare failures
against an actual baseline. No merged PR alone establishes acceptance or FinClaw cutover.
