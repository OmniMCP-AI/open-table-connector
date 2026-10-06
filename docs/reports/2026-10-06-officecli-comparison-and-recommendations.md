# OfficeCLI and OTC: CLI Design Research and Recommendations

Research date: 2026-10-06 (Asia/Shanghai). Status: research baseline and
recommendations implemented through the P0-P2 surface; live OfficeCLI/browser
and MaybeSheet acceptance gates remain pending.

Follow-on: [P0-P2 specification](../superpowers/specs/2026-10-06-cli-and-office-artifacts-p0-p2-design.md)
and [acceptance report](2026-10-06-p0-p2-acceptance.md).

## 1. Recommendation

**Adopt OfficeCLI's discoverability and selected spreadsheet ergonomics, but do not replace OTC's public interface with its document-DOM command language.** Keep `read`, `inspect`, `convert`, and `import`; retain the Python SDK as the application authority. Improve the `spreadsheet` command family with operation-specific help and a small number of typed shortcuts that compile into the existing buffered session operations.

The highest-return lessons are:

1. Make capabilities, argument types, examples, restrictions, and readback guarantees discoverable through machine-readable, operation-scoped help.
2. Give common spreadsheet edits concise commands without making callers construct internal operation records.
3. Make batch input easier to pipe while retaining OTC's versioned, bounded, strict JSON contract.
4. Add optional visual inspection for report workflows, separately from physical verification and formula correctness.
5. Publish short, task-oriented agent guidance generated or checked against the actual command surface.

Do not adopt automatic property correction on writes, implicit formula activation, positional paths as persistent identity, hidden resident autosave, raw XML mutations in the neutral API, or claims that a local-file transaction generalizes to remote providers.

OfficeCLI is a useful complementary document-authoring tool and a source of interaction patterns. With the requested expanded scope, recommend an **optional artifact-export integration**: OfficeCLI creates native Word/PowerPoint tables and provides HTML/PNG/watch presentation; **existing Excelize capabilities provide rich spreadsheet operations for both local XLSX and MaybeSheet sheet-mode**. OfficeCLI is not a spreadsheet authoring backend in this proposal. Do not enhance either engine. This does not make OfficeCLI a mandatory runtime or turn document elements into OTC's core `Table` model. Section 9 defines the expanded recommendation and its boundaries.

## 2. Scope, Method, and Confidence

### Inspected revisions

| Project | Exact source | Scope |
| --- | --- | --- |
| OfficeCLI | `8df116451aafc9d192787d623514de0c52ea2dc9` | Public `main` snapshot, project version `1.0.154`; commit dated 2026-10-06 02:26:17 +08:00 |
| OTC | `0ef07b2327800375c7782eb1d4dc18a132cd1e2e` | Current checkout; existing user changes to `.gitignore`, `AGENTS.md`, and untracked `opencode.jsonc` were not modified |

OfficeCLI was cloned to a temporary directory and its README, command handlers, help schemas, batch executor, resident flush policy, MCP server, rendering adapter, SDK descriptions, and build configuration were inspected. OTC's CLI parser, pipeline, output handling, workbook session, capability definitions, local workbook provider, verification code, tests, and user guides were inspected. Sources are linked in section 13, with OfficeCLI links pinned to the inspected commit.

The graph tools named in OTC's `AGENTS.md` were not available in this session. Bounded file searches and source reads were used instead. The unauthenticated GitHub repository API was rate-limited; raw source and the Git checkout were available. No popularity, release-download, issue-volume, or maintenance-cadence conclusions are inferred from unavailable metadata.

**Evidence levels:** implementation observations below mean the relevant source was read; documentation claims are attributed; proposed commands are explicitly marked. OfficeCLI was not installed or executed, and its performance, Excel fidelity, and formula coverage were not independently benchmarked. The machine did not expose `dotnet`. Its public snapshot references a test project in `officecli.slnx`, but that test project is absent from the tracked tree; SDK smoke scripts and build smoke checks are present. Schema documentation describes contract tests, but those test implementations could not be audited here. This is an evidence limitation, not a claim that the maintainers have no tests. [O1, O2, O4, O12]

OTC's focused current CLI tests were executed successfully in a fresh environment: **37 passed in 15.29 seconds**. The initial existing-environment run failed with CLI PATH and provider-loading errors; the clean frozen-workspace run passed without source changes. These results validate the selected OTC CLI cases, not the full provider matrix. Reproduction is in section 12.

## 3. The Products Solve Different Primary Problems

OfficeCLI's central abstraction is a document with addressable elements: paragraphs, slides, shapes, worksheets, cells, charts, and other OOXML objects. Its shared `IDocumentHandler` exposes `Get`, `Query`, `Set`, `Add`, `Remove`, `Move`, semantic views, raw XML, and schema validation. Different formats implement the same general editing vocabulary. [O3]

OTC's central abstraction is a physical connector-backed `Table`, with `Client`, deferred `Query`, and Polars data frames. The SDK owns normalized results, SQL policy, and application ergonomics; connectors own physical I/O and provider behavior. Workbook, layout, and formula extensions provide additional surfaces without pretending that an arbitrary cell range is a table. [T1, T2, T6]

This distinction should drive the CLI decision. A document tree is a good common model for Word, Excel, and PowerPoint editing. It is a poor universal model for a PostgreSQL table, a paginated Feishu base, a remote worksheet, and a temporal data query.

### Detailed comparison

| Dimension | OfficeCLI at inspected revision | OTC at inspected revision | Implication |
| --- | --- | --- | --- |
| Primary workload | Create, inspect, edit, render office documents | Read/move tables; SDK queries and mutations; controlled workbook operations | Competing mainly in XLSX/report workflows |
| Main formats/providers | DOCX, XLSX, PPTX; format/export plugins | Local tabular formats, SQLite/PostgreSQL, Google Sheets, MaybeSheet, Feishu and temporal integrations | Preserve provider-neutral routing |
| Command structure | `verb file path --prop key=value` | Table verbs with `--from`/`--to`; `spreadsheet action --uri ...` | Improve spreadsheet ergonomics locally |
| Target model | Document path plus element path or selector | Canonical endpoint plus typed table/grid/field/session target | Avoid introducing a second endpoint grammar |
| Data model | Nodes and predominantly string property maps | Typed tables, range matrices, explicit formulas, operation results | Keep value type fidelity |
| Discovery | Embedded format/element/verb schemas; progressive help | Connector listing, argparse help, operation IDs and guides | Operation-scoped schema help is a clear gap |
| Structured output | Opt-in JSON envelopes plus human output | Table JSONL by default, JSON/CSV/table options; workbook SDK JSON | Keep existing automation defaults |
| Batch | Array of command items; stdin/file/inline; default rollback on item failure | Versioned `changes` envelope; bounded file input; buffered mutation session | Borrow input convenience, retain contract |
| Sessions | Named-pipe resident documents, auto-start and deferred flush | Explicit SDK buffer; CLI mutation commits once; close does not save | Do not silently change durability semantics |
| Local transaction | Temporary-copy promotion for nonresident atomic batches | Staged, verified publication with preservation and conflict guards | Similar goal, different verification contracts |
| Remote transaction | Local OOXML batch mechanism does not establish remote provider guarantees | Capability-aware rejection or explicit partial opt-in | Provider restrictions must survive new syntax |
| Formula behavior | Own evaluator; README advertises 350+ functions | Explicit Formula Extension; native dialects; local Excel calculation through Excelize | No evaluator replacement without conformance |
| Validation | OpenXML schema validation, issue inspection, rendering | Results/receipts, physical verification, layout observations and hashes | Visual and semantic checks are complementary |
| SQL and time series | No equivalent public lane found in reviewed surface | Relational SQL lite, temporal SQL lite, native SQL in SDK | Avoid conflating DOM `query` with SQL |
| SDK architecture | Python/Node thin clients over resident protocol; C# embedding entry point | Python SDK is primary; CLI/process adapt lower layers | Keep OTC's existing dependency direction |
| MCP | One command tool sharing the CLI parser, accepting string or argv | Reviewed CLI has no MCP command; `otc-process` is a distinct framed transport | MCP is optional adapter work, not a CLI rewrite |
| Distribution | Self-contained .NET single-file builds, package-manager wrappers | Python wheels and `uv`, optional provider packages | Improve onboarding without coupling providers |
| Agent onboarding | Embedded specialized skills and installation helpers | Guides, examples, CLI help | Add a compact OTC workflow guide |

