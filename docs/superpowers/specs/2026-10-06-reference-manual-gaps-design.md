# OTC Reference Manuals and Gap-Closure Specification

Date: 2026-10-06 (Asia/Shanghai).
Status: ready for implementation planning; this specification closes the gaps
found while preparing complete CLI and SDK manuals.
Related implementation: [P0-P2 acceptance](../../reports/2026-10-06-p0-p2-acceptance.md).

## Objective

Deliver complete, executable reference manuals for the CLI, SDK, spreadsheet
contracts, providers, artifacts, MCP, and process runtime. Examples must either
run against a local provider or state the exact provider, credential, and
runtime prerequisites. Generated inventories must stay synchronized with the
parser and public exports.

The documentation work exposed four behavioral gaps that must be closed before
the manuals can claim a complete workflow:

| Gap | Current evidence | Required result |
| --- | --- | --- |
| CLI spreadsheet shortcuts | `spreadsheet style/format/write/worksheet` compile a change but `run_spreadsheet` only writes for `batch` and `operation`; shortcut output can report success without committing | Every shortcut enters the same buffered session write path and returns its real commit/verification result |
| Recipe export | `spreadsheet recipe export` is parsed as `worksheet_action` because both positionals share the parser; `export_recipe` accepts selectors without observing the target | `recipe export` parses unambiguously and exports only fresh, target-backed observations |
| SDK generic dispatcher | `execute_operation` creates a workbook but does not close or commit the session for range mutations | Generic spreadsheet operations either commit according to `ExecutionOptions` or return an explicit planned/read-only result, with no leaked session |
| MCP host execution and artifact runtime | The standalone MCP server can discover but returns configuration errors for inspect/execute; OfficeCLI render/view/watch remains unavailable without a runtime | Host wiring is explicit and fail-closed; view/watch report qualified runtime state, never synthetic success |

These gaps are part of the documentation acceptance surface because an example
that parses but does not persist or execute is misleading.

## Constraints

- Local workbook and CSV paths use canonical `file://` URLs. MaybeSheet uses its
  canonical HTTPS document URL.
- Rich XLSX authoring uses the existing Excelize-backed provider only. OfficeCLI
  never authors, recalculates, or resaves authoritative XLSX.
- Existing `OperationResult`, receipts, commit states, verification states,
  error codes, and exit-code mappings remain authoritative.
- Unsupported providers and unqualified object families fail closed before
  dispatch. Remote multi-command operations retain partial/unknown effects.
- Documentation generation must not import optional providers as a requirement
  for core help or SDK imports.
- The generated API/CLI/schema references are derived artifacts, not a second
  hand-maintained contract.

## User-facing manuals

Create and maintain these linked documents:

1. `docs/user-guide/cli-manual.md` — installation, command model, routing,
   complete command examples, input limits, output formats, error/exit behavior,
   spreadsheet sessions, recipes, artifact export, and MCP invocation.
2. `docs/user-guide/sdk-manual.md` — client construction, registry/configuration,
   tables, transactions, SQL, formulas, workbook/layout sessions, snapshots,
   recipes, artifacts, temporal storage, results, and client affinity.
3. `docs/user-guide/components.md` — component/package matrix, provider routes,
   optional dependencies, capabilities, runtime prerequisites, and live-vs-
   recorded evidence.
4. `docs/reference/cli-options.md` — generated parser inventory.
5. `docs/reference/api-inventory.md` — generated public-export and signature
   inventory.
6. `docs/reference/spreadsheet-schemas.md` — generated operation descriptors and
   JSON schemas.

The existing short pages remain entry points. Each must link to the relevant
manual rather than duplicate a partial API description. README files should
contain a short orientation and link to the manuals; package READMEs must state
their install name, public exports, provider boundary, and a smallest working
example where the package owns one.

## Manual content requirements

### CLI manual

Document every parser command: `list`, `inspect`, `read`, `convert`, `import`,
`help`, `capabilities`, `spreadsheet`, and `artifact`. For each command include
required/optional arguments, defaults, output formats, exit behavior, and one
local example. Explain that `help` is static while `capabilities` can require
live routing/authentication.

Document these complete flows:

```console
otc inspect --from orders.csv --output-format json
otc read --from file:///absolute/orders.csv --output-format table
otc convert --from orders.csv --to orders.jsonl --output-format jsonl
otc import --from orders.csv --to gsheets://ID/Orders --if-exists append
otc help spreadsheet range.style --output-format json
otc capabilities --uri file:///absolute/report.xlsx --output-format json
```

