# CLI Manual

`otc` is a pipeline tool for inspecting, moving, and safely mutating tabular
resources. This manual is organized from the shortest useful command to the
complete option and evidence model. The generated [CLI option inventory](../reference/cli-options.md)
is the parser-level source of truth: every flag, default, choice, and usage
line is generated from `build_parser()`.

The command model follows a familiar open-source CLI shape: DuckDB documents
startup arguments separately from interactive dot commands, and csvkit groups
tools by input, processing, and output. OTC applies the same separation to
source addressing, transformation/publication, and output/evidence. See the
[DuckDB CLI overview](https://duckdb.org/docs/stable/clients/cli/overview),
[DuckDB arguments](https://duckdb.org/docs/current/clients/cli/arguments), and
[csvkit CLI guide](https://csvkit.readthedocs.io/en/latest/cli.html).

## 1. Install and run

Install a release or use the workspace checkout:

```console
uv tool install open-table-connector
otc --help
otc --version

uv sync --all-packages --group dev
source .venv/bin/activate
otc --help
```

The equivalent entry points are `otc` and `open-table-connector`. The legacy
`open-connectors` alias remains for compatibility. The root parser has only
`--version`; command options belong after the subcommand.

## 2. Addressing and credentials

Use a bare path or canonical `file://` URL for local CSV, JSON, JSONL, XLSX,
and Markdown resources. CSV is a codec, not a public connector scheme. Use
`md://` only when explicitly selecting the Markdown connector. MaybeSheet uses
canonical HTTPS document URLs. Do not put tokens, passwords, or access keys in
URIs.

```console
otc inspect --from orders.csv --output-format json
otc inspect --from file:///absolute/path/orders.xlsx --output-format json
otc read --from md:///absolute/path/report.md --output-format table
otc read --from https://www.maybe.ai/docs/spreadsheets/d/DOCUMENT --target Orders
```

Provider credentials are selected by a logical reference. The reference maps
to environment or secret-manager bindings in the OTC config:

```console
otc read --credential-key google_sheets=work \
  --from gsheets://SPREADSHEET_ID/Orders
```

`--credential-key` is repeatable. It selects a binding for one invocation; it
does not carry a secret to the provider as a command argument. A malformed
binding, forbidden URI credential, or missing required credential returns a
structured configuration/authentication error before provider I/O.

## 3. Choose a workflow

| Need | Command | Writes? | Start here |
| --- | --- | ---: | --- |
| See installed providers | `list` | no | `otc list --output-format table` |
| Understand a source | `inspect` | no | `otc inspect --from SOURCE --output-format json` |
| Stream rows | `read` | no | `otc read --from SOURCE --output-format jsonl` |
| Create a local destination | `convert` | local | `otc convert --from SOURCE --to DEST` |
| Publish to a connector | `import` | remote/local | `otc import --from SOURCE --to DEST --if-exists error` |
| Read an operation schema | `help` | no | `otc help spreadsheet range.write --output-format json` |
| Resolve target support | `capabilities` | no | `otc capabilities --uri URI --output-format json` |
| Edit a workbook | `spreadsheet` | yes/buffered | `otc spreadsheet write ...` |
| Export a document artifact | `artifact export` | new artifact | `otc artifact export ...` |

## 4. Output, exit status, and evidence

The normal output format is JSON Lines (`jsonl`) for row-producing commands.
Use `csv`, `json`, or `table` when a consumer requires that representation.
`convert` additionally accepts `auto` and `excel` as output/destination formats.

Failures are one safe JSON object on stderr. Scripts should branch on the exit
status and `code`, not on human-readable message text. The common status model
is:

| Result field | Meaning | Automation rule |
| --- | --- | --- |
| `outcome=succeeded` | Operation completed | consume value and receipts |
| `outcome=planned` | Dry-run validated but did not publish | show plan; do not claim persistence |
| `outcome=rejected` | Preflight or policy stopped dispatch | fix input/policy; no retry of same input without change |
| `outcome=partial` | Some effects are committed | inspect every receipt and reconcile |
| `outcome=unknown` | Commit visibility is unresolved | reconcile before retrying |
| `verification=passed` | Independent evidence matched | safe to use the claimed value |
| `verification=failed/unavailable` | Evidence did not prove the claim | treat as unresolved |

CLI exit codes are intentionally small: `0` means success or an accepted
plan, `2` means command/argument usage failure, and `5` means a connector,
capability, execution, verification, or reconciliation failure. See the
[stable error-code reference](../reference/error-codes.md).

## 5. Core data commands

### `list`

`list` loads installed descriptors and reports connector IDs, URI schemes,
capabilities, modes, and materialization support when available.

```console
otc list
otc list --output-format json
otc list --output-format csv
```

Options: `--output-format {csv,json,jsonl,table}`. The default is `jsonl`.
An installed descriptor is not proof that a specific target supports every
operation; use `capabilities` for target evidence.

### `inspect`

`inspect` reads source facts without returning the full row payload. It is the
right first step for schema discovery, connector routing, row-count checks,
and preflight evidence.

```console
otc inspect --from orders.csv --output-format json
otc inspect --from file:///absolute/path/model.xlsx --sheet Model --range A1:H100
otc inspect --from gsheets://ID/Orders --credential-key google_sheets=work
```

Options:

| Option | Applies | Details |
| --- | --- | --- |
| `--from SOURCE` | required | source path or connector URI |
| `--from-format {auto,csv,excel,json,jsonl,table}` | optional | override local format detection |
| `--output-format {csv,json,jsonl,table}` | optional | defaults to `jsonl` |
| `--sheet NAME` | optional | worksheet or provider sheet |
| `--range A1:R9` | optional | bounded range where the provider supports it |
| `--field-name NAME` | repeatable | field projection for supported providers |
| `--limit N` | optional | positive row bound |
| `--timeout SECONDS` | optional | connector deadline |
| `--credential-key PROVIDER=REF` | repeatable | credential binding reference |
| `--target VALUE` | optional | provider-specific target selector |
| `--to DESTINATION` | accepted for compatibility | not used by inspection |
| `--if-exists POLICY` | accepted common option | not used by inspection |

### `read`

`read` returns records. Prefer JSONL for pipelines and `table` for terminals.
Use `--limit` and `--range` to keep reads bounded.

```console
otc read --from orders.csv --output-format jsonl
otc read --from orders.csv --limit 20 --output-format table
otc read --from file:///absolute/path/report.xlsx --sheet Report --range A1:D50
otc read --from gsheets://ID/Orders --range 'Orders!A1:E20' --output-format json
```

`read` accepts the same source, format, sheet/range, field, timeout,
credential, and target options as `inspect`. `--to` and `--if-exists` are
parser-compatible common options but do not create a destination; use
`convert` or `import` when publishing is intended.

### `convert`

`convert` reads once and writes a local destination or stdout. It is for
codec conversion and local hand-off, not remote connector publication.

```console
otc convert --from orders.csv --to orders.jsonl --output-format jsonl
otc convert --from orders.csv --to orders.xlsx --to-format excel --sheet Orders
otc convert --from orders.csv --to - --output-format csv
otc convert --from file:///absolute/orders.json --to report.csv --to-format csv
```

Options are `--from`, `--to`, `--from-format`, `--output-format`, `--to-format`,
`--if-exists`, `--sheet`, `--range`, `--field-name`, `--limit`, `--timeout`,
`--credential-key`, and `--target`. `--output-format` controls stdout when
the destination is `-`; `--to-format` controls a file destination. If both
are supplied, they are independent. `--if-exists` is `error`, `append`, or
`replace`; use `error` unless overwriting is deliberate.

### `import`

`import` publishes into a writable connector. It uses the same common source
options as `read`, plus a required `--to` and conflict policy.

```console
otc import --from orders.csv --to gsheets://ID/Orders --if-exists append
otc import --from orders.csv --to https://www.maybe.ai/docs/spreadsheets/d/DOC \
  --target Orders --if-exists replace --credential-key maybe_sheet=work
```

Use `append` for additive loads, `replace` only for an intentional replacement,
and `error` for create-only behavior. A remote partial or unknown result is
not converted into success; retain its receipt and reconcile with a bounded
readback.

### `help` and `capabilities`

`help` is static catalog discovery and never opens a target. `capabilities`
binds the catalog to a target and may perform provider observation.

```console
otc help spreadsheet
otc help spreadsheet range.write --output-format json
otc capabilities --uri file:///absolute/path/report.xlsx --sheet Report
otc capabilities --uri https://www.maybe.ai/docs/spreadsheets/d/DOC \
  --output-format json
```

`help` options: positional `namespace`, optional `operation_id`, and
`--output-format {json,table}` (default `table`). `capabilities` options:
required `--uri`, optional `--sheet`, and `--output-format {json,table}`
(default `table`).

## 6. Spreadsheet commands

All spreadsheet mutations open one buffered workbook session, queue changes,
call the same `write()` path as the SDK, and close the session. `--dry-run`
returns a planned result without changing bytes. `--expected-revision` adds
optimistic concurrency. `--idempotency-key` makes a retried request
recognizable. `--allow-partial` opts into partial effects; it does not make a
partial result look successful.

Common required option: `--uri URI`. Common optional options are:

| Option | Meaning |
| --- | --- |
| `--sheet NAME` | worksheet target for range and operation shortcuts |
| `--range A1:R9` | A1 rectangle for read/style/format/write |
| `--values JSON` | rectangular JSON matrix for `write` |
| `--values-file PATH` | read that matrix from a bounded JSON file or stdin (`-`) |
| `--operation ID` | catalog operation for `operation` |
| `--arguments JSON` | typed operation arguments, default `{}` |
| `--commands PATH` | version `1.0` batch command file |
| `--profile PROFILE` | `general/1.0`, `literal-artifact/1.0`, or `rich-artifact/1.0` |
| `--create` | create a new local workbook/session |
| `--dry-run` | validate and plan without publication |
| `--allow-partial` | allow provider partial results |
| `--expected FILE` | independent expected-intent JSON for verification |
| `--expected-revision HASH` | reject stale source bytes/revision |
| `--idempotency-key KEY` | stable retry identity |
| `--failure-directory PATH` | retain failure artifacts |
| `--credential-key PROVIDER=REF` | provider credential binding |

### Read and inspection actions

```console
otc spreadsheet read --uri file:///absolute/report.xlsx --sheet Report --range A1:D20
otc spreadsheet style-read --uri file:///absolute/report.xlsx --sheet Report \
  --range A1:D2 --fields '["bold","fill"]'
otc spreadsheet config-read --uri file:///absolute/report.xlsx --sheet Report \
  --rows '[1,2]' --columns '["A","B"]' --view-fields '["hidden","width"]'
otc spreadsheet inspect --uri file:///absolute/report.xlsx
otc spreadsheet verify --uri file:///absolute/report.xlsx --expected expected.json
```

`read` requires `--sheet` and `--range`. `style-read` additionally accepts
`--fields`. `config-read` requires `--rows` and `--columns`, with optional
`--view-fields`. `inspect` observes workbook metadata. `verify` checks the
retained expected intent or provider verification model.

### Shortcut mutations

```console
otc spreadsheet write --uri file:///absolute/report.xlsx --sheet Report \
  --range A1:B2 --values '[["Name","Total"],["Ada",42]]'
otc spreadsheet style --uri file:///absolute/report.xlsx --sheet Report \
  --range A1:B1 --bold --italic
otc spreadsheet style --uri file:///absolute/report.xlsx --sheet Report \
  --range A1:B1 --no-bold
otc spreadsheet format --uri file:///absolute/report.xlsx --sheet Report \
  --range B2:B20 --pattern '$#,##0.00'
otc spreadsheet worksheet create --uri file:///absolute/report.xlsx --name Summary
otc spreadsheet worksheet rename --uri file:///absolute/report.xlsx \
  --sheet Summary --name Executive
otc spreadsheet worksheet delete --uri file:///absolute/report.xlsx --sheet Executive
```

`write` requires a non-empty rectangular matrix whose dimensions exactly match
the A1 range. `style` supports `--bold`, `--no-bold`, `--italic`, and
`--no-italic`; conflicting positive and negative flags are usage errors.
`format` requires `--pattern`. Worksheet `create` and `rename` require
`--name`; `delete` uses `--sheet`.

### Generic operation and batch actions

Use `operation` when the catalog already has a typed operation and `batch`
when several buffered mutations must publish together.

```console
otc spreadsheet operation --uri file:///absolute/report.xlsx \
  --operation range.write --sheet Report \
  --arguments '{"address":"A1","values":[["ready"]]}'
```

Batch files are closed JSON objects with exactly `version` and `changes`:

```json
{
  "version": "1.0",
  "changes": [
    {"operation_id":"range.write","target_key":"Report","arguments":{"address":"A1","values":[["ready"]]}},
    {"operation_id":"range.format","target_key":"Report","arguments":{"address":"B2:B20","pattern":"$#,##0.00"}}
  ]
}
```

```console
otc spreadsheet batch --uri file:///absolute/report.xlsx --commands changes.json
otc spreadsheet batch --uri file:///absolute/report.xlsx --commands - < changes.json
```

Each change must contain only `operation_id`, `target_key`, and `arguments`.
Read-only operations are rejected in a buffered batch. Image bytes may be
represented as a strict `content_base64` string; duplicate encodings and
invalid base64 are rejected before dispatch.

### Profiles and rich XLSX

`general/1.0` is the broad workbook profile, `literal-artifact/1.0` applies
literal artifact constraints, and `rich-artifact/1.0` enables the existing
Excelize-backed rich subset. The rich subset currently covers PNG/JPEG image
insert, list/read observation, and deletion with serialized readback.

```console
otc spreadsheet operation --uri file:///absolute/report.xlsx \
  --create --profile rich-artifact/1.0 --operation image.insert --sheet Report \
  --arguments '{"content_base64":"...","mime_type":"image/png","anchor":"B2"}'
```

OfficeCLI never authors or resaves authoritative XLSX. MaybeSheet sheet-mode
uses the same operation contract but remains live-evidence gated.

### Recipes

Recipes capture observed layout operations and requirements. They never carry
cell values, formulas, or image bytes.

```console
otc spreadsheet recipe export --uri file:///absolute/report.xlsx \
  --selectors selectors.json
otc spreadsheet recipe export --uri file:///absolute/report.xlsx \
  --selectors selectors.json --allow-incomplete
otc spreadsheet apply --uri file:///absolute/report.xlsx \
  --spec recipe.json --dry-run
```

Export binds selectors to a fresh observation. Missing or unsupported
selectors fail by default; `--allow-incomplete` emits explicit omissions.
Apply revalidates requirements and closes the session after success, failure,
or unknown commit. Use the generated [spreadsheet schemas](../reference/spreadsheet-schemas.md)
for every operation's argument/result schema.

## 7. Artifact commands

The optional artifacts package provides native DOCX/PPTX table snapshots and
disposable views. Install the artifacts and OfficeCLI packages separately.

```console
otc artifact export --from orders.csv --to report.docx
otc artifact export --from orders.csv --to deck.pptx
```

`artifact export` accepts `--from`, `--to`, and `--output-format {json,table}`.
The source currently must be a qualified CSV and the destination must be
`.docx` or `.pptx`; legacy `.doc`, `.ppt`, and `.xls` are rejected. OfficeCLI
is not an XLSX writer.

The parser also exposes the neutral view/watch contract:

```console
otc artifact view --uri file:///absolute/report.docx --mode html
otc artifact view --uri file:///absolute/deck.pptx --mode screenshot
otc artifact watch start --uri file:///absolute/report.docx
otc artifact watch status --session SESSION_ID
otc artifact watch refresh --session SESSION_ID
otc artifact watch stop --session SESSION_ID
```

View options: `--uri`, `--mode {html,screenshot,text,outline,stats,issues}`,
and `--output-format {json,table}`. Watch options: `--uri`, `--session`, and
`--output-format`. The current CLI returns an explicit capability result until
a qualified OfficeCLI/browser runtime is configured. SDK view/watch records
source and snapshot hashes, owned process identity, loopback URL, and
preview-copy-only/discard semantics.

## 8. MCP stdio

The optional MCP package exposes exactly three official tools:
`otc_discover`, `otc_inspect`, and `otc_execute`. Set `OTC_MCP_CONFIG` to an
absolute policy file. Embedding deployments inject an SDK client with
`MCPHost(client)`; no-host inspect/execute fails closed.

The operation request is closed and typed:

```json
{
  "namespace":"spreadsheet",
  "operation_id":"range.read",
  "version":"1.0",
  "target":{"uri":"file:///absolute/report.xlsx","sheet":"Report","object_id":null},
  "arguments":{"address":"A1:B2"}
}
```

Do not add shell commands, module names, credentials, or undeclared fields.
Policy checks run before dispatch. See the [SDK manual](sdk-manual.md) for
host injection and the package README for deployment configuration.

## 9. Use-case recipes

### Daily analyst export

```console
otc inspect --from daily-orders.csv --output-format json
otc convert --from daily-orders.csv --to daily-orders.jsonl --output-format jsonl
otc convert --from daily-orders.jsonl --to daily-orders.xlsx --to-format excel --sheet Orders
otc inspect --from daily-orders.xlsx --output-format json
```

### Team-sheet publication

```console
otc inspect --from daily-orders.csv --output-format json
otc import --from daily-orders.csv --to gsheets://ID/Orders \
  --if-exists append --credential-key google_sheets=work
otc read --from gsheets://ID/Orders --range 'Orders!A1:E20' --output-format table
```

### Safe workbook layout change

```console
otc capabilities --uri file:///absolute/report.xlsx --sheet Report --output-format json
otc spreadsheet style --uri file:///absolute/report.xlsx --sheet Report \
  --range A1:E1 --bold --dry-run
otc spreadsheet style --uri file:///absolute/report.xlsx --sheet Report \
  --range A1:E1 --bold --expected-revision sha256:...
otc spreadsheet verify --uri file:///absolute/report.xlsx --sheet Report
```

### Reproducible batch update

Keep `changes.json` under version control, run it with `--dry-run` in CI, then
publish with a unique idempotency key and retain the JSON result as an audit
artifact.

### Preview a committed artifact

Finish the authoritative Excelize/SDK commit and independent readback first.
Then call the SDK artifact view or watch contract on its disposable snapshot.
Never use preview output as the workbook source of truth.

## 10. Troubleshooting

1. Run `otc list` to confirm the provider is installed and enabled.
2. Run `otc help NAMESPACE [OPERATION]` to confirm the operation schema.
3. Run `otc capabilities --uri URI` to distinguish static support from target evidence.
4. Reduce the input with `--limit`, `--range`, or a bounded source file.
5. For a failed mutation, inspect `commit`, `verification`, and every receipt.
6. For `unknown`, reconcile/read back before retrying; do not assume no effect.
7. For credential errors, fix the configured reference instead of adding secrets to the URI.

See [error codes](../reference/error-codes.md), [agent workflows](agent-workflows.md),
and the [generated option inventory](../reference/cli-options.md) for the
machine-level details.
