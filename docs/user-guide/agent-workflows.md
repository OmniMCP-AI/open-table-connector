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