Sources: [O1-O12], [T1-T11]. A capability existing in one OTC provider does not imply availability in all providers. SDK availability does not imply a corresponding CLI command exists.

## 4. Should OTC Use the OfficeCLI Command Style?

### What makes it effective

The command `officecli set report.xlsx /Sheet1/A1 --prop bold=true` has a small, repeatable structure: action, document, object, properties. The same shape applies to a paragraph or slide shape. The agent can inspect a node, ask for the schema for its element type, and issue a small edit. Batch reuses the same vocabulary. This reduces the number of interaction patterns an agent must learn. [O1, O3, O4]

The most valuable part is not the choice of `set` over `operation`. It is the surrounding feedback loop: discover valid properties, inspect the target, mutate, inspect readback, validate, and render. Copying only short verbs would miss most of the benefit.

### Where the model does not transfer

**`set` is too broad for OTC's whole domain.** A keyed table update, a literal range write, a style change, and a formula write have different requirements. Combining all of them behind a loosely typed property bag makes it easier to activate formulas accidentally or lose the distinction between strings, numbers, dates, nulls, and empty cells.

**Document paths are addresses, not durable identities.** OfficeCLI's README calls paths stable, but `/slide[1]/shape[2]` is positional. Inserting or deleting earlier elements can change the meaning of an index; worksheet/cell coordinates also move under structural edits. OTC's stable worksheet binding and stale-handle protections should remain authoritative. A convenience path, if ever added, must resolve to a typed target and cannot itself prove identity. [O1, O3, T6, T7]

**A selector language would duplicate existing query responsibilities.** OfficeCLI has CSS-like selectors and row conditions. OTC already has table filtering and SQL policy in the SDK. Adding another free-form expression grammar to the CLI would introduce ambiguity around types, escaping, nulls, and execution location. Expose existing SDK query functionality deliberately if needed; do not copy DOM selectors as a shortcut.

**One local file is not a distributed transaction.** OfficeCLI's nonresident batch uses a temporary copy and promotes it when the batch succeeds. OTC must distinguish local publication from a sequence of remote commands where failure can leave partial or unknown effects. `--best-effort` cannot manufacture rollback, compare-and-swap, or idempotency support. [O5, T7, T8]

### Options considered

| Option | Benefit | Cost and risk | Decision |
| --- | --- | --- | --- |
| Replace OTC with global `get/set/add/remove/query` | Short, uniform editing vocabulary | Breaking scripts; table/grid ambiguity; broad semantic redesign | Reject |
| Keep current CLI unchanged | No migration cost | Generic spreadsheet operations stay difficult to discover | Insufficient |
| Add typed shortcuts under `otc spreadsheet` | Shorter common edits; same session/results | Small parser and documentation expansion | Recommend |
| Add another executable with an OfficeCLI-compatible grammar | Familiarity for OfficeCLI users | Two public grammars, compatibility burden, semantic mismatches | Defer unless measured demand exists |
| Embed OfficeCLI as the default XLSX provider | Immediate access to more document objects | New runtime/protocol, preservation and formula requalification | Reject as current default |
| Optional artifact/rendering/export integration | OfficeCLI Word/PowerPoint tables and views; Excelize-only rich XLSX | Version pinning, writer/renderer isolation, artifact validation | Recommend as a separate optional layer; see section 9 |

## 5. A Compatible OTC CLI Direction

### Preserve today's table commands

These are existing forms, not proposed replacements:

```sh
otc inspect --from file:///absolute/path/orders.csv --output-format json
otc read --from file:///absolute/path/orders.csv --output-format jsonl
otc convert --from orders.csv --to orders.xlsx --to-format excel --sheet Orders
otc import --from orders.csv --to gsheets://ID/Orders --if-exists replace
```

Keep `--from` and `--to`: they express direction clearly in a connector product. Keep `--to-format` separate from `--output-format`: destination codec and stdout representation are different choices. Existing CLI import conflict policies also should not be casually equated with SDK create-only materialization semantics. [T1, T3, T4]

Local CSV and workbook endpoints remain bare-path conveniences normalized to canonical `file://` URLs. MaybeSheet remains a canonical HTTPS document URL. Do not introduce the retired local-format or provider URI aliases.

### Add a small ergonomic spreadsheet layer

Current, implemented syntax:

```sh
otc spreadsheet operation --uri file:///absolute/path/report.xlsx \
  --operation range.style --sheet Report \
  --arguments '{"address":"A1:F1","bold":true}'
```

The following was the proposed syntax at research time. The implemented
shortcuts are now available; see the [CLI reference](../user-guide/cli.md) for
the current parser and capability limits:

```sh
otc spreadsheet style --uri file:///absolute/path/report.xlsx \
  --sheet Report --range A1:F1 --bold

otc spreadsheet format --uri file:///absolute/path/report.xlsx \
  --sheet Report --range D4:F38 --pattern '#,##0.00'

otc spreadsheet write --uri file:///absolute/path/report.xlsx \
  --sheet Report --range A1:B2 --values-file values.json

otc spreadsheet worksheet create --uri file:///absolute/path/report.xlsx \
  --sheet Summary
```

`style`, `format`, and `write` should translate into `range.style`, `range.format`, and `range.write` records and enter the same preflight/commit/readback path. Worksheet commands should do the same for their existing operation IDs. Keep `operation` and version `1.0` batches as the complete advanced interface. Shortcuts must not become a second execution engine. [T4, T6]

For booleans, distinguish omission from explicit false; for example, `--bold` and `--no-bold`. Preserve native units for dimensions. For values, use typed JSON matrices, not string guessing. A common option must represent the same contract everywhere; provider-specific extensions should be discoverable and explicit.

A top-level `set` alias is not needed in the first iteration. Optional positional endpoint shorthand can be evaluated later, but an invocation supplying both a positional endpoint and `--uri` must reject conflicting targets rather than guess.

### Add progressive discovery

**Proposed commands:**

```sh
otc help spreadsheet range.style --output-format json
otc capabilities --uri file:///absolute/path/report.xlsx --output-format json
```

Separate static operation documentation from endpoint-specific capability resolution. Help should be offline and side-effect-free. An endpoint capability check may require authentication or metadata I/O; report that explicitly. It must not claim a provider supports a feature merely because the generic operation schema defines it.

Each operation description should include its version, target kind, arguments and types, required fields, exact enums, limits, examples, capability identity, allowed profiles, side-effect category, result schema, and verification behavior. Endpoint results should include provider/version information and supported argument subsets where applicable. Keep secrets out of both errors and discovery output.

