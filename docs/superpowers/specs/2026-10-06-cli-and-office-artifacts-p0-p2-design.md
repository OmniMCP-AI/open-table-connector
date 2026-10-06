# OTC CLI and Office Artifacts: P0-P2 Specification

Date: 2026-10-06 (Asia/Shanghai).
Status: implemented in PR #8; source-level acceptance is recorded, with live
OfficeCLI/browser and MaybeSheet gates explicitly pending.
OTC source baseline: `0ef07b2327800375c7782eb1d4dc18a132cd1e2e`; merged source:
`e37bb5027d8475dace0322b1110af71b4c4a9476`.
Research: [OfficeCLI comparison and recommendations](../../reports/2026-10-06-officecli-comparison-and-recommendations.md).

Implementation: [P0-P2 plan index and workstreams](../plans/2026-10-06-cli-and-office-artifacts-p0-p2.md). The workstreams are executed and their status is recorded in the acceptance ledger.

## 1. Objective and Decisions

Make OTC easier for people and agents to discover and operate, and extend it to editable document-table exports and rich spreadsheet workflows without replacing its table model or weakening verified-write behavior.

The user-approved scope direction carried into this proposal is:

1. Cover every P0-P2 recommendation in the research roadmap.
2. Use OfficeCLI for native DOCX/PPTX table creation and HTML/PNG/semantic views/watch.
3. Use **existing Excelize capabilities only** for rich local XLSX creation and object mutations. OfficeCLI must not write the authoritative spreadsheet.
4. Include **MaybeSheet sheet-mode as a first-class rich spreadsheet target**, using its existing Excelize-backed provider operations.
5. Add OTC integration and qualification, not new engine functionality. Missing MaybeSheet endpoints or Excelize features are not permission to enhance upstream engines.

This specification selects an additive design: shared operation discovery, thin ergonomic CLI commands, shared spreadsheet recipes, an optional document artifact adapter, and an optional MCP adapter. A global OfficeCLI-style CLI replacement is rejected because it would conflate tables, formulas, cells and document elements. A mandatory OfficeCLI spreadsheet backend is rejected because it contradicts the required writer boundary.

The scope spans independent subsystems. Sections 5-11 are workstream specifications with separate acceptance gates; section 13 establishes dependencies. Follow-on implementation plans should be split by workstream rather than making one oversized change.

The command/API/schema names below are the normative target and are now
implemented where the acceptance ledger marks them complete. Existing public
commands and result contracts remain authoritative; unsupported or runtime-
dependent paths continue to return explicit capability results.

## 2. Scope and Traceability

| ID | Priority | Required deliverable | Contract | Acceptance |
| --- | --- | --- | --- | --- |
| DISC-1 | P0 | Complete CLI reference and command index | Section 5 | A1 |
| DISC-2 | P0 | Offline operation schemas and live capability inspection | Section 5 | A2 |
| CLI-1 | P1 | Typed spreadsheet shortcuts | Section 6 | A3 |
| CLI-2 | P1 | Bounded stdin batch input | Section 6 | A4 |
| CLI-3 | P1 | Safe suggestions and explicit exit semantics | Section 6 | A5 |
| GUIDE-1 | P1 | Version-aligned task guide for agents | Section 6 | A6 |
| DOC-1 | P2 | Editable native DOCX/PPTX table exports | Section 8 | A7 |
| VIEW-1 | P2 | HTML/PNG/semantic views and watch lifecycle | Section 9 | A8 |
| RICH-1 | P2 | Rich local XLSX using existing Excelize APIs | Section 7 | A9 |
| RICH-2 | P2 | Shared rich operations on MaybeSheet sheet-mode | Section 7 | A10 |
| MCP-1 | P2 | Optional discover/inspect/execute adapter | Section 11 | A11 |
| RECIPE-1 | P2 | Replayable supported layout recipes | Section 10 | A12 |

Excluded: P3 resident workbook service; legacy binary `.doc`/`.ppt`/`.xls` converters; new renderers/formula evaluators; upstream engine/server enhancements; arbitrary Word/PowerPoint editing; automatic page-layout invention; whole-document dump/replay; bidirectional synchronization; Base-mode rich-object mutation; implicit Google/Feishu parity; and general raw XML mutation APIs.

Native outputs in P2 are `.docx`, `.pptx`, and `.xlsx`. Legacy extensions must return unsupported-capability before output mutation. They must never be aliases for OOXML files with renamed extensions.

## 3. Invariants

