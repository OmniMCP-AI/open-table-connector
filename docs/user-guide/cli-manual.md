# CLI Manual

This is the behavior manual for `otc`. The generated [CLI option inventory](../reference/cli-options.md) is the exhaustive parser reference; this page explains which commands open targets, which commands publish changes, and how to interpret results.

## Install and address targets

```console
uv tool install open-table-connector
otc --help
otc --version
```

Use a bare path or canonical `file://` URL for local files. CSV is a codec, not a public URI scheme. MaybeSheet targets are canonical HTTPS document URLs.

```console
otc inspect --from file:///absolute/path/orders.csv --output-format json
otc read --from file:///absolute/path/orders.xlsx --sheet Orders --output-format table
otc read --from https://www.maybe.ai/docs/spreadsheets/d/DOCUMENT --target Orders --output-format json
```

Provider credentials are selected by reference, never embedded in operation payloads:

```console
otc --credential-key google_sheets=work read --from gsheets://SPREADSHEET/Orders
```

## Core commands

`list` reports installed descriptors. `inspect` reads schema and source facts. `read` emits rows. `convert` reads once and writes a local destination. `import` writes a connector destination under its conflict policy. `help` describes a registered operation without opening a target, and `capabilities` resolves target-specific support and evidence.

```console
otc list --output-format json
otc help spreadsheet range.write --output-format json
otc capabilities --uri file:///absolute/path/report.xlsx --output-format json
otc convert --from orders.csv --to orders.jsonl --output-format jsonl
otc import --from orders.csv --to gsheets://ID/Orders --if-exists replace
```

Success is represented in the selected output format. Failures are one safe JSON object on stderr. Automation should branch on the exit code and stable `code`; message text is diagnostic.

## Spreadsheet sessions

Every mutating spreadsheet command uses one buffered workbook session. Reads observe the current committed workbook. Mutations queue changes and call the same `write()` path used by the SDK.

```console
otc spreadsheet read --uri file:///absolute/path/report.xlsx --sheet Report --range A1:D20
otc spreadsheet write --uri file:///absolute/path/report.xlsx --sheet Report --range A1:B2 --values '[["Name","Total"],["Ada",42]]'
otc spreadsheet style --uri file:///absolute/path/report.xlsx --sheet Report --range A1:B1 --bold
otc spreadsheet format --uri file:///absolute/path/report.xlsx --sheet Report --range B2:B20 --pattern '$#,##0.00'
otc spreadsheet worksheet create --uri file:///absolute/path/report.xlsx --name Summary
```

Use `--dry-run` to validate and return a planned result without changing bytes. Use `--expected-revision` to reject a stale source, `--allow-partial` only when partial receipts are acceptable, and `--idempotency-key` when a caller may retry a request.

```console
otc spreadsheet write --uri file:///absolute/path/report.xlsx --sheet Report --range A1 --values '[["preview"]]' --dry-run
otc spreadsheet batch --uri file:///absolute/path/report.xlsx --commands changes.json --expected-revision sha256:...
```

The result fields `outcome`, `commit`, `verification`, `receipts`, `warnings`, and `error.reconciliation` are authoritative. `unknown` means the caller must reconcile before retrying; it is never treated as success.

## Rich XLSX and recipes

Rich XLSX uses the existing Excelize-backed provider. OfficeCLI is never an XLSX writer. Select `--profile rich-artifact/1.0` when creating a workbook and check capabilities before relying on object families. The qualified local subset currently covers PNG/JPEG image insertion, observation, and deletion. MaybeSheet sheet-mode uses the same operation contract but needs live evidence.

```console
otc spreadsheet operation --uri file:///absolute/path/report.xlsx \
  --profile rich-artifact/1.0 --operation image.insert --sheet Report \
  --arguments '{"content_base64":"...","mime_type":"image/png","anchor":"B2"}'
```

Recipes are observation-backed layout envelopes. They contain operations and requirements, never values, formulas, or image bytes. Export requires selectors and a fresh target observation; unsupported or missing selectors fail unless `--allow-incomplete` is explicit.

```console
otc spreadsheet recipe export --uri file:///absolute/path/report.xlsx --selectors selectors.json
otc spreadsheet apply --uri file:///absolute/path/report.xlsx --spec recipe.json --dry-run
```

## Artifacts, views, and watch

The optional artifacts package exports native DOCX/PPTX table snapshots from qualified CSV input. Legacy `.doc`, `.ppt`, and `.xls` destinations are rejected. HTML, PNG, text, outline, stats, issues, and watch use disposable snapshots and must have a qualified OfficeCLI runtime; absence is an explicit `unsupported_capability` result.

```console
otc artifact export --from orders.csv --to report.docx
otc artifact export --from orders.csv --to deck.pptx
```

The SDK artifact facade supports view/watch lifecycle once the optional binary and renderer are configured. Preview edits are never published back to the authoritative workbook.

## MCP

The optional MCP package exposes exactly `otc_discover`, `otc_inspect`, and `otc_execute` over official MCP stdio. `OTC_MCP_CONFIG` must be an absolute policy path. Host-backed deployments inject an SDK client; no-host startup remains fail-closed. Requests use the closed typed operation wire format, including `target.uri`, `target.sheet`, and `target.object_id` keys.