OfficeCLI's schemas include aliases, examples, readback descriptions, and `strict` versus `report` enforcement. This is an excellent starting pattern, but OTC should not advertise unsupported or unproven provider features as guaranteed. Add conformance checks connecting advertised capabilities to actual execution and readback. [O4, T5, T7]

### Improve batch transport without changing meaning

OTC currently accepts a command file with this closed envelope:

```json
{"version":"1.0","changes":[
  {"operation_id":"worksheet.create","target_key":"Report","arguments":{}},
  {"operation_id":"range.write","target_key":"Report","arguments":{"address":"A1:B1","values":[["Account","Amount"]]}}
]}
```

Retain this format, its 16 MiB input limit, 10,000-change limit, rejection of duplicate properties/non-finite numbers/unknown envelope keys, and explicit mutation-only semantics. OfficeCLI's bare arrays and mixed read/write command batches need not be copied. [O5, T4]

The useful addition is `--commands -` for explicitly bounded stdin input. Today `_read_json` opens a filesystem path, so `-` is not a stdin alias. Define mutual-exclusion rules before introducing inline/file/stdin alternatives; do not consume protocol stdin in an MCP host. OfficeCLI's source contains a concrete fix for this exact stdin-versus-JSON-RPC conflict. [O5]

## 6. Agent Experience: What to Borrow and What to Change

### Schema-backed help before a larger command inventory

OTC's main CLI reference lists five top-level table commands and omits `spreadsheet`, although the parser already registers it. Spreadsheet documentation exists elsewhere, including `style-read` and `config-read` in source. This is a concrete information architecture gap. First unify the command index, examples, and task guides; then add syntax where measured friction remains. [T3, T4, T7]

OfficeCLI packages help with the executable, so documentation is available offline and matches the installed build. OTC should likewise distribute versioned operation descriptions with the relevant packages, aggregating installed providers at runtime. Avoid a single central schema that imports every optional provider.

### Errors should suggest, not silently choose

OfficeCLI's `ApplySetWithCorrection` can apply an unsupported property under a unique edit-distance-one corrected name. Its set command can also apply supported properties while reporting unsupported ones. This is convenient for interactive document editing but inappropriate as OTC's default financial/data mutation behavior. [O6]

Recommend an error that names the invalid key, provides valid keys or a suggested spelling, and states `commit=not_committed` when preflight prevented dispatch. The user or agent can explicitly retry the corrected request. Do not silently change field names, formulas, worksheet targets, or units.

Preserve OTC's result distinctions: outcome, commit state, verification state, receipts, and safe error details. A boolean `success` is not enough to express a successful write followed by a readback mismatch or unknown remote effects.

There is also a current consistency issue worth documenting before new aliases: table errors use category-specific exit codes in `output.py`, while `run_spreadsheet` returns `5` for caught `OTCError` results. A new shortcut should preserve existing behavior initially; any normalization needs an explicit compatibility decision. OfficeCLI's documented warning exit `2` can mean either some work landed or nothing applied, so copying its exit codes would be particularly confusing for OTC, where `2` already means usage/invalid URI in relevant paths. [O1, O6, T4, T5]

### MCP: shared implementation, deliberate interface

The current OfficeCLI MCP server exposes **one `officecli` tool**, with a `command` argument accepting a string or argv array. It routes through the existing CLI parser rather than defining a separate tool for every document operation. This is more specific than the README's broad statement that operations are available as tools. It avoids duplicate parsing logic and a large eager tool inventory. [O9]

OTC can borrow lazy discovery and shared execution without adopting a shell-string-only API. If an MCP adapter is built, prefer a small discover/inspect/execute surface with typed request objects, or a validated argv array for a compatibility tool. Both should call SDK operations and reuse result contracts. Do not reimplement provider logic or invoke a shell interpreter. Measure schema-context cost and task reliability before choosing one-tool versus several-tool exposure.

`otc-process` is not already an MCP server or a workbook resident daemon: it uses a versioned framed control protocol and verified Arrow artifacts for its own integration scope. Reuse its transport lessons where relevant, not its name as evidence that all workbook commands already have a persistent protocol. [T10]

### Agent guidance and installation

Borrow OfficeCLI's short "discover, inspect, edit, verify" workflow and task-specific examples. OTC guidance should emphasize capability checks, literal versus formula writes, explicit partial effects, canonical URLs, and retained verification expectations.

Do not make an ordinary OTC read/help invocation install skills, modify other applications' configuration, or update its binary. OfficeCLI has automatic installation/update behavior and opt-outs; reproducible data jobs benefit from pinned packages and explicit setup commands. An optional `otc doctor` or explicit agent-setup command is a better future fit. [O10, O11]

## 7. Rendering, Formulas, and Rich Workbook Objects

### Rendering is worth exploring

OfficeCLI's HTML views, PNG screenshots, and watch loop are valuable because layout errors are hard to detect from cell values or styles alone. OTC report workflows would benefit from previewing clipped labels, poorly sized columns, unreadable colors, and misplaced images.

However, the source explicitly says PNG screenshot capture shells out to an available browser; no browser engine is embedded in the binary. Thus "single binary" is accurate for the main distribution but does not mean every visual workflow has zero external prerequisites. The `.csproj` is a self-contained single-file .NET application, not evidence of Native AOT compilation. [O2, O8]

A proposed OTC preview should remain optional, render a committed snapshot or clearly marked staged artifact, and report its backend/version and unsupported features. A preview is not proof of Excel-identical rendering. A clean screenshot is not proof that literal values, formulas, cached values, image bytes, or names survived correctly. Keep physical verification, formula verification, and visual review as separate results.

### Do not replace formula semantics based on feature counts

OfficeCLI advertises an internal engine with 350+ functions and dynamic arrays. This is a substantial product capability, but the count was not independently validated and says little about parity on OTC's workloads. Its schema explicitly distinguishes a cell's `value` property from `formula`; this is useful, but its value handling can infer numeric storage from a string unless a text format/type is selected. [O1, O7]

OTC already has local Excel calculation through Excelize and provider-native formulas elsewhere. The right comparison is not "OfficeCLI calculates; OTC cannot." Evaluate financial/date precision, reference translation, unsupported functions, caches, external references, dynamic arrays, errors, and provider dialects before considering any new backend. Ordinary table/range writes must remain literal under the applicable contract; formula execution remains explicit. [T1, T7]

### Rich objects belong in the optional artifact layer

OfficeCLI's documented and schema-exposed XLSX surface includes charts, pivots, conditional formatting, validation, comments, names, slicers, sparklines, and other objects. OTC's workbook catalog deliberately records many corresponding CRUD operations as unsupported or preservation-only. Existing pivots/cache parts are rejected before general editing until preservation is proven; the strict literal-artifact profile rejects charts and other out-of-profile features. [O1, O7, T7, T8]

This is a real breadth gap for authoring rich Excel reports. The requested rich-XLSX integration should use existing Excelize object APIs exclusively, with images as an initial use case. OfficeCLI's richer XLSX authoring catalog is comparative context, not a feature inventory to expose or a fallback writer. Scope the first release to creation/export and the existing Excelize operations that can be demonstrated; full CRUD parity is not a prerequisite for a truthful export capability. Each advertised operation and preservation claim still needs its own evidence. A screenshot of a chart or a successful save does not establish round-trip fidelity.

## 8. Sessions, Batching, and Performance