- Preserve `Client`, `Table`, `Query`, DataFrame, and existing table semantics. Document tables and arbitrary cell ranges do not become connector-backed `Table` values.
- Keep `read`, `inspect`, `convert`, `import`, `list`, and existing `spreadsheet` actions compatible. Preserve destination codec versus stdout representation and existing import conflict policies.
- Use canonical `file://` URLs for local artifacts and HTTPS document URLs for MaybeSheet. Bare local paths may normalize to `file://`. No new format-specific local URI schemes.
- Shared SDK/session logic owns execution policy; CLI and MCP are adapters. Providers perform physical I/O and do not acquire new reverse dependencies on the SDK.
- Ordinary value writes remain literal. Formula execution is explicit and provider-dialect-aware. No string-prefix inference or automatic property-name correction on writes.
- Retain existing `OperationResult` outcome, commit, verification, warnings and receipts. Do not replace them with a boolean success envelope.
- Capability declarations require dispatch and observation evidence. Static schema presence is not proof of provider support.
- Preserve native layout units and exact number-format strings. No implicit character/pixel or dialect conversion.
- Preserve current stricter `literal-artifact/1.0` behavior. Rich artifacts do not broaden that profile or bypass unsupported-part guards in existing writers.
- Local rich spreadsheet writes use Excelize. Remote rich writes use MaybeSheet's existing sheet-mode provider. No fallback to OfficeCLI or silent second-writer retry.
- No automatic install, self-update, client configuration modification, or background watcher on ordinary help/read/export commands.
- Report partial/unknown remote effects honestly. Do not synthesize rollback, idempotency, revisions, or physical verification from acknowledgments.

## 4. Architecture and Ownership

```text
CLI / Python SDK / optional MCP
                |
       discovery + normalized requests
                |
       SDK policy and result adaptation
          /              |                  \
 shared spreadsheet   document artifact    presentation
 session/recipes      orchestration        orchestration
     |                    |                   |
 local Excelize /      OfficeCLI          OfficeCLI views
 MaybeSheet adapter    DOCX/PPTX writer   on disposable copies
```

| Owner | Responsibility |
| --- | --- |
| `packages/contract` | Generic versioned operation descriptor/discovery contracts; provider-neutral data only |
| `packages/spreadsheets` | Shared operation schemas, typed rich-object requests, recipes, and existing session protocol |
| `packages/sdk` | Capability resolution, preflight, orchestration, normalized results, and lazy optional facades |
| `packages/cli` | Parser, renderer, help, shortcuts, explicit command lifecycle |
| `packages/local_files` | Existing Excelize adapter for the explicit rich-XLSX path; local publication/readback |
| `packages/maybe_sheet` | Existing remote command mappings, stable object IDs, provider observations and partial effects |
| New optional `packages/artifacts` | Neutral document export/view request models and physical adapter protocol; depends on contract only |
| New optional `packages/officecli` | OfficeCLI version/protocol adapter, DOCX/PPTX creation and views; no SDK import |
| New optional `packages/mcp` | MCP transport over SDK/discovery; optional MCP runtime dependency |
| `packages/conformance` and `specification/conformance` | Shared operation/transport parity and package independence gates |

Use existing entry-point discovery conventions for optional adapters, extending descriptor fields only through an explicitly versioned contract. Core imports and table commands must succeed when artifacts, OfficeCLI, MCP, or any provider are absent. New SDK facades must load optional contracts only when used.

Reuse `SpreadsheetProvider.bind/preflight/commit/observe` and the current buffered session. Add a distinct local rich profile, `rich-artifact/1.0`, selected explicitly for Excelize rich operations; do not silently change the engine for existing general workbook sessions. For MaybeSheet, keep its existing `general/1.0` provider profile and advertise admitted rich operations there; a local profile name must not manufacture a remote guarantee.

The shared operation catalog describes semantics, target types and validation. Each provider maps admitted operations to its engine. Transport adapters cannot add independent capability routing or retry logic.

## 5. P0: Discovery and Documentation

### 5.1 Commands

```sh
otc help spreadsheet range.style --output-format json
otc help spreadsheet image.insert --output-format json
otc capabilities --uri file:///absolute/path/report.xlsx --output-format json
otc capabilities --uri https://www.maybe.ai/docs/spreadsheets/d/DOCUMENT \
  --sheet Report --output-format json
```

`help` is static, offline and side-effect-free. It must work without credentials or OfficeCLI. It aggregates installed operation definitions and identifies unavailable optional packages; it never opens a target.

`capabilities` resolves an endpoint and optionally a sheet. It may authenticate/read metadata but must not mutate. Its response declares whether resolution used static descriptors or a live target observation, with timestamp and provider version where available. An unknown live state must not be reported as supported. A nonexistent local output can be assessed through static creation capabilities, with no claim that an existing workbook was inspected.

