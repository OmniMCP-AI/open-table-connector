# OTC P0-P2 acceptance ledger

Date: 2026-10-06 (Asia/Shanghai)

This ledger distinguishes implemented-source evidence from live runtime gates.
The branch contains the implementation and its tests; a pending live gate is
not presented as qualified behavior.

The final source revision for this ledger includes the Python 3.11 dataclass
compatibility fix, the Excelize-only rich-profile write path, and fail-closed
MCP startup added after the initial local verification.

| Gate | Evidence on this branch | Result |
| --- | --- | --- |
| A1 command/reference inventory | D2/D4 commits `7b8ed9d`, `d58fc86`; CLI reference checker and 209 CLI tests | Pass |
| A2 discovery truthfulness | D1/D2 commits; 122 combined SDK/CLI/universal discovery tests | Pass |
| A3 shortcut parity | D3 commit `dd6860b`; shortcut, stdin, and CLI E2E tests | Pass |
| A4 bounded file/stdin input | D1/D3 commits; strict JSON and explicit `--commands -` tests | Pass |
| A5 errors and exits | D4 commit; safe suggestion and exit mapping tests | Pass |
| A6 agent guide | D4 documentation and CLI reference checks | Pass |
| A7 native document tables | O1/O2 commits `0b2882a`, `e7ca3c2`; 38 artifact/OfficeCLI/MCP-focused tests | Source-level pass; live OfficeCLI export pending |
| A8 views/watch | O3/O4 commits `67d08ba`, `6686d99`; view/session/parser tests | Source-level pass; live renderer/browser pending |
| A9 local Excelize rich objects | R1/R2/R4 commits; 3 local image tests, 74 local provider/verify/formula tests, 2 snapshot tests | Pass for qualified image subset |
| A10 MaybeSheet rich sheet-mode | R3 commit `78da567`; 5 recorded MaybeSheet tests | Pending live disposable target/credentials |
| A11 typed MCP parity | M1/M2 implementation; 10 MCP tests; official SDK initialize/list/call smoke | Pass for typed transport and discovery; host-backed execute parity remains runtime-dependent |
| A12 observed recipe replay | R5 commit `0236597`; 6 recipe/SDK/CLI tests | Pass for local contract and dry-run semantics |

## Verification commands

The focused suites completed during implementation include:

```text
209 CLI tests
122 combined SDK/CLI/universal discovery tests
74 local spreadsheet/provider/verification/formula tests
5 rich contract tests
3 local rich XLSX/image tests
5 recorded MaybeSheet rich tests
6 recipe/SDK/CLI tests
38 artifact/OfficeCLI/MCP focused tests
10 MCP package tests after official SDK integration
```

The official MCP client successfully initialized `otc-mcp`, listed exactly
`otc_discover`, `otc_inspect`, and `otc_execute`, and called `otc_discover`
over stdio. Cancellation and host-backed execution require an SDK host and are
kept as explicit integration limitations rather than inferred from the
discovery smoke.

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