OfficeCLI reduces repeated file parsing through resident documents and single-pass batches. Its default resident flush policy adapts between two and ten seconds of idle time; explicit save/close or a flush-each setting changes when disk is updated. Its own reads can observe pending edits before another tool reading the file can. MCP defaults away from auto-spawning residents but still uses an existing resident when one holds the file. [O5, O9, O10]

OTC already buffers workbook changes in an SDK session. Standalone CLI mutations queue one operation and call `write`; a batch commits its queued edits once. The session rejects unsafe concurrent use and freezes after partial/unknown effects pending reconciliation or rebinding. Closing a session does not implicitly write. [T4, T6, T7]

Therefore the first performance improvement is to teach and streamline OTC batches, not to add an invisible background process. A resident service might eventually help high-frequency interactive clients, but it would need explicit lifecycle, persisted-versus-buffered state, concurrency control, credential lifetime, idle/crash recovery, and session identity contracts. Benchmark first.

OfficeCLI's nonresident CLI batch rollback mechanism is visible in source; do not assume identical durability guarantees for every embedding surface. Its public `BatchExecutor.ExecuteBatch` directly executes against a caller-owned handler and does not itself implement the CLI's temporary-copy publication wrapper. Shared verbs and JSON shapes are not by themselves proof of transaction parity. [O5]

No speed ratio or token-saving percentage is claimed in this report. Both tools have batch strategies; equivalent durability and verification must be included in any comparison.

## 9. Integration and Build-versus-Borrow

### 9.1 Expanded scope and architecture

The requested direction is broader than a renderer subprocess: **OTC should export table data into editable Word and PowerPoint tables using OfficeCLI, author rich XLSX artifacts using existing Excelize capabilities only, and expose OfficeCLI's document views and watch loop.** Implement this as adapter and orchestration work. No new OfficeCLI renderer, Excelize object implementation, formula evaluator, or legacy-format converter is in scope.

Recommended responsibility split:

```text
OTC Table / Query / DataFrame
          |
          v
Bounded artifact export request + explicit display/layout options
          |
          +--> OfficeCLI: DOCX/PPTX native tables
          |
          +--> Existing Excelize binding: sole rich-XLSX writer
          |    (images first; other existing APIs only as qualified)
          +--> MaybeSheet sheet-mode: existing provider operations
          |    backed by its Excelize engine; remote receipts/readback
          |
          v
Closed staged file -> independent checks -> final file:// artifact
          |
          +--> OfficeCLI HTML / PNG / semantic views
          +--> Explicit OfficeCLI watch session on a working copy
          +--> Existing exporter/converter, when installed and qualified
```

Keep the OfficeCLI interface in an optional integration package, tentatively `open-table-connector-officecli`, with thin CLI/SDK entry points. The name is a proposal. Keep rich spreadsheet operations in the shared spreadsheet extension, with local-files/Excelize and MaybeSheet sheet-mode adapters, so both work without OfficeCLI installed. Source acquisition stays in OTC; Word/PowerPoint construction stays in OfficeCLI; rich spreadsheet writes use admitted existing Excelize-backed capabilities through the appropriate provider. The artifact orchestration owns format routing, temporary files, writer/renderer isolation, subprocess limits, receipts, and publication. It must not pass remote credentials to OfficeCLI just to render an exported local artifact.

An exported DOCX/PPTX table is an editable presentation of an OTC data snapshot. It is not automatically a connector-backed `Table` with keyed updates, SQL support, or bidirectional synchronization. Refer to the source identity and snapshot in export receipts; do not imply live binding.

### 9.2 Format support: native first, legacy conversion explicitly gated

The requested document families include Word (`doc/docx`), PowerPoint (`ppt/pptx`), and Excel (`xls/xlsx`). OfficeCLI's native handlers support OOXML `.docx`, `.pptx`, and `.xlsx`. The reviewed factory also recognizes macro-enabled OOXML variants, but that is not evidence of legacy binary-format support. [O13]

| Requested format | Recommended integration behavior | Evidence and boundary |
| --- | --- | --- |
| `.docx` | Create an actual editable Word table, in a new document or a supported copied template | OfficeCLI table schema exposes add/set/get and native table children |
| `.pptx` | Create an actual editable PowerPoint table on a selected/new slide | OfficeCLI table schema exposes placement, dimensions, columns and table/cell styling |
| `.xlsx` | Export typed data and create supported rich workbook objects with Excelize only | Existing Python Excelize APIs; OfficeCLI is optional for presentation only |
| `.doc` | Convert a supported legacy input to DOCX through an installed plugin; produce `.doc` only with an independently qualified output converter | The plugin protocol describes `.doc` migration; this does not prove legacy output creation |
| `.ppt` | Gate import/output conversion on an installed, qualified converter | No native binary `.ppt` writer established by this research |
| `.xls` | Gate import/output conversion on an installed, qualified converter | No native binary `.xls` writer established by this research; XLSX support is not XLS support |

The product goal can include all six extensions, but the initial engine-reuse scope can commit only to the three native formats. Advertise individual conversion directions at runtime. Missing conversion support returns an explicit unsupported-capability result; never rename OOXML bytes to a legacy extension or silently substitute a different output format.

OfficeCLI distinguishes `dump-reader` migration, `exporter` conversion, and `format-handler` editing. A legacy input migration may create and edit a sibling native file while leaving the original untouched. OTC should perform that work inside its staging area and return both the actual media type and actual output path. The protocol allows extensions but is not proof that a particular DOC/PPT/XLS exporter is available. [O13]

### 9.3 Native table creation in Word and PowerPoint

The export request should include source data, ordered columns, header policy, display formatting, target document/template, insertion target, and bounded layout options. Native tables are the default; an image of a table is a separately requested presentation mode and does not count as editable-table support.

For **DOCX**, use OfficeCLI's table and cell operations for headers, rows, column widths, alignment, borders, and supported table styles. For **PPTX**, use native table objects with slide selection, position, size, column widths, and supported header/body styling. Read back the created object paths/IDs instead of assuming that the next table is always at a particular positional index. OfficeCLI's DOCX and PPTX schemas provide concrete existing operations for both. [O14]

Important mapping rules:

- Preserve the source snapshot's row/column ordering. Convert values to display strings under explicit rules for numbers, dates, locale, nulls, booleans, and empty strings. Word/PowerPoint presentation cells are not a lossless storage substitute for the original typed table; retain source schema/formatting metadata in the receipt or companion manifest.
- Preserve formulas as explicitly chosen displayed results or formula text; do not promise spreadsheet recalculation inside a Word/PowerPoint table. XLSX formula behavior remains separately controlled.
- Do not encode arbitrary source data by simply joining cells with commas and rows with semicolons. OfficeCLI's table `data` convenience property uses those delimiters. Prefer existing per-cell properties/operations inside JSON batches and verify commas, semicolons, quotes, newlines, Unicode, and leading zeros. JSON encoding alone does not escape a delimiter interpreted inside a property value. [O14]
- Use existing engine layout primitives. For large tables, require an explicit bounded split policy, caller-supplied row chunks, or a qualified existing template flow. Do not introduce a new pagination or auto-layout engine. Reject overflow that cannot be handled with existing functionality rather than truncating rows silently.
- Separate creation in a new artifact from insertion into a copied template. Validate preservation of supported template content; avoid in-place edits to a user's only copy during export.

Acceptance should include editable native-table structure, expected dimensions, displayed cell content, header treatment, placement, and preservation of unrelated template content. Physical/content checks and screenshots address different failures.