### 5.2 Descriptor contract

Use JSON Schema draft 2020-12 for argument schemas, with closed object properties. Each `otc.operation/1.0` descriptor contains:

| Field | Meaning |
| --- | --- |
| `schema`, `operation_id`, `version` | Descriptor identity, normalized operation ID, semantic version |
| `target_kind` | Table, worksheet, range, spreadsheet object, document artifact or preview session |
| `arguments_schema` | Required fields, scalar types, exact enums, constraints and conditional requirements |
| `capability` | Existing capability identity or explicitly introduced versioned identity |
| `profiles` | Profiles to which the semantic operation applies; not provider support |
| `effects` | `read`, `buffered_write`, `publish`, or `session_control` |
| `limits` | Static input bounds and references to provider-specific bounds |
| `result` | Existing result/value schema reference and verification meaning |
| `examples` | Valid machine-checkable requests and human command examples |

Endpoint capability entries add `support` (`supported`, `unsupported`, `unknown`), option constraints, advertised commit guarantees, observation/readback coverage, and reason codes. Unknown backend version is `null`, never guessed from a local dependency. All entries carry the operation version.

There must be one declarative source for operation documentation and validation where practical. During migration, existing validators can remain, but contract tests must compare schema-accepted cases with dispatch validation. Help must not expose a property as guaranteed when its provider ignores or rejects it.

### 5.3 Documentation

The main CLI reference must list all registered commands and spreadsheet actions, including style/config observations, batch, verify and new families. Generate/check its command index against the parser. Cross-link discovery, source/destination format rules, literal/formula distinctions, capability restrictions and result semantics. Runnable examples must use temporary/disposable targets in verification, never live accounts by default.

## 6. P1: CLI Ergonomics and Agent Guidance

### 6.1 Typed shortcuts

Add the following within `spreadsheet`, preserving `operation` and `batch`:

```sh
otc spreadsheet style --uri file:///absolute/path/report.xlsx \
  --sheet Report --range A1:F1 --bold --no-italic
otc spreadsheet format --uri file:///absolute/path/report.xlsx \
  --sheet Report --range D4:F38 --pattern '#,##0.00'
otc spreadsheet write --uri file:///absolute/path/report.xlsx \
  --sheet Report --range A1:B2 --values-file values.json
otc spreadsheet worksheet create --uri file:///absolute/path/report.xlsx \
  --sheet Summary
```

`style` maps to `range.style`; `format` to `range.format`; `write` to `range.write`. Initial worksheet shortcuts cover create/rename/delete and compile to existing operations. Rename requires `--name`; delete has no implicit cascade. Structural reference restrictions remain in provider preflight.

Initial style flags: bold/italic with explicit positive/negative forms, font name, font size, foreground, fill, horizontal/vertical alignment and text-layout. Fields and enums must be generated from or validated against the existing shared style schema; flags cannot introduce alternate semantics. Complex borders and provider-specific options remain available through structured operation arguments until typed coverage is qualified.

`--values-file` contains a rectangular JSON array of rows. Omission, null, false, zero, empty string and numeric-looking strings must stay distinct under the provider's advertised contract. A1 target dimensions and row/column limits are validated before dispatch. Formula-prefixed strings remain literals; this command does not gain a formula switch.

Shortcuts expose the same applicable `--dry-run`, `--allow-partial`, `--expected-revision`, `--idempotency-key` and failure-retention options as the existing mutation path. Unsupported guarantees reject. Every shortcut must produce the same normalized changes and semantic result as its generic equivalent.

### 6.2 Bounded batch stdin

`otc spreadsheet batch --commands -` reads stdin explicitly. A real filename retains existing behavior. No implicit stdin reads and no new inline payload flag in this scope.

Keep the exact version `1.0` envelope and mutation-only rules. File and stdin parsing both enforce 16 MiB of UTF-8 bytes, at most 10,000 changes, duplicate-property rejection, finite JSON numbers, closed keys, and valid operation targets. Read at most the byte limit plus one before rejecting. Empty/malformed input rejects before mutation. Stdin parsing is not end-to-end streaming execution: dispatch begins only after bounded parsing and preflight.

MCP must supply structured payloads, never consume protocol stdin as command data. A batch-input timeout/cancellation is a transport failure with no mutation if dispatch has not started.

### 6.3 Errors and compatibility

