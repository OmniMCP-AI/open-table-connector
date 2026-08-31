# Critical Review Remediation Ledger

This ledger tracks every finding from the 2026-08-31 review. `hypothesis` means
the claim is not yet reproduced by the remediation evidence; later tasks replace
that disposition with `verified`, `invalid`, or `superseded`.

| Finding | Evidence | Priority | Plan task | Verification | Disposition | Commit |
|---|---|---:|---|---|---|---|
| T1 | Evidence chain self-referential | P1 | Specification 1–7 | ledger, fixtures, verifier | verified | pending |
| T2 | Duplicated temporal cores | P2 | Structure 1–7 | structural review | hypothesis | pending |
| T3 | Wire rigor exceeds runtime rigor | P0 | Correctness 1–7 | adversarial tests | hypothesis | pending |
| T4 | Semantics live only in code | P1 | Specification 1 | normative document | verified | 4e1372b |
| T5 | Workspace engineering lags claims | P0 | Packaging 1–6 | metadata/CI checks | hypothesis | pending |
| A1 | DST calendar chaining can drop rows | P0 | Correctness 1 | DST fixture | hypothesis | pending |
| A2 | COUNT accepts a value field | P0 | Specification 1 | Python/schema contract tests | superseded | 4e1372b |
| A3 | SQLite precision mismatch | P0 | Correctness 3 | non-ns fixtures | verified | dbcabdf |
| A4 | Postgres isolation after DDL | P0 | Correctness 4 | live/recording SQL test | verified | 47175b9 |
| A5 | SQL observed range assumes ns | P0 | Correctness 4 | precision receipt tests | verified | dbcabdf |
| A6 | Hosted if_exists=error overwrites/appends | P0 | Correctness 6–7 | provider write tests | verified | 37e93dd |
| A7 | CLI CSV uses Markdown escaping | P0 | Packaging 4–5 | delimiter/newline tests | verified | 0c6846c |
| A8 | IPC fingerprint depends on chunking | P1 | Correctness 5 | chunk invariance test | verified | 7987b86 |
| A9 | Receipt counts/identity fabricated | P1 | Correctness 1 | receipt evidence tests | verified | 7987b86 |
| A10 | --from-format ignored for paths | P1 | Packaging 4 | CLI routing tests | verified | 0c6846c |
| A11 | Qualified SQLite names fail | P0 | Correctness 3 | reader tests | verified | bed6ac9 |
| A12 | Google gid treated as title | P1 | Correctness 6 | URL parsing tests | verified | 37e93dd |
| A13 | output_order fields unchecked | P1 | Correctness 7 | plan validation tests | verified | 7987b86 |
| A14 | SQLite in-memory state resets | P0 | Correctness 4 | lifecycle test | verified | bed6ac9 |
| A15 | SQLite bucket arithmetic truncates | P0 | Correctness 3 | pre-origin tests | verified | dbcabdf |
| B1 | Frame header short-read unsafe | P0 | Process 4 | framing tests | verified | c7c0c67 |
| B2 | Serialization failures disappear/leak | P0 | Process 2–6 | failure envelope tests | verified | pending |
| B3 | Process state/backlog unbounded | P1 | Process 2, 7 | bounded stress tests | verified | pending |
| B4 | Cancel callback holds global lock | P1 | Process 2 | concurrency test | verified | pending |
| B5 | `ok` key sniffs direction | P1 | Process 4, 6 | closed envelope fixtures | verified | pending |
| B6 | Retry/NACK/diagnostics lifecycle gaps | P1 | Process 2, 7 | protocol lifecycle tests | hypothesis | pending |
| C1 | No normative semantics | P1 | Specification 1 | semantics document | verified | 4e1372b |
| C2 | Runtime oracle computes expected values | P1 | Specification 2 | fixture loader tests | hypothesis | pending |
| C3 | Hash inputs unspecified/non-portable | P1 | Specification 7 | hash manifest tests | verified | pending |
| C4 | Stub providers labeled offline verified | P1 | Specification 5 | evidence documents | verified | pending |
| C5 | Only process requests schema'd | P1 | Specification 4 | payload schema tests | hypothesis | pending |
| C6 | Error codes outside closed enum | P1 | Specification 3 | enum/schema parity | hypothesis | pending |
| C7 | Published schemas looser than Python | P1 | Specification 3 | invalid fixture parity | hypothesis | pending |
| C8 | Capability identity has two forms | P1 | Specification 5 | identity round-trip tests | verified | pending |
| C9 | Receipt defs copy-pasted | P1 | Specification 3 | shared-ref schema tests | hypothesis | pending |
| C10 | Cross-framework manifest ignored | P1 | Specification 6 | manifest execution test | hypothesis | pending |
| C11 | Schema misses semantic invariants | P1 | Specification 1, 3 | normative/schema tests | hypothesis | pending |
| D1 | USER_ENTERED enables formulas | P1 | Correctness 6 | write option test | verified | 37e93dd |
| D2 | Postgres read gate allows writes | P1 | Correctness 4 | read-only transaction test | hypothesis | pending |
| D3 | URI scrubbing misses empty/fragments | P1 | Process 3 | URI security tests | hypothesis | pending |
| D4 | ResolveContext repr leaks credentials | P1 | Process 3 | repr/redaction test | hypothesis | pending |
| D5 | maybe_sheet env/cache collisions | P1 | Process 3 | key/cache tests | hypothesis | pending |
| D6 | Bootstrap TOCTOU/PATH/env leakage | P1 | Process 3 | bootstrap security tests | hypothesis | pending |
| D7 | Redaction over/under-matches | P1 | Process 6 | structured redaction tests | hypothesis | pending |
| E1 | CLI output flag conflates destination | P2 | Packaging 4 | codec routing tests | hypothesis | pending |
| E2 | Read/convert JSONL diverge | P2 | Packaging 4 | shared codec tests | hypothesis | pending |
| E3 | Resource limits truncate silently | P2 | Process 6, Packaging 5 | receipt/CLI tests | hypothesis | pending |
| E4 | Coordinate identity silently drops data | P2 | Specification 5 | coordinate round-trip tests | hypothesis | pending |
| E5 | Fingerprint validation differs | P2 | Specification 3 | schema/code parity | hypothesis | pending |
| E6 | ATOMIC-only conformance | P2 | Specification 2 | visibility cases | hypothesis | pending |
| E7 | CLI json/jsonl schemes inconsistent | P2 | Packaging 4 | registry tests | hypothesis | pending |
| E8 | Usage errors lose actionable details | P2 | Packaging 5 | CLI error tests | hypothesis | pending |
| E9 | ConnectorError unsafe defaults/None loss | P2 | Process 6 | error serialization tests | hypothesis | pending |
| E10 | Invalid lazy type expression | P2 | Specification 6 | get_type_hints test | hypothesis | pending |
| E11 | Capability names inconsistent | P2 | Specification 5 | identity tests | verified | pending |
| E12 | Registry shadows/dead write routes | P2 | Packaging 4 | collision/route tests | hypothesis | pending |
| F1 | Evaluator repeats IPC and loops buckets | P2 | Structure 1–3 | performance regressions | hypothesis | pending |
| F2 | Projection pushdown defeated | P2 | Structure 4–5 | requested-field tests | hypothesis | pending |
| F3 | CLI materializes before limit | P2 | Packaging 4 | bounded reader tests | hypothesis | pending |
| F4 | Feishu unchunked/unbounded transport | P2 | Correctness 7, Process 7 | chunk/transport tests | hypothesis | pending |
| G1 | Hosted packages omit dependencies | P0 | Packaging 1 | metadata checker | verified | 4e1372b |
| G2 | Missing license/release artifacts | P0 | Packaging 2 | package checker | verified | b683229 |
| G3 | Documented sync uninstalls workspace | P0 | Packaging 1 | docs/uv sync check | verified | 4e1372b |
| G4 | No CI/lint/typecheck automation | P1 | Packaging 3, 6 | workflow validation | hypothesis | pending |
| G5 | No release trains/tags | P1 | Packaging 2, 3 | package boundary docs | verified | 22aa51f |
| G6 | Rename residue and junk | P1 | Packaging 6 | hygiene check | hypothesis | pending |
| G7 | Conflicting dependency pins | P0 | Packaging 1 | metadata checker | verified | 4e1372b |
| G8 | Buildable root/no typing markers | P0 | Packaging 1–2 | uv/build/py.typed checks | verified | b683229 |
| G9 | Micro-package hygiene uncertain | P2 | Packaging 2 | boundary evidence | hypothesis | pending |