### 9.4 Views, PNG screenshots, and the watch loop

Expose OfficeCLI's existing `view` modes through the optional integration rather than writing another renderer. Include HTML, screenshots, and the applicable text/outline/stats/issues modes. Additional outputs such as SVG or PDF should be advertised only for the formats/backends/plugins actually available; PDF is not assumed to be built into every installation. [O1, O8, O13]

| Surface | Integration behavior | Required qualification |
| --- | --- | --- |
| HTML view | Produce a local HTML artifact with explicit destination; optionally open it | Supported objects, fonts/assets, and documented rendering limitations |
| PNG screenshot | Capture selected supported pages/slides/sheets/ranges through existing OfficeCLI selectors | External browser available; actual selection semantics checked per format; nonblank output |
| Outline/text/stats | Bounded structural/content inspection | Mode supported for the format; output limits retained |
| Issues/validation | Return engine diagnostics separately from OTC verification | No claim that a clean engine result proves full semantic fidelity |
| Watch | Start an explicit local preview session, return URL/session metadata, expose stop/status | Port ownership, process lifetime, update behavior, and writable working-copy semantics |
| Other exports | Delegate to an existing installed exporter | Exact input/output pair and runtime availability verified |

**Watch is not automatically a passive file watcher.** The inspected command description says it refreshes when OfficeCLI modifies a document and that external edits are not detected. The README also describes interactive XLSX cell edits and chart repositioning. Therefore the integration must not promise that an Excelize write automatically refreshes a running OfficeCLI preview, or that the stock preview is read-only. [O1, O15]

Use two explicit workflows:

1. **Review a delivered snapshot:** render HTML/PNG from a closed, committed file, with its hash recorded. Any watch session operates on a disposable working copy unless a genuinely read-only mode is verified.
2. **Interactive authoring:** for DOCX/PPTX, OfficeCLI owns a working copy and its resident/watch session; OfficeCLI edits drive the live loop. For XLSX, Excelize alone edits the authoritative workbook. After Excelize saves and closes, regenerate the preview copy and reopen/restart OfficeCLI's preview, since external edits are not detected. This restart boundary uses existing functionality and avoids inventing an engine notification feature.

For XLSX watch, disable editing only if an existing read-only facility can be verified. Otherwise expose the stock watch UI only on a disposable preview copy and clearly identify that edits there are not saved back or accepted as output. Never publish an OfficeCLI-edited preview copy as the Excelize artifact. Verify the source hash remains unchanged. If a strictly read-only live UI is required and unavailable, report that limitation and use static HTML/PNG until an existing backend mode satisfies it; building a new watch engine is outside scope.

A watch session should return its actual localhost URL, process/session ID, working-copy path, and persistence state. Stopping preview must be distinguished from exporting/publishing a document. The adapter should never equate a refreshed browser view with a flushed file. Before delivery, explicitly save/close the authoritative writer, run required checks against its on-disk artifact, and publish. Discard XLSX preview-copy edits.

### 9.5 Rich spreadsheets: local XLSX and MaybeSheet sheet-mode

**Interpretation of "no new enhancement":** integration wrappers, capability mapping, serialization, and qualification tests are in scope; new upstream features, new object types, formula-engine changes, or a new renderer are out of scope. Rich spreadsheet operations reuse existing Excelize capabilities through the local Python binding or MaybeSheet's existing sheet-mode API/CLI. An unavailable provider operation remains unsupported; do not route it to OfficeCLI or add a new backend feature to close the gap.

**MaybeSheet sheet-mode is a first-class target, not just a source for local XLSX export.** The requested scope is one shared rich-sheet operation model with two execution providers. The shared Excelize backend is supplied architectural context from the user; this OTC checkout verifies the MaybeSheet adapter/protocol, not MaybeSheet's internal server implementation or deployed Excelize version. Distinguish that architectural premise from measured API parity. [T13]

OTC pins `excelize` to `>=0.1,<0.2`; the inspected lockfile resolves `0.1.0`. Runtime introspection of that installed Python binding confirmed the methods below. This is stronger than assuming that every feature in upstream Go Excelize is available through Python, but method presence is not yet an artifact-correctness test. Current OTC source uses Excelize through `excel_formula.py` for calculation; the general workbook/image path uses openpyxl. The proposed image/object integration would therefore be new OTC adapter wiring, not an already implemented OTC Excelize image path. [T8, T12]

| Object/function | Existing methods observed on the installed Excelize file object | Initial integration policy |
| --- | --- | --- |
| Images | `add_picture`, `add_picture_from_bytes`, `get_pictures`, `delete_picture` | First admitted Excelize object use case; qualify bytes, anchors, size, crop/placement options actually exposed |
| Charts | `add_chart`, `add_chart_sheet`, `delete_chart` | Use only supported chart types/options; preserve formulas, caches, and unrelated objects in fixtures |
| Shapes | `add_shape` | Creation where existing options suffice; do not imply unobserved read/update/delete parity |
| Native tables | `add_table`, `get_tables` | Distinguish XLSX table objects from cell ranges and DOCX/PPTX presentation tables |
| Pivots | `add_pivot_table`, `get_pivot_tables` | Gate exact supported options and preservation; current OTC general writer rejects pivot parts |
| Comments | `add_comment`, `get_comments`, `delete_comment` | Admit only qualified existing comment model |
| Data validation | `add_data_validation`, `get_data_validations` | Existing rule types only; preserve reference behavior |
| Conditional formatting | `new_conditional_style`, `set_conditional_format`, `unset_conditional_format` | Existing style/rule options only; independently inspect serialized output |

The method inventory above describes the **local Python binding**, not MaybeSheet's transport. For each corresponding operation, the MaybeSheet adapter must resolve an already exposed API/CLI command and verify its actual arguments, results, and readback. Sharing an engine supports reuse of semantics and fixtures; it does not make a local method remotely callable.

#### Provider mapping and current evidence

| Concern | Local XLSX | MaybeSheet sheet-mode |
| --- | --- | --- |
| Target | Canonical `file://` workbook | Canonical HTTPS document URL plus stable Sheet-engine worksheet identity |
| Execution | Existing Excelize Python APIs | Existing authenticated MaybeSheet API/CLI operations over its backend |
| Shared model | Typed range values, layout, images and admitted rich objects | Same operation names and typed requests where semantics match |
| Images now | Binding exposes add/read/delete methods; proposed rich export path needs qualification | OTC adapter already advertises insert/list/read/delete; bounded PNG/JPEG, cell anchors, stable picture IDs |
| Image options | Qualify the binding's existing sizing/placement options | Current adapter rejects explicit sizing because a tested single-command contract is absent |
| Other objects | Existing methods listed above, individually qualified | Admit only existing exposed commands with evidence; charts/pivots/etc. are not proven by local method presence |
| Commit | Closed staged file and verified publication | Provider commit receipts; multi-command writes require explicit partial-effects opt-in under the current contract |
| Concurrency | Existing local coordination/conflict checks | Do not invent CAS/idempotency; current workbook adapter rejects those guarantees |
| Verification | Independent file/object readback | Fresh provider readback and, where available, independent exported-XLSX inspection |
| Preview | Disposable copy of the committed workbook | Disposable exported snapshot of the remote sheet/workbook |

