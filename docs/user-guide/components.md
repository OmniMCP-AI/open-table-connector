# Components Manual

Use the generated [API inventory](../reference/api-inventory.md) for names and signatures, this page for package ownership and prerequisites, and each package README for focused examples.

## Core layers

| Package | Owns | Dependency rule |
| --- | --- | --- |
| `contract` | URI, identity, receipts, errors, operation wire contracts | framework-free |
| `sdk` | Client, Table, Query, workbook sessions, results | depends on neutral contracts |
| `cli` | argparse, output, exit codes, shortcuts | thin wrapper over SDK |
| `spreadsheets` | workbook operation schemas, Excelize-neutral rich contracts, recipes | provider-neutral |
| `local_files` | local CSV/XLSX/JSON/Markdown routing and Excelize-backed workbook provider | optional connector |
| `artifacts` | neutral DOCX/PPTX/view/watch models | no OfficeCLI process dependency |
| `officecli` | optional native DOCX/PPTX export and disposable rendering | isolated external process |
| `mcp` | optional official MCP stdio tools and policy boundary | explicit SDK host |

## Local files and Excelize

Local table and workbook paths use bare paths or canonical `file://` URLs. The local rich profile uses existing Excelize capabilities for qualified PNG/JPEG images, observations, and deletion. It does not add new object implementations and does not call OfficeCLI. MaybeSheet sheet-mode shares the workbook operation contract but requires provider-specific live evidence before a capability is advertised.

```python
from open_table_connector.sdk import Client, ConnectorRegistry
from open_table_connector.local_files import LocalFilesConnector

client = Client(registry=ConnectorRegistry([LocalFilesConnector()]))
book = client.workbook.create("file:///absolute/path/report.xlsx", profile="rich-artifact/1.0")
book.worksheet.create("Report")
book.worksheet("Report").image(png_image, anchor="B2")
result = book.write()
```

## OfficeCLI adapter

Install `open-table-connector-officecli` only when native document artifacts or views are required. The adapter creates DOCX/PPTX table snapshots from qualified sources, reports content hashes and coverage, and never authors authoritative XLSX.

The pinned runtime is qualified by version probe (`1.0.154`). Rendering is argv-only, bounded, loopback-only for watch, and launched with `OFFICECLI_SKIP_UPDATE=1` and `OFFICECLI_NO_AUTO_RESIDENT=1`. Browser-dependent PNG requires an executable browser. Missing or mismatched prerequisites produce capability errors.

```console
otc artifact export --from orders.csv --to report.docx
```

## MCP adapter

Install `open-table-connector-mcp` separately. The official stdio server registers `otc_discover`, `otc_inspect`, and `otc_execute`; an embedding deployment supplies `MCPHost(client)` and an optional policy. The standalone entry point requires an absolute `OTC_MCP_CONFIG` and fails closed when it is absent or invalid.

## Providers and capability evidence

Provider installation does not imply operation support. Check `otc list`, `otc help`, and `otc capabilities` before dispatch. Remote providers may report partial or unknown effects; those states remain in the result and require reconciliation. Credentials are resolved by configuration references and are never forwarded to OfficeCLI renderers.

## Reference map

- [CLI manual](cli-manual.md)
- [SDK manual](sdk-manual.md)
- [CLI option inventory](../reference/cli-options.md)
- [Python API inventory](../reference/api-inventory.md)
- [Spreadsheet schemas](../reference/spreadsheet-schemas.md)