Add safe argument-path details and deterministic suggestions to rejected inputs. Suggestions are informational; they never change keys or retry writes. Errors must identify preflight rejection versus post-dispatch failure and preserve receipts for known/unknown effects. Never serialize raw provider exception objects, credential values or full authenticated URLs.

Keep existing exit behavior in P0-P2: table category mappings stay unchanged; new spreadsheet shortcuts and recipes use the existing spreadsheet result path, including `5` for caught `OTCError`. New artifact commands use `2` for input/usage rejection and `5` for failed/rejected/partial/unknown execution results; `0` requires a succeeded/planned result without a failed required verification. Document that clients must inspect commit/verification, not infer them from the process code. A future category normalization is a separate compatibility change.

### 6.4 Agent guide

Ship a compact guide covering discover, inspect, plan/dry-run, mutate, verify and deliver. Include local and MaybeSheet workflows, canonical URLs, explicit formulas, partial effects, snapshot previews and capability errors. Help and guide examples must match the installed version. Installation into agent clients remains an explicit user action; publishing a guide does not authorize auto-installation.

## 7. P2: Shared Rich Spreadsheet Operations

### 7.1 Provider scope

Local XLSX and MaybeSheet sheet-mode are both required targets. The shared Excelize backend architecture for MaybeSheet is user-provided context; qualify the exposed MaybeSheet protocol rather than inferring remote capabilities from the local Python binding.

For local `rich-artifact/1.0`, Excelize is the sole writer from creation/template opening through final save. Existing openpyxl general/literal paths remain unchanged. Independent readers may inspect but must not resave rich output. OfficeCLI receives disposable presentation copies only.

For MaybeSheet, dispatch existing authenticated provider commands to stable Sheet-engine worksheet identities. Reject Base-engine targets and preserve other Base worksheets. Do not download, modify locally and upload a replacement as an implicit fallback.

### 7.2 Object admission

Normalize shared IDs as `spreadsheet.<operation>/1.0`. Preserve existing operation IDs and their arguments. Introduce object-specific operations only for an admitted existing engine API; do not invent a generic arbitrary engine-call endpoint.

| Family | Existing local API evidence | P2 obligation |
| --- | --- | --- |
| Images | `add_picture`, `add_picture_from_bytes`, `get_pictures`, `delete_picture` | Mandatory initial insert/read/list/delete workflow for both providers where already exposed; independent bytes/anchor verification |
| Charts | `add_chart`, `add_chart_sheet`, `delete_chart` | Qualify existing chart kinds/options and expose supported operations |
| Shapes | `add_shape` | Qualify existing creation options; no invented CRUD parity |
| XLSX tables | `add_table`, `get_tables` | Native table-object creation/read, distinct from range data |
| Pivots | `add_pivot_table`, `get_pivot_tables` | Existing creation/read options, cache/reference preservation fixtures |
| Comments | `add_comment`, `get_comments`, `delete_comment` | Existing comment model only |
| Validation | `add_data_validation`, `get_data_validations` | Existing rule types/reference behavior |
| Conditional formatting | `new_conditional_style`, `set_conditional_format`, `unset_conditional_format` | Existing style/rule combinations and physical readback |

The inventory was observed on Python `excelize 0.1.0`; it is not blanket acceptance. Each family must receive an explicit disposition: qualified operation subset, or unsupported with the specific existing API/transport/readback blocker. A wrapper is in scope; new Excelize functionality or a new MaybeSheet server endpoint is not. Missing qualification prevents advertising that operation, and must remain visible in the release matrix rather than silently disappearing from scope.

Common typed object requests contain target worksheet identity, object kind, create/update/delete/read intent only where supported, anchor/reference coordinates, and versioned options. Image input uses original bytes/MIME/hash, not OfficeCLI file paths. Unknown options reject. Provider-specific option schemas may extend the common subset under a named provider namespace; they cannot redefine common fields or accept unchecked property bags.

The image baseline for MaybeSheet is currently bounded PNG/JPEG, cell anchors, stable picture IDs and an 8 MiB insertion limit. Explicit sizing is currently rejected by its adapter. Preserve this until an existing command and readback prove support; do not add the limit to unrelated local operations or claim sizing parity from common backend ancestry.

### 7.3 Commit and verification

Local sequence: validate all changes, stage within the destination filesystem, write through Excelize, save/close, independently observe retained intent, then publish with existing conflict/coordination protections. Creation defaults to no overwrite. Existing-workbook changes require an explicit session and stale-source guard. Partial results from an unpublished staging file are not committed destination effects. Publication followed by cleanup failure must retain committed-state evidence.

