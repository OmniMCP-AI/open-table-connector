# OTC P0-P2 acceptance ledger

Date: 2026-10-06 (Asia/Shanghai)

This ledger distinguishes implemented-source evidence from live runtime gates.
The branch contains the implementation and its tests; a pending live gate is
not presented as qualified behavior.

The final source revision for this ledger includes shortcut persistence,
fresh recipe observation, generic session finalization, explicit MCP host
wiring, bounded renderer/watch state, and complete generated manuals.

| Gate | Evidence on this branch | Result |
| --- | --- | --- |
| A1 command/reference inventory | Generated CLI/API/schema references; CLI parity and link checks | Pass |
| A2 discovery truthfulness | D1/D2 commits; 122 combined SDK/CLI/universal discovery tests | Pass |
| A3 shortcut parity | Commit `6cc4146`; persistence and dry-run shortcut tests | Pass |
| A4 bounded file/stdin input | D1/D3 commits; strict JSON and explicit `--commands -` tests | Pass |
| A5 errors and exits | D4 commit; safe suggestion and exit mapping tests | Pass |
| A6 agent guide | D4 documentation and CLI reference checks | Pass |
| A7 native document tables | Existing adapter coverage plus artifact focused suite | Source-level pass; live OfficeCLI export pending |
| A8 views/watch | Commit `f0352d3`; fake runtime, source-hash, port, crash, refresh, and stop tests | Source-level and fake-runtime pass; live renderer/browser pending |
| A9 local Excelize rich objects | R1/R2/R4 commits; 3 local image tests, 74 local provider/verify/formula tests, 2 snapshot tests | Pass for qualified image subset |
| A10 MaybeSheet rich sheet-mode | R3 commit `78da567`; 5 recorded MaybeSheet tests | Pending live disposable target/credentials |
| A11 typed MCP parity | Commit `2d0f9ec`; 15 MCP tests including local host-backed inspect/execute | Pass for typed transport, discovery, policy, and host dispatch |
| A12 observed recipe replay | Commit `768df41`; recipe/SDK/CLI/spreadsheet tests | Pass for local contract and dry-run semantics |
| A13 manuals and generated references | Commit `1730166`; deterministic generator, `--check`, CLI parity, link check | Pass |

## Verification commands

The focused suites completed during implementation include:

```text
59 focused gap tests
1,829 full regression tests passed
7 tests skipped for unavailable live integrations
3 local rich XLSX/image tests
5 recorded MaybeSheet rich tests
15 MCP package tests including host-backed execution
Generated reference and manual-link checks
Package boundary/independence checks and wheel smoke
```

The official MCP client initialized `otc-mcp`, listed exactly
`otc_discover`, `otc_inspect`, and `otc_execute`, and the local host fixture
executed typed inspect/write operations through the SDK catalog.

## Release blockers and scope decisions

- A qualified OfficeCLI binary and browser runtime were unavailable. Real DOCX,
  PPTX, HTML, PNG, and watch acceptance therefore remains pending.
- No authorized live MaybeSheet disposable target was available. Recorded
  evidence does not close the live A10 gate.
- Rich XLSX uses existing Excelize capabilities only, including sheet-mode
  provider reuse; OfficeCLI is never the spreadsheet author.
- Legacy `.doc`, `.ppt`, and `.xls` output is not claimed without a separately
  qualified converter.
- Unsupported charts, pivots, shapes, comments, validations, conditional
  formatting, and other object families remain capability-gated until
  independent save/reopen evidence exists.