The current MaybeSheet adapter checks Sheet-engine topology and refuses Base-engine mutation. Its image insertion accepts PNG/JPEG bytes up to 8 MiB and requires a cell anchor; deletion requires a stable `picture_id`. Those are provider restrictions, not limits to impose on every Excelize consumer. Retain provider-specific capability/option discovery rather than reducing both providers to the smallest common feature set. [T13]

Define a capability matrix by provider, operation, option subset, backend/transport version when available, and verification coverage. Reuse contract fixtures for common semantics, with provider-specific fixtures for IDs, units, transport encoding, failures, and readback. If MaybeSheet already exposes an operation that OTC does not yet wrap, adding the OTC mapping is in scope. If MaybeSheet exposes no route to it, record the gap; adding a new server endpoint or new Excelize functionality is outside this proposal's no-enhancement scope.

MaybeSheet Base mode is excluded from these rich-sheet mutations, even when Base and Sheet worksheets share a document. Preserve Base worksheets and existing identities. Use the SDK's worksheet/grid binding for objects; do not model an image or arbitrary worksheet as a `Table`.

#### Local and remote execution

Excelize is the sole authoring engine for the local rich-XLSX path; MaybeSheet's Excelize-backed sheet-mode provider owns remote mutations. Record the provider/transport version and exact admitted operations in receipts, and record backend version only when actually exposed. OfficeCLI may inspect/render an exported snapshot or disposable preview copy, but must not create, edit, recalculate, or resave the authoritative spreadsheet. There is no second-writer fallback.

Local pipeline:

1. Resolve an OTC data snapshot and validate a recipe against the installed Excelize capability inventory.
2. Create or open a staging workbook with Excelize; apply only supported data, layout, formula, and object operations.
3. Save and close Excelize. Independently verify the resulting content, image bytes/anchors, supported object definitions, and template preservation.
4. Optionally render a disposable copy through OfficeCLI. Keep renderer diagnostics and visual review separate from semantic verification; verify the authoritative file hash is unchanged.
5. Publish the verified Excelize-produced file. Discard preview-copy mutations and never use them as an export result.

MaybeSheet pipeline:

1. Resolve the canonical HTTPS endpoint and stable Sheet-engine worksheet binding; preflight the requested operations and options against that provider's existing surface.
2. Dispatch through the authenticated MaybeSheet adapter. Retain current partial-effects opt-in, commit/uncertainty reporting, and reconciliation behavior; a shared Excelize backend does not create a remote transaction.
3. Read values/object metadata back through MaybeSheet and retain created object IDs. Use an existing XLSX export operation for independent physical inspection when available; otherwise report the actual narrower verification coverage.
4. For OfficeCLI views, render a disposable exported snapshot. Associate it with an observed revision when available, or record export time/hash and the lack of revision consistency. Do not upload an edited preview back as a substitute for provider operations.
5. Refresh a remote watch preview by explicitly re-exporting and restarting/reloading through supported mechanisms. OfficeCLI does not automatically observe remote MaybeSheet edits; use an existing event mechanism or explicit/polled refresh only when requested. Report snapshot freshness.

Do not pass a rich artifact back through the current OTC general workbook writer when it contains unsupported parts such as pivots. Use a distinct Excelize artifact-export path and narrowly scoped verification profile; retain the existing conservative table/workbook path unchanged. Independent readers can inspect the result without becoming writers.

Describe support as tuples of Excelize binding version, operation, options, and tested preservation scope. Presence of `add_chart` does not prove every chart type/options combination is supported or correctly rendered by OfficeCLI. Missing render support is a presentation limitation, not a reason to change the authoritative workbook with another engine. Excelize does not handle Word/PowerPoint tables.

### 9.6 Public surface and result contract

The following section records the original proposed OTC commands. The released
subset uses the separate `artifact` namespace and is documented in the [CLI
reference](../user-guide/cli.md); renderer-dependent view/watch paths remain
capability-gated:

```sh
# Export an OTC data snapshot as editable native tables.
otc artifact export --from orders.csv --to file:///absolute/path/report.docx \
  --engine officecli --spec word-table.json
otc artifact export --from orders.csv --to file:///absolute/path/deck.pptx \
  --engine officecli --spec slide-table.json

# Rich workbook recipe: existing Excelize APIs only.
otc artifact export --from orders.csv --to file:///absolute/path/report.xlsx \
  --engine excelize --spec rich-workbook.json

# Apply the shared rich-sheet recipe through MaybeSheet's existing provider.
otc spreadsheet apply \
  --uri https://www.maybe.ai/docs/spreadsheets/d/DOCUMENT \
  --sheet Report --spec rich-workbook.json --allow-partial

# Views and preview use existing OfficeCLI functionality.
otc artifact view --uri file:///absolute/path/report.docx --mode html \
  --to file:///absolute/path/report.html
otc artifact view --uri file:///absolute/path/deck.pptx --mode screenshot \
  --page 1 --to file:///absolute/path/slide-1.png
otc artifact watch --uri file:///absolute/path/report.xlsx --working-copy
```

`--spec` would be a bounded, versioned integration recipe, not arbitrary shell commands. It references source columns, native-table placement, supported formatting, and qualified object operations. Engine choice is format/provider-scoped: OfficeCLI for DOCX/PPTX tables, local Excelize for rich XLSX, and MaybeSheet's existing sheet-mode provider for remote rich-sheet operations. A shared spreadsheet recipe is portable only over each provider's admitted capabilities and options; the proposed `spreadsheet apply` compiles into the existing session operations and preserves their commit policy. No spreadsheet recipe can route an object mutation to OfficeCLI. Preview commands select OfficeCLI independently of the authoring engine. The schema and exact CLI naming require implementation design, but the core export and verification boundaries do not.

Results should record source snapshot identity, destination/media type, engine versions, operation/object mapping, output hash, display-format policy, known omissions, verification coverage, and commit state. Preview results additionally record renderer/browser versions and the rendered artifact hash. Watch results distinguish buffered edits, saved working copy, and published output. Missing fonts, unsupported objects, failed conversion, and unavailable browser are explicit diagnostics, not successful full-fidelity exports.

### 9.7 Delivery gates and sequence

| Stage | Deliverable using existing engine features | Release gate |
| --- | --- | --- |
| A | Optional adapter discovery and installed-engine capability inventory | OTC works without OfficeCLI; unsupported versions/operations reject before mutation |
| B | OfficeCLI DOCX/PPTX native table export and Excelize XLSX export | Typed-source/display mapping fixtures, native-table readback, template preservation |
| C | HTML/PNG/semantic views and explicit watch lifecycle | Nonblank renders, correct selections, source unchanged in snapshot workflow; restart after external writes demonstrated |
| D | Excelize-backed rich operations for local XLSX and MaybeSheet sheet-mode; images first | Per-provider capability/option gates, object readback, template/Base-sheet preservation, honest remote commit states; no OfficeCLI writes |
| E | Optional legacy DOC/PPT/XLS conversion using existing installed converters | Exact conversion direction advertised; fidelity/loss report; actual legacy output independently identified |

Stages B-D are the recommended integration scope. Stage E remains conditional on existing converter availability, consistent with the no-engine-enhancement constraint. Full arbitrary Word/PowerPoint editing, bidirectional table synchronization, automatic layout invention, and new Excelize features are excluded.

### 9.8 Build-versus-borrow decision