MaybeSheet sequence: bind, preflight the whole request, dispatch via current provider commands, retain created IDs and per-command receipts, independently observe effects. Current multi-command writes require `allow_partial=True`; unsupported expected revision/idempotency rejects. Partial/unknown effects freeze further mutation until existing reconciliation/rebind requirements are satisfied. Never automatically retry uncertain writes.

Verification covers the requested object fields and declared preservation scope. Image bytes/anchors, chart/table definitions, pivot caches, comments/rules and unrelated template content need object-specific fixtures. Exported XLSX inspection is supplementary remote evidence, not a substitute for provider identity/readback. Missing export/revision support must be reported honestly.

The current general writer rejects pivot/unsupported parts. Do not route rich output through it or weaken its guard. Local rich-profile verification is distinct from literal-artifact verification and must report its narrower object coverage.

## 8. P2: Native Document Table Export

### 8.1 Interface and authoring boundary

```sh
otc artifact export --from orders.csv --to file:///absolute/path/report.docx \
  --engine officecli --spec word-table.json
otc artifact export --from orders.csv --to file:///absolute/path/deck.pptx \
  --engine officecli --spec slide-table.json
otc artifact export --from orders.csv --to file:///absolute/path/report.xlsx \
  --engine excelize --spec rich-workbook.json
```

SDK consumers use a lazy `Client.artifacts()` facade with `export`, `view`, and `watch` operations accepting the same typed requests as the CLI. Results are existing `OperationResult` values containing typed artifact/preview metadata. The facade does not turn artifact files into tables or depend on OfficeCLI at core import time.

`artifact export` is create-only for local destinations. Templates are read into a staging copy; original templates are not modified. Existing artifacts require a separately opened supported session, not a hidden overwrite flag on export. Source collection uses the existing SDK and bounded limits, not a second file/data parser in OfficeCLI.

### 8.2 Export spec

Use a closed `otc.artifact-export/1.0` JSON envelope with `format`, `columns`, `header`, `display`, `template`, `placement`, and `layout` fields. `format` is `docx`, `pptx` or `xlsx` and must match the output codec. `template` is optional; all other structural fields are required, with empty objects allowed only where their schema defines defaults. `columns` is an ordered unique list of source fields, with explicit display labels. No arbitrary CLI strings or shell fragments are accepted.

Display policy must define null, date/time, numeric formatting and locale behavior. Defaults are deterministic: null displays empty, booleans `true`/`false`, date/time ISO-8601, strings unchanged, and numeric display avoids locale grouping unless explicitly requested. DOCX/PPTX cells hold display values, not a lossless typed database; receipts retain the source schema and display policy. XLSX preserves supported typed values and uses explicit cell formatting.

DOCX placement is document-body append or a qualified existing template table target. PPTX placement is a selected/new slide with explicit position/size. XLSX placement identifies a worksheet and top-left cell, with an explicit header policy. Exported document tables must be native editable objects, not screenshots. Cell data is passed with structured per-cell operations; comma/semicolon joining is forbidden for arbitrary values. Escape/encoding tests include quotes, delimiters, newlines, Unicode and leading zeros.

`layout` is a format-discriminated object, not a free-form property map. DOCX/PPTX variants contain admitted native table formatting and the chunking options below. The XLSX variant contains `profile: "rich-artifact/1.0"` and an `operations` array of normalized spreadsheet operation records. Source rows are written first to the declared placement; layout/object operations follow in the same staging session. Images reference explicitly supplied bounded assets with content hashes. No operation may change the destination, invoke another writer, or fetch an undeclared resource. Schema definitions must fix required fields and defaults for each admitted operation before that operation is exposed.

Large-table policy is explicit bounded row chunks. No automatic pagination engine is added. PPTX requires a positive `rows_per_slide` and a maximum slide count; DOCX uses existing Word table flow and supported layout primitives. Overflow unresolved by existing operations fails required visual acceptance or is reported as unverified, never solved by silently omitting data.

Read back created IDs/paths and use them for subsequent operations. Positional paths are not durable identities. Word/PowerPoint formulas are exported as explicitly selected display results or literal text, never promised as recalculating spreadsheet formulas.

### 8.3 OfficeCLI adapter

Qualify a pinned binary version and protocol behavior; no install/update during execution. Spawn with argv, never a shell. Use existing no-auto-resident/update opt-outs for one-shot export, and explicitly save/close before independent inspection. Reject unknown properties rather than accepting OfficeCLI's auto-correction/partial-property behavior as OTC success. Inspect per-item warnings and results, not exit code alone.

