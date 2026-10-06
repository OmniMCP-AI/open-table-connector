# Agent Workflows

Agents should begin with static discovery and keep execution explicit.

```sh
otc help spreadsheet range.style --output-format json
otc capabilities --uri file:///absolute/path/report.xlsx --output-format json
otc spreadsheet batch --uri file:///absolute/path/report.xlsx --commands commands.json --dry-run
```

Use canonical `file://` paths for local files and HTTPS document URLs for
MaybeSheet. Preserve formulas as explicit formula operations; ordinary writes
keep strings beginning with `=` literal. A rejected request has no mutation.
Partial or unknown results retain receipts and must be reconciled before retry.
Use disposable targets for examples and verify persisted readback before delivery.

For report artifacts, finish the authoritative Excelize write and independent
readback before requesting an OfficeCLI HTML, PNG, or watch preview through the
SDK artifact contract. The current CLI exposes the contract but returns an
explicit capability error for view/watch until a qualified renderer is
configured. Preview outputs are disposable and do not become the XLSX source
of truth. Native DOCX/PPTX table exports are presentation snapshots, not live
connector-backed tables. When using MCP, discover the operation first and pass
typed request objects through the policy-gated `otc_inspect` or `otc_execute`
tool.