| Strategy | Appropriate use | Preconditions | Recommendation |
| --- | --- | --- | --- |
| Learn from design only | Help, recipes, error suggestions, batch ergonomics | Adapt to OTC contracts and tests | Start now |
| Optional OfficeCLI artifact adapter | Native DOCX/PPTX tables from OTC data | Typed/display mapping, pinned engine, staged publication and independent checks | Recommend |
| Optional renderer/watch integration | HTML/PNG/semantic views and explicit live authoring sessions | Browser/font checks; working copies; flush and restart boundaries | Include in the optional adapter |
| Shared Excelize-backed rich-sheet operations | Local XLSX and MaybeSheet sheet-mode data, images and existing exposed object operations | Provider-specific dispatch, capability/option qualification, preservation, readback and commit semantics | Both providers in scope; no engine/server enhancements |
| Optional legacy conversion | DOC/PPT/XLS import/output through existing tools | Installed converter, exact direction and fidelity qualification | Conditional support; never extension renaming |
| Copy implementation | Specific reusable algorithms | Apache-2.0 notices plus third-party dependency review; language integration cost | Case by case |
| Mandatory OfficeCLI backend | All OTC XLSX operations | Requalification of existing contracts and deployment footprint | Not justified |

OfficeCLI is Apache-2.0 licensed and includes a NOTICE and third-party notices. That supports reuse subject to the applicable obligations, but does not remove the engineering cost of integrating C# code into a Python provider architecture. An optional process boundary is generally a more contained experiment than porting a document engine. [O12]

For artifact export, operate on a staging copy first. Save and close the format's authoritative writer before independent inspection or rendering. Before publication, validate the export intent. Never treat an engine acknowledgment or OfficeCLI schema validation alone as an OTC verified receipt.

## 10. Prioritized Roadmap

These are relative effort/risk assessments, not calendar estimates or implementation commitments.

| Priority | Work | Expected return | Relative effort | Acceptance condition |
| --- | --- | --- | --- | --- |
| P0 | Repair CLI reference/discovery gap | Existing functionality becomes findable | Small | Main index covers every registered command/action; examples run |
| P0 | Operation help schema and capability inspection design | Fewer guessed arguments and unsupported attempts | Medium | Static schema distinct from live capability; provider claims exercised |
| P1 | Typed `style`, `format`, `write`, worksheet shortcuts | Faster common report edits | Medium | Equivalent normalized operations and receipts to existing path |
| P1 | Bounded stdin batch support | Easier agent/program pipelines | Small-medium | Same limits/validation as files; no protocol stdin consumption |
| P1 | Safe error suggestions and documented exit semantics | Reliable recovery without silent mutation | Medium | Invalid requests do not dispatch; secrets stay redacted |
| P1 | Task-oriented agent guide | Better use of existing capabilities | Small | Version-aligned examples, canonical URLs, clear verification steps |
| P2 | Optional DOCX/PPTX native table export | Editable document/presentation output from OTC data | Medium-large | Native structure and displayed values verified; template content preserved |
| P2 | OfficeCLI HTML/PNG/semantic views and watch | Visual review and iterative authoring | Medium-large | Snapshot source untouched; watch lifecycle and external-writer restart explicit |
| P2 | Rich local XLSX and MaybeSheet sheet-mode using existing Excelize-backed capabilities | Shared image/object operations without engine development | Large | Both provider mappings qualified; remote partial effects preserved; OfficeCLI never writes the spreadsheet |
| P2 | MCP discovery/execution adapter | Access from clients without shell tools | Medium | Same SDK behavior/results; optional dependencies preserved |
| P2 | Replayable supported layout recipes | Repeated report consistency | Medium | Round-trip only advertised subset; values/formulas not silently altered |
| P3 | Resident service | Potential interactive latency benefit | Large | Benchmarks justify lifecycle and concurrency complexity |
| P3 | Existing legacy DOC/PPT/XLS converters | Compatibility with binary Office formats | Converter-dependent | Exact installed conversion directions and output fidelity qualified |

Prefer layout recipes over promising an immediate whole-workbook `dump` equivalent. OfficeCLI's replayable document dump is attractive, but OTC cannot truthfully replay resources that its public catalog cannot create. Start with a versioned supported layout subset, explicit omissions, and dependency ordering.

Implementation ownership should stay narrow: CLI parsing/help in `packages/cli`; SDK orchestration in `packages/sdk`; neutral operation schemas alongside the appropriate contract/extension; physical support in provider packages. The proposed OfficeCLI artifact adapter is optional and must not introduce mandatory imports into existing table providers. Generate or validate docs from those definitions. Keep optional providers removable. [T2]

## 11. Evaluation Plan Before Committing to a New Grammar

Run the same tasks against current OTC and a thin proposed shortcut prototype. OfficeCLI should participate where it actually addresses the workload, principally local XLSX. Do not score it as failing PostgreSQL or cloud connector workflows outside its stated scope.

| Task | What it tests |
| --- | --- |
| Inspect an unfamiliar workbook and discover writable style properties | Help quality and capability accuracy |
| Create a small typed table with `"00123"`, numeric values, nulls and empty strings | Type preservation, literal semantics |
| Style headers, accounting formats, widths and freeze panes | Common command ergonomics and native units |
| Apply 100 edits to one workbook | Cold invocation, batch, verification and serialization costs |
| Use an invalid property halfway through a batch | Preflight, rollback/partial effects, error recovery |
| Modify a workbook concurrently after opening | Stale binding and conflict behavior |
| Write explicit formulas and read cached/calculated values | Dialect, evaluator and cache distinctions |
| Edit a workbook containing charts, names, validation and pivots | Preservation and explicit unsupported behavior |
| Perform the closest supported remote worksheet workflow | Provider restrictions and partial effects |
| Reopen the delivered artifact in an independent reader | Durability and semantic readback |
| Export the same source to native DOCX and PPTX tables | Editable structure, delimiter-safe content, display formatting, bounded layout |
| Create rich XLSX with Excelize, then render a copy through OfficeCLI | Image/object correctness, rendering limitations, unchanged authoritative file |
| Update an XLSX through Excelize while its disposable preview is watched | Explicit preview restart; preview-copy edits never reach the output |
| Run shared image/object fixtures against local XLSX and MaybeSheet sheet-mode | Common semantics, provider option differences, stable remote IDs and independent readback |
| Request a local-supported object absent from MaybeSheet's exposed surface | Preflight rejection without mutation or OfficeCLI fallback |
| Mutate a Sheet worksheet beside a Base worksheet, then export a preview | Base preservation, remote commit evidence and preview freshness |
| Request legacy DOC/PPT/XLS output with and without a converter | Accurate capability discovery, output format and explicit rejection |

Measure first-attempt success, help/retry calls, input/output tokens, wall time, peak memory, process startups, bytes emitted, and final artifact correctness. Include process exit, flush, publication, and required verification in latency. Separate failures from unsupported workloads. Record pinned versions, OS, provider configuration, fixtures, seeds, and cold/warm runs.

Suggested gates for OTC adoption: zero regressions in value/formula/preservation fixtures; no weakening of unsupported-capability rejection; legacy scripts unchanged; and a meaningful measured reduction in agent retries or task time. A target such as 20% fewer interaction steps can be a product goal, but it is not a result established by this research.

## 12. Validation Performed and Remaining Questions

The successful focused run used:

```sh
UV_PROJECT_ENVIRONMENT=/tmp/otc-officecli-research-venv \
  uv run --all-packages --frozen python -m pytest \
  packages/cli/tests/test_spreadsheet_commands.py \
  packages/cli/tests/test_commands.py \
  packages/cli/tests/test_cli_e2e.py -q --tb=short
```