Export receipts retain source snapshot identity, output media type/hash, engine version, object mapping, display policy, omission diagnostics and verification coverage. Required semantic verification failure prevents publication. Optional visual review is a separately reported state; a valid file is not automatically visually verified.

## 9. P2: Views and Watch

### 9.1 Views

```sh
otc artifact view --uri file:///absolute/path/report.docx --mode html \
  --to file:///absolute/path/report.html
otc artifact view --uri file:///absolute/path/deck.pptx --mode screenshot \
  --page 1 --to file:///absolute/path/slide-1.png
```

Initial modes: HTML, screenshot, text, outline, stats and issues, each enabled only for qualified format support. Schema validation is exposed as a distinct diagnostic operation. PNG requires an available supported browser; absence is an explicit capability/dependency error. Fonts and renderer versions must be recorded. PDF/SVG or other outputs are not blanket P2 promises and require an already installed, qualified backend capability.

Render a closed snapshot in disposable storage. Source hashes before/after presentation must match. The authoritative spreadsheet must never be edited, recalculated or resaved by OfficeCLI. For MaybeSheet, use an existing authenticated export operation and pass only the local snapshot to OfficeCLI. Record provider revision if available; otherwise timestamp/hash plus revision-consistency unavailable. No automatic upload of rendered or edited copies.

Output selectors must be format-specific. `--page` is not silently interpreted as a worksheet or range. Bounded screenshot output must be nonblank and correctly framed; source values/objects still need independent semantic checks. A renderer omission is a presentation limitation, not permission to change the workbook with another writer.

### 9.2 Explicit watch lifecycle

```sh
otc artifact watch start --uri file:///absolute/path/report.xlsx
otc artifact watch status --session SESSION_ID
otc artifact watch refresh --session SESSION_ID
otc artifact watch stop --session SESSION_ID
```

`start` creates a disposable working snapshot and explicit preview process, binds loopback only, selects an available port, and returns session ID/URL, source and snapshot hashes, format, provider/export timestamp, editability, persistence policy and process ownership. It must not stop unrelated processes or reuse a port by killing its owner. Session state is stored in a user-scoped runtime directory with an unguessable ID and verified process identity; `stop` may terminate only owned processes. This preview lifecycle is not a P3 workbook mutation daemon.

OfficeCLI's current watch refreshes on its own edits, not arbitrary external writes. `refresh` closes/releases the current snapshot session, obtains a new committed source snapshot and restarts the existing renderer/watch as needed. No default polling or background remote monitoring. A future requested refresh interval requires explicit bounds and cancellation; it is not part of P2's initial contract.

For XLSX/MaybeSheet, watch is presentation-only relative to the authoritative source. Use an existing read-only mode only if proven. If stock watch exposes editing, mark `editability=preview_copy_only` and `persistence=discard`; do not label the UI read-only. Reject a `read_only_required` request when no existing mode satisfies it, with static HTML/PNG as a suggested alternative. Never publish preview-copy mutations.

For DOCX/PPTX, the initial OTC watch wrapper also defaults to disposable review. Advanced OfficeCLI authoring remains separate; the wrapper does not add implicit publish-on-stop. `stop` closes only the preview session and cleans owned temporary data. A crash/timeout leaves authoritative artifacts untouched and exposes cleanup diagnostics. Status after process death returns stopped/failed state, not a stale live URL.

## 10. P2: Layout Recipes

Add `otc spreadsheet recipe export` and `otc spreadsheet apply`. Existing version `1.0` mutation batches remain unchanged; recipes have a separate `otc.spreadsheet-recipe/1.0` envelope.

```json
{
  "schema": "otc.spreadsheet-recipe/1.0",
  "version": "1.0",
  "requirements": ["spreadsheet.range.style/1.0"],
  "operations": [
    {"operation_id":"range.style","target_key":"Report",
     "arguments":{"address":"A1:F1","bold":true}}
  ]
}
```

Envelope fields are exactly those shown. Operation records reuse existing normalized `operation_id`, `target_key`, `arguments` shape. Requirements are validated against operations, never trusted as proof of support. P2 layout recipes include supported styles, number formats, row/column sizing, view config and qualified placement changes to existing objects; values, formulas and external resources are excluded from automatic export. Placement-only replay requires an explicit object binding and cannot recreate absent image/chart content. Explicit artifact recipes can reference separately validated source data or image assets under their own schema.

Export reads actual supported layout/object observations. It must not reconstruct alleged readback from previous write parameters. When any requested property cannot be observed, default export rejects; explicit `--allow-incomplete` may produce a recipe only with a separate result warning/coverage manifest listing omissions. An incomplete recipe must never be labeled a lossless workbook dump.

