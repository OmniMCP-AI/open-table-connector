# OTC Excel and Maybe Sheet Completion Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans; check tasks against evidence.

**Goal:** Complete Excel/Maybe workbook operations by consolidating existing code.
**Architecture:** One SDK facade, one private shared session, existing provider storage,
one independent XLSX verifier. Google implementation and FinClaw integration are excluded.
**Spec:** [Excel and Maybe completion](../specs/2026-09-14-excel-maybe-sheet-completion-design.md).
**Evidence:** [Readiness matrix](../../spreadsheet-readiness.md), including individual R1–R16 rows.

This execution checklist consolidates the original four tasks without changing the
normative requirements. Tests and release acceptance are separate: the supported
Maybe commands pass, but its required typed-value baseline remains blocked upstream.

## 1. Consolidate sessions and results

Existing SDK `workbook.py`/`result.py` adapt the private spreadsheets `_session.py`
and existing `Change`/provider protocol. Provider storage uses neutral values/errors.

- [x] Buffer edits until write; support pending local reads, dry-run and no-save close.
- [x] Freeze inputs and captured results; retain existing result/receipt types.
- [x] Reject concurrent use, closed/sealed sessions, stale handles and unsafe retries.
- [x] Retain partial/unknown effects; reconcile by observation or require rebind.
- [x] Queue explicit Formula shorthand with literal values; infer dialect and reuse validation.
- [x] Remove replaced Excel/Maybe wrappers and provider SDK imports; preserve Google behavior.
- [x] Run shared lifecycle, SDK, Formula and compatibility regressions.

## 2. Complete independently verified local artifacts

Keep loading/editing/staging in `local_files/spreadsheet_workbook.py`; only
`spreadsheet_verify.py` is new. It verifies one bounded immutable archive against
independently retained intent, without calling the writer.

- [x] Verify ordered sheets, literal/empty text, native styles/layout, merges and PNG/JPEG bytes.
- [x] Enforce finite resource bounds before/during parsing, actual decompression and image decode.
- [x] Reject malformed/extra/duplicate XML, ZIP, relationships, cells, formulas and unsupported parts.
- [x] Capture intended properties before serialization; return deterministic manifests and byte hashes.
- [x] Stage, close, verify and publish exclusively; preserve race winners and committed destinations.
- [x] Retain bounded owned diagnostics with separate primary/cleanup/retention error evidence.
- [x] Test independent fixtures, corruption, boundaries, creator races, symlinks and injected failures.
- [x] Preserve empty literals through reopening and installed-wheel image/receipt roundtrips.

## 3. Extend the existing Excel and Maybe adapters

Reuse local storage/Formula coordination and Maybe connector/process helpers;
Maybe has one `spreadsheet.py` compiler rather than a second resource framework.

- [x] Implement supported sheet/range/dimension/style/format/merge/sort/Formula/image operations.
- [x] Validate addresses, shapes, values, units and reference changes before mutation.
- [x] Preserve tested existing Excel objects; reject unsafe rich text and structural edits.
- [x] Pin actual `mbs 0.28.4` commands and JSON contract `1.0`; preserve Base worksheets and gids.
- [x] Reject non-atomic batches unless partial execution is explicit; retain IDs and uncertain effects.
- [x] Require complete formula evidence before remote sorting or merging populated ranges.
- [x] Run recorded and authorized disposable live tests; clean up all owned live documents.
- [ ] Complete Maybe numeric, Boolean, date/time and literal empty-string writes.
  The tested RAW command loses these distinctions. OTC rejects them before dispatch;
  an upstream typed-write contract plus recorded/live readback tests is required.

## 4. Expose, validate and publish

The existing CLI uses SDK sessions via one command module. Versioned bounded batch
files contain existing operation verbs/arguments, not a new public model hierarchy.

- [x] Route CLI standalone mutations and batches through one commit; support dry-run/partial flags.
- [x] Bind advertised capabilities to real conformance operations and update dependencies/discovery.
- [x] Document supported/unsupported/deferred operations and separate release gates; no FinClaw cutover claim.
- [x] Remove duplicate wrappers; retain independent corruption and preservation tests.
- [x] Record final Python 3.11–3.14, lint/type/package and clean installed-wheel results.
- [x] Commit the verified implementation and evidence for the requested remote-main delivery.
  Source: `dea43f785833fc83ad9ac7bf8c5c03b5e37292b7`; final evidence is recorded above.

The remaining Maybe requirement blocks that provider's complete baseline release.
It does not block delivery of the local artifact implementation and tested remote
subset. Optional catalog work and deferred Google/FinClaw work stay outside this plan.