Result: **37 passed in 15.29s**, Python 3.13.13. Coverage includes batch dry-run/commit/read, rejection before file creation, retained-intent verification, table result rendering, safe errors, format selection, and CLI/module entry points. Existing environment first attempt: 22 passed, 15 failed; the fresh frozen workspace resolved that run's failures without code changes. No cloud credentials or live remote mutations were used.

The OfficeCLI runtime and public test suite were not run. No native Excel/LibreOffice visual comparison, adversarial formula corpus, transaction fault injection across tools, or performance benchmark was executed. OTC's historical readiness ledger is useful context but its older full-suite results are not represented as freshly rerun evidence. The focused tests do not prove all workbook/session/conformance guarantees.

For the expanded integration research, the installed `excelize 0.1.0` Python binding was imported, a new in-memory workbook was opened, its existing image/object method names were inspected, and it was closed. No image/chart/pivot artifact round-trip or Excelize-to-OfficeCLI rendering pipeline was tested. OfficeCLI's native table schemas, handler factory, plugin protocol, and watch command source were additionally reviewed. The expanded integration remains a recommendation, not an implemented or certified feature.

For the MaybeSheet scope expansion, the current OTC adapter's advertised operations, Sheet-engine checks, image validation, and commit restrictions were source-reviewed. No live MaybeSheet calls or server-side Excelize inspection were performed. Shared backend architecture is user-provided context; object-by-object remote parity remains to be qualified.

Questions to settle during implementation design:

- Which spreadsheet tasks account for most real CLI usage: literal exports, financial layout, cloud updates, or rich report authoring?
- Can operation argument schemas be extracted from current validators, or is a small shared declarative definition needed to prevent help/dispatch drift?
- Which capability checks require authenticated endpoint I/O, and how should offline help represent unknown provider support?
- Should spreadsheet exit-code normalization be versioned separately from ergonomic additions?
- Which renderer offers acceptable XLSX visual fidelity for the actual report corpus, at an acceptable installation cost?

These questions do not block the central recommendation: improve discovery and add compatible, typed spreadsheet shortcuts before considering a global grammar rewrite or a new engine.

## 13. Source Index

OfficeCLI links below are immutable revision references. OTC links are relative to this report and describe the OTC revision recorded in section 2.

- **O1:** [README: commands, advertised features, output, SDKs](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/README.md).
- **O2:** [.NET project and dependencies](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/src/officecli/officecli.csproj).
- **O3:** [Shared document-handler interface](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/src/officecli/Core/IDocumentHandler.cs).
- **O4:** [Schema design](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/schemas/README.md), [help command](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/src/officecli/CommandBuilder.Help.cs).
- **O5:** [Batch parsing, dispatch and atomic publication](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/src/officecli/CommandBuilder.Batch.cs), [in-process batch executor](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/src/officecli/Core/BatchExecutor.cs).
- **O6:** [Set command](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/src/officecli/CommandBuilder.Set.cs), [shared property correction](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/src/officecli/CommandBuilder.cs), [output formatting](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/src/officecli/Core/OutputFormatter.cs).
- **O7:** [XLSX cell schema](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/schemas/help/xlsx/cell.json), [XLSX schemas](https://github.com/iOfficeAI/OfficeCLI/tree/8df116451aafc9d192787d623514de0c52ea2dc9/schemas/help/xlsx).
- **O8:** [External-browser screenshot adapter](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/src/officecli/Core/HtmlScreenshot.cs).
- **O9:** [MCP tool definition and shared-parser execution](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/src/officecli/McpServer.cs).
- **O10:** [Resident flush policy](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/src/officecli/Core/ResidentFlushPolicy.cs), [resident execution](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/src/officecli/ResidentServer.cs), [agent guide, read as research material](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/SKILL.md).
- **O11:** [Startup behavior](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/src/officecli/Program.cs), [update handling](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/src/officecli/Core/UpdateChecker.cs).
- **O12:** [Solution/test-project reference](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/officecli.slnx), [build/smoke workflow](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/.github/workflows/build.yml), [SDKs](https://github.com/iOfficeAI/OfficeCLI/tree/8df116451aafc9d192787d623514de0c52ea2dc9/sdk), [license](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/LICENSE), [notices](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/THIRD-PARTY-NOTICES.txt).
- **O13:** [Native handler selection and foreign-format routing](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/src/officecli/Handlers/DocumentHandlerFactory.cs), [plugin kinds and conversion directions](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/plugins/plugin-protocol.md).
- **O14:** [DOCX native-table schema](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/schemas/help/docx/table.json), [PPTX native-table schema](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/schemas/help/pptx/table.json).
- **O15:** [Watch command and external-edit limitation](https://github.com/iOfficeAI/OfficeCLI/blob/8df116451aafc9d192787d623514de0c52ea2dc9/src/officecli/CommandBuilder.Watch.cs).
- **T1:** [OTC README](../../README.md).
- **T2:** [Package boundaries](../package-boundaries.md).
- **T3:** [CLI user reference](../user-guide/cli.md), [parser](../../packages/cli/src/open_table_connector/cli/__main__.py).
- **T4:** [Spreadsheet CLI parser and dispatch](../../packages/cli/src/open_table_connector/cli/spreadsheet_commands.py), [table pipeline and compatibility paths](../../packages/cli/src/open_table_connector/cli/pipeline.py).
- **T5:** [Output and exit-code handling](../../packages/cli/src/open_table_connector/cli/output.py), [connector listing](../../packages/cli/src/open_table_connector/cli/commands.py).
- **T6:** [SDK workbook APIs](../../packages/sdk/src/open_table_connector/sdk/workbook.py), [session state machine](../../packages/spreadsheets/src/open_table_connector/spreadsheets/_session.py), [capability identities](../../packages/spreadsheets/src/open_table_connector/spreadsheets/capabilities.py).
- **T7:** [Spreadsheet operations and support catalog](../user-guide/spreadsheet-operations.md), [historical readiness evidence](../spreadsheet-readiness.md).
- **T8:** [Local provider and verified publication](../../packages/local_files/src/open_table_connector/local_files/spreadsheet_workbook.py), [independent strict verifier](../../packages/local_files/src/open_table_connector/local_files/spreadsheet_verify.py).
- **T9:** [CLI spreadsheet tests](../../packages/cli/tests/test_spreadsheet_commands.py), [CLI command tests](../../packages/cli/tests/test_commands.py), [CLI end-to-end tests](../../packages/cli/tests/test_cli_e2e.py).
- **T10:** [Process transport](../../packages/process/README.md).
- **T11:** [Session tests](../../packages/spreadsheets/tests/test_session.py), [provider preservation/conflict tests](../../packages/local_files/tests/test_spreadsheet_provider.py), [physical verification tests](../../packages/local_files/tests/test_spreadsheet_verify.py).
- **T12:** [Pinned Excelize dependency](../../packages/local_files/pyproject.toml), [resolved binding version](../../uv.lock), [current Excelize calculation integration](../../packages/local_files/src/open_table_connector/local_files/excel_formula.py). Existing object API names in section 9.5 were verified through runtime introspection of the resolved Python binding, not inferred from the Go API.
- **T13:** [MaybeSheet spreadsheet adapter: capabilities, Sheet-engine guards, images, preflight and commit](../../packages/maybe_sheet/src/open_table_connector/maybe_sheet/spreadsheet.py), [provider guide](../../packages/maybe_sheet/README.md). These establish OTC's exposed transport behavior, not the implementation/version of the remote Excelize backend.