Apply preflights every operation and requirement, resolves current stable target bindings, then compiles into the existing session. `--dry-run` performs no mutations; remote metadata reads remain allowed. `--allow-partial` retains current remote commit meaning, not permission to drop unsupported fields. Local/MaybeSheet recipes share semantics over their advertised subsets. Applying a recipe containing an unsupported chart/style option rejects before dispatch.

Recipe inputs reuse the 16 MiB/10,000-operation limits and strict JSON parser. Asset inputs are bounded separately by the provider's existing limits; no arbitrary file/network fetching from a recipe. Native dimensions remain native: a local character width must not become an approximate remote pixel width. Caller-provided provider-specific values require explicit schema fields and capability checks.

## 11. P2: MCP Adapter

Provide an optional `otc-mcp` stdio executable with three initial tools:

| Tool | Typed request | Behavior |
| --- | --- | --- |
| `otc_discover` | Static operation selector or endpoint capability request | Same schemas/capability resolution as CLI |
| `otc_inspect` | Operation ID, target and typed arguments constrained to read effects | Same SDK observations; bounded output |
| `otc_execute` | Operation ID/typed request or versioned batch/recipe, explicit execution flags | Same validation, session and result path |

Tools accept structured objects, not shell command strings. `execute` supports dry-run and requires explicit partial-effects flags where needed. `inspect` rejects operations whose descriptor effect is a write/publish/session mutation. Neither tool exposes arbitrary subprocess or raw provider calls. Transport cannot invent a new retry policy.

Use an existing supported MCP library, not a hand-built JSON-RPC implementation. Keep stdout protocol-only and stderr credential-safe. Return structured existing operation results; map failed/rejected/partial/unknown or required-verification-failed results to MCP error semantics while retaining commit evidence. Success with unrelated informational warnings is not automatically failure.

Discovery must remain lazy and bounded; avoid embedding every provider property schema in every tool description. Schema references returned by discover must resolve to the installed version. Require an explicit deployment-owned allowed-root/allowed-provider policy for local artifact paths and remote credentials; do not accept credentials in tool arguments or inherit arbitrary shell access.

CLI, SDK and MCP parity tests must compare normalized requests, preflight rejection, result fields and persisted effects for the same fixtures. MCP is not a replacement for `otc-process`, whose existing framed transport remains separate.

## 12. Limits, Security and Failure Behavior

All request envelopes are versioned/closed; parse limits precede provider dispatch. Reuse existing workbook resource limits, including archive expansion checks. New document export uses bounded source collection and explicit row/column/page counts; one operation cannot request an unbounded document or screenshot sequence.

Subprocess adapters require a finite configured deadline and bounded diagnostic capture. Cancellation terminates owned child processes, records known effects and retains staged artifacts only under the existing explicit failure-retention policy. Do not print unbounded stdout or raw document bodies into errors.

Use argv and structured JSON, preserve literal shell metacharacters, reject unsafe template/asset path traversal under the configured root, and do not resolve arbitrary network resources from exported document contents as engine instructions. Renderer network/font dependencies must be explicit; credentials never enter its environment merely because source collection needed them.

Preflight is not a remote lock. Capability or topology changes between discovery and dispatch must surface as provider errors without invented atomicity. Verification occurs against the actually committed artifact/observed provider state, not an earlier clean snapshot. Every error path must preserve whether source/output remained untouched, committed, partial or unknown.

## 13. Delivery Order and Gates

| Wave | Workstreams | Dependency and independently useful outcome |
| --- | --- | --- |
| 1 | DISC-1, DISC-2 | Existing functionality discoverable; static/live capability distinction tested |
| 2 | CLI-1/2/3, GUIDE-1 | Common edits and batch input easier, with compatibility and result parity |
| 3A | RICH-1, RICH-2 | Shared image/object contracts with local and remote provider evidence |
| 3B | DOC-1 | Native document-table export; independent of new spreadsheet objects |
| 4A | VIEW-1 | Snapshot views/watch over accepted local or remote exports |
| 4B | RECIPE-1 | Replay subset builds on observed capabilities from waves 1-3 |
| 4C | MCP-1 | Adapts accepted operations from earlier waves; no new domain semantics |

Priorities define scope/order, not calendar estimates. Each wave can release independently, but P0-P2 cannot be marked complete while a required workstream is omitted. MaybeSheet is not deferred out of RICH-2 simply because local tests pass. A missing existing remote operation is an explicit capability gap; document its disposition without developing a new server feature.