The spreadsheet section must include batch envelopes, stdin/file bounds,
dry-run, `--allow-partial`, expected revisions, idempotency, failure retention,
literal/general/rich profiles, style/format/write/worksheet shortcuts, images,
verification, and recipe application. A shortcut is documented as equivalent to
one buffered operation followed by the same `write()` call as `operation`.

Artifact documentation must distinguish the currently usable DOCX/PPTX export
from renderer-gated `view` and `watch`. It must state that the current CLI
returns `unsupported_capability` for unconfigured renderer paths.

### SDK manual

Use a single local-files setup fixture in all examples:

```python
from open_table_connector.local_files import LocalFilesConnector
from open_table_connector.sdk import Client, ConnectorRegistry

client = Client(registry=ConnectorRegistry([LocalFilesConnector()]))
```

Cover the following public lifecycle and result rules:

- `Client.from_config`, `Client.open`, `Client.materialize`, `Client.collect`,
  `Client.sql`, `Client.native_sql`, `Client.formulas`, `Client.workbook`,
  `Client.artifacts`, `Client.close`;
- `Table.inspect/read/read_page/insert/update/delete/drop/transaction/layout`
  and create-only materialization;
- `OperationResult.require_value`, `.with_results`, `.to_wire`, `Outcome`,
  `CommitState`, `VerificationState`, `OTCError`, receipts, warnings, and
  reconciliation references;
- formula target kinds, explicit `FormulaExpression`, provider-native dialects,
  calculated-value freshness, and recalculation limits;
- workbook profiles, staged writes, close-without-save, stale worksheet
  generations, image insertion/read/list/delete, independent verification, and
  retained intent;
- recipe export/apply parsing, the `otc.spreadsheet-recipe/1.0` envelope, dry
  run, forbidden value/formula/assets fields, and qualified operation subsets;
- snapshots and artifact view/watch lifecycle, including disposable-copy
  semantics; and
- temporal scan/latest/as-of/aggregate/gap-fill, Temporal SQL restrictions,
  managed stage/commit/readback/abort, leases, idempotency, and bounds.

Every mutating example must show the commit and verification states, then reopen
or independently inspect the destination. Every failed or uncertain example
must show the error code and the reconciliation rule.

### Component manual

Include a matrix with install package, entry point, public routes, modes,
optional dependencies, and evidence status for:

| Component | Required coverage |
| --- | --- |
| `contract` | closed wire types, canonical URLs, limits, receipts |
| `sdk` | registry, client, results, SQL, formulas, temporal, workbook |
| `cli` | parser and command dispatch |
| `local_files` | CSV/JSON/JSONL/Markdown and Excelize workbook profiles |
| `spreadsheets` | catalog, capabilities, rich objects, recipes, snapshots |
| `maybe_sheet` | canonical HTTPS, Base/Sheet modes, recorded/live gates |
| `google_sheets` / `feishu_bitable` / `postgres` / `sqlite` / `dbt` | route,
  credentials, supported modes, capability checks |
| `artifacts` / `officecli` | contracts, DOCX/PPTX export, renderer prerequisites |
| `mcp` | three tools, `OTC_MCP_CONFIG`, policy, host requirement |
| `process` | framed protocol, `OTC_PROCESS_CONFIG`, artifact root |
| `timeseries` / `formulas` / `conformance` | purpose, public contracts, test role |

No component row may imply that a static catalog entry is live provider
support. Link each row to its readiness evidence or explicit blocker.

## Behavioral gap closure

### CLI shortcut commit path

Refactor `run_spreadsheet` so actions `style`, `format`, `write`, and
`worksheet` call the same queue-and-`WorkbookSession.write()` path as
`operation` and `batch`. `read`, `style-read`, `config-read`, `verify`, and
`inspect` remain non-mutating. Preserve one-operation buffering, `--dry-run`,
`--allow-partial`, `--expected-revision`, `--idempotency-key`, and
`--failure-directory`. A successful shortcut must emit the SDK wire result, not
just an inspection result. A failure must use the established exit/error path.

Acceptance:

- style/format/write/worksheet create/rename/delete persist through reopen;
- dry-run leaves bytes and sheet names unchanged and returns `planned`;
- invalid arguments dispatch zero provider commands;
- all shortcut options compile identically to their generic operation records;
- partial/unknown receipts freeze the session and preserve reconciliation data.

### Recipe observation and parser

Give `recipe` its own subparser or place `export` in a single unambiguous
position. The accepted form is:

```console
otc spreadsheet recipe export --uri file:///absolute/report.xlsx \
  --selectors selectors.json --allow-incomplete
```

`export_recipe` must bind the target through the SDK, capture a fresh snapshot or
provider observation, and include only operations whose selectors are present
and independently observed. Default behavior rejects missing observations;
`--allow-incomplete` returns an explicit omission warning. Requirements are
recomputed from operations. Values, formulas, expression text, image bytes,
asset paths, and arbitrary provider options are rejected. Apply must validate
the recipe, bind the target, respect dry-run/partial/revision/idempotency
options, and close the session without discarding a committed result.

Acceptance:

- parser accepts the form above and rejects ambiguous positional forms;
- fresh observation changes or stale source revisions are detected;
- local export/apply/reopen verifies style/format/config identity;
- unsupported selector fails before dispatch; incomplete export is explicit;
- apply dry-run produces no file mutation; and
- remote partial effects preserve receipt IDs and unknown state.

### SDK generic operation dispatch

Make the built-in spreadsheet handler use a bounded context-managed session or
an equivalent explicit close/finalize path. Read operations return observations
without publication. Mutations queue records, call `write()` with the supplied
`ExecutionOptions`, return its complete result, and close after commit or
failure. Never suppress `OTCError`, partial effects, or unknown commit states.

Acceptance covers range write/style/format, worksheet creation, dry-run,
unsupported operations, stale revisions, and no leaked open sessions.

### MCP host wiring

Keep exactly three tools. `create_server()` must accept an explicit host
dependency or factory that supplies the configured `Client` and policy. The
standalone `otc-mcp` process remains fail-closed when no host is configured; a
host-backed deployment must route `otc_inspect` and `otc_execute` through the
same `OperationCatalog`, `execute_operation`, and `ExecutionOptions` used by
the CLI. Reject read/write mismatches, policy violations, shell-like values,
credential values, and unknown operations before dispatch.

Acceptance uses the official MCP client for initialize/list/call, verifies
exactly three tools, runs a read-only inspect and a typed local execute through
a test host, and verifies no-host startup returns configuration failure.

### Artifact renderer and watch gates

Keep artifact creation separate from workbook authoring. Add a runtime adapter
interface that reports binary version, renderer/browser availability, supported
formats/modes, and owned process identity. `view` copies a committed snapshot
into disposable storage; source hash is checked before and after rendering.
`watch start/status/refresh/stop` records ownership, loopback URL, snapshot
hash, editability, persistence, and termination state. Refresh re-exports a
fresh committed snapshot; it never uploads preview edits or silently polls.

Acceptance requires either a qualified OfficeCLI/browser runtime or an explicit
capability result. With a fake runtime, verify nonblank PNG/HTML output, asset
references, path isolation, source immutability, port ownership, stale-PID
protection, crash status, refresh replacement, and stop-without-publish.

## Generated-reference tooling

`scripts/generate_reference_manuals.py` is the single generator for CLI options,
public API exports/signatures, and spreadsheet operation schemas. It must:

- import only the workspace's core package set;
- tolerate absent optional provider wheels and mark their sections unavailable;
- use deterministic sorting and stable source links;
- preserve declared signatures without evaluating arbitrary annotations;
- provide `--check` for CI; and
- fail on stale generated files.

CI adds:

```console
uv run --all-packages python scripts/generate_reference_manuals.py --check
uv run --all-packages python scripts/check_cli_reference.py
```

The generated files must link from `docs/reference/README.md`, while the three
manuals link from the root README and package READMEs.

## Verification and delivery

Run the focused tests for each gap, the documentation generator check, CLI
reference check, package-boundary/independence checks, and the existing full
suite. Build wheels for core, CLI, spreadsheets, artifacts, OfficeCLI, and MCP
to verify optional-package imports remain removable. Update the acceptance
report with the new gap rows and keep live OfficeCLI/MaybeSheet gates explicit
when their runtimes or credentials are unavailable.

Out of scope: new Excelize object types, new MaybeSheet server commands,
legacy `.doc/.ppt/.xls` converters, a global OfficeCLI command grammar, and
automatic background rendering or remote polling.