| Gate | Required evidence |
| --- | --- |
| A1 | Parser/reference inventory matches; current and new examples validate |
| A2 | Offline help does no I/O; live unknown/support states truthful; schemas agree with provider validation |
| A3 | Shortcut/generic request and result parity; boolean omission, units, types and formula literals preserved |
| A4 | File/stdin parity; exact byte/count boundaries; duplicate keys/non-finite input rejected; no MCP stdin consumption |
| A5 | No mutation on invalid-key suggestions; redaction; legacy exit behavior preserved; partial/unknown evidence retained |
| A6 | Guide examples checked against schemas/parser; no automatic client install |
| A7 | Native DOCX/PPTX editable-table readback; delimiter/Unicode/type-display fixtures; template preservation; no overwrite |
| A8 | HTML/PNG nonblank/framed; backend absence explicit; watch lifecycle/port ownership; unchanged authoritative hashes; remote freshness |
| A9 | Excelize object inventory disposition; image/object independent readback; staged publication/conflicts; unsupported parts never reach general writer |
| A10 | MaybeSheet recorded protocol plus authorized disposable live evidence for advertised claims; stable IDs, Base preservation, partial effects and sizing restrictions |
| A11 | CLI/SDK/MCP parity; stdout framing, access policy, payload limits, cancellation, secret handling |
| A12 | Observe/export/apply/reopen equivalence for supported layout subset; explicit omissions; provider units/requirements preserved |

Cross-cutting fixtures include null versus empty string, leading zeros, large integers/decimals, dates, formula-prefixed literals, Unicode/shell metacharacters, duplicate worksheet names/case rules, stale revisions, concurrent publication, missing fonts/browser, partial remote writes, and a workbook containing images, charts, names, validation and pivots. No test may silently drop an unsupported object to obtain a green round trip.

Run relevant focused suites per workstream, then package-boundary/independence and universal conformance gates before release. Optional live tests require the repository's configured disposable-target authorization; recorded tests alone cannot be labeled live acceptance. Report exact engine/provider versions and hashes of verification fixtures/results.

## 14. Current Evidence and Implementation Handoff

The research recorded 37 focused existing CLI tests passing in a clean frozen
environment. The implementation and release acceptance are recorded in the
[P0-P2 acceptance report](../../reports/2026-10-06-p0-p2-acceptance.md). Local
Excelize object method presence is not treated as round-trip qualification;
OfficeCLI was source-reviewed but its live runtime was unavailable, and
MaybeSheet live acceptance remains gated by authorized disposable credentials.

Before implementing an object family, freeze its concrete request/option schema from existing engine APIs and current provider commands, then test the common semantics and provider restrictions. Do not claim or fill a missing capability by analogy with another engine/provider. This qualification is part of RICH-1/RICH-2, not an unbounded engine-development task.

Follow-on plans should name exact files, request types, validators, operation mappings, fixtures and commands for each workstream. They must preserve the invariants and gate IDs in this spec. No product code, dependency installation, commits or release actions are requested by this specification-writing task.

## 15. Source References

- [Research, source index and evolving scope](../../reports/2026-10-06-officecli-comparison-and-recommendations.md)
- [Package boundaries](../../package-boundaries.md)
- [CLI parser](../../../packages/cli/src/open_table_connector/cli/__main__.py)
- [Spreadsheet CLI parser/dispatch](../../../packages/cli/src/open_table_connector/cli/spreadsheet_commands.py)
- [Output and exit handling](../../../packages/cli/src/open_table_connector/cli/output.py)
- [SDK results](../../../packages/sdk/src/open_table_connector/sdk/result.py)
- [SDK workbook facade](../../../packages/sdk/src/open_table_connector/sdk/workbook.py)
- [Spreadsheet provider protocol](../../../packages/spreadsheets/src/open_table_connector/spreadsheets/_protocols.py)
- [Spreadsheet session](../../../packages/spreadsheets/src/open_table_connector/spreadsheets/_session.py)
- [Current capability identities](../../../packages/spreadsheets/src/open_table_connector/spreadsheets/capabilities.py)
- [Local workbook provider](../../../packages/local_files/src/open_table_connector/local_files/spreadsheet_workbook.py)
- [Local verification](../../../packages/local_files/src/open_table_connector/local_files/spreadsheet_verify.py)
- [MaybeSheet spreadsheet provider](../../../packages/maybe_sheet/src/open_table_connector/maybe_sheet/spreadsheet.py)
- [Spreadsheet usage and capability catalog](../../user-guide/spreadsheet-operations.md)
- [Financial layout specification](2026-09-20-unified-table-financial-layout-design.md)
