# Open Table Connector — Critical Review

**Date:** 2026-08-31
**Scope:** all 12 workspace packages (~26k LOC, 193 files), `specification/` (11 JSON Schemas, conformance suites, fixtures, compatibility attestation), the four design docs under `docs/superpowers/`, and workspace-level engineering (packaging, docs, hygiene).
**Method:** five parallel deep reviews (core contract/timeseries, connector implementations, CLI + process transport, specification/conformance, workspace engineering), with suspected bugs verified empirically against the repo's own venv where possible. Findings marked **[verified]** were reproduced by running code; the rest are by inspection.

---

## Executive summary

This is a genuinely disciplined codebase in its contracts: closed wire schemas, frozen dataclasses with aggressive validation, consistent credential hygiene, and design docs of unusual rigor. The local-files managed snapshot store is the strongest module in the workspace — real crash consistency (fsync + atomic rename + directory fsync), content addressing, and fault-injection tests on both sides of the pointer swap.

But the project's **central value proposition is verifiable evidence** — receipts, capability attestations, conformance certification — and almost every link in that evidence chain is currently self-referential or broken:

1. **The reference evaluator fabricates receipt fields** to satisfy its own invariants (`examined_rows` inflated, connector identity invented from the URI scheme).
2. **The conformance oracle is the implementation under test.** Expected values are computed at test time from the Polars executor; there are no pinned golden results. If the oracle drifts, everything "passes" together.
3. **Providers are labeled `offline_verified` on the strength of permissive fakes** — the Postgres stub regex-extracts column names and returns all rows regardless of the WHERE clause, and the one real-database test is env-gated and evidently never run (it would fail; see finding C4).
4. **The attestation YAML's evidence hashes are referenced by zero code**, the pinned surface commit is already stale, and the document has duplicate keys inside a "closed v1" format.
5. **The spec is not independently implementable.** There is no normative semantics prose; both content hashes are Python/pyarrow-byte-specific; only the request half of the process protocol has a schema — yet the compatibility file pins a Rust sister implementation.

Alongside that theme, the review found **real data-corruption and data-loss bugs** (silent row loss in DST gap-fill, a COUNT that ignores its column, a SQLite time-unit mismatch that silently filters out all rows at non-nanosecond precision, `if_exists="error"` that overwrites), a **Postgres snapshot-read path that cannot work against a real server**, and **workspace engineering far behind the "independently released" claim** (two packages can't install standalone, no LICENSE, no CI, and the documented setup command uninstalls the workspace).

Nothing here is unsalvageable — the architecture is coherent and most fixes are localized. The priority order should be: (P0) the silent-wrong-results bugs, (P1) making the verification story honest, (P2) the copy-paste debt and CLI consistency.

---

## Cross-cutting themes

### T1. The evidence chain doesn't verify what it claims

- `evaluator.py:185` sets `examined_rows = max(examined_rows, returned_rows)` because the receipt invariant `returned <= examined` is violated by gap-fill's fabricated rows — so the receipt reports work that never happened **[verified]**. `evaluator.py:538` mints `ConnectorIdentity(request.target.scheme, "0.1.0", "1.0")` out of thin air.
- `specification/conformance/timeseries/conftest.py:52` computes `expected` by running the Polars executor in the same process. Parity is certified against the implementation, not the spec.
- The vendored golden corpus (`specification/fixtures/timeseries/v1/*.json` — calendar buckets, `America/New_York`, linear fill) is only schema-validated, never executed. The features most likely to diverge across implementations have zero conformance execution.
- `specification/compatibility/ots-otc-timeseries-v1.yaml`: `corpus_hash` and per-provider `evidence_hash` values are computed over unspecified bytes and checked by no code; `otc_surface_commit: 755de59` was already invalidated by commit `974d332` touching `specification/`. Commit-hash pinning guarantees perpetual re-attestation churn (two "docs: attest" commits in the last 30).
- `test_suite_count.py` gates on "≥120 collected tests" — a quantity target (straight from the design doc's acceptance criteria) that is trivially inflatable and detects nothing behavioral.

**Recommendation:** pin golden expected outputs (Arrow IPC or JSON rows, hashed in the manifest) next to the plan fixtures; drive the semantic matrix from the vendored corpus; make receipts report true values (relax the invariant — gap-fill legitimately returns more than it examines); take connector identity as a constructor argument; define what each attestation hash covers and add a CI verifier; attest against tags, not commits; replace the count gate with a checked inventory of required case IDs.

### T2. Copy-paste connector cores that have already diverged

`postgres/temporal.py` (970 lines) and `sqlite/temporal.py` (855) are 54% line-identical; readers 67%; `_read_artifact` exists four times (postgres, sqlite, maybe_sheet, local_files). The cost is not hypothetical: `_observed_range` was fixed to be precision-aware in `local_files/managed_snapshots.py:762` but both SQL copies (`postgres/temporal.py:947`, `sqlite/temporal.py:839`) still assume nanoseconds, so their readback receipts are wrong by up to 10⁹ for non-ns columns. `local_files` already demonstrates the right shape (a shared `ManagedSnapshotStore` parameterized by codec); the SQL stores need the analogous extraction — a shared managed-store core parameterized by a small dialect object (placeholder style, upsert clause, lock statement) plus one shared secure-artifact reader in `timeseries`.

### T3. Wire rigor far exceeds runtime rigor

The contracts reject a stray bool in an int field, but the evaluator computes the wrong aggregate for `count(value_field)` and loses rows across DST transitions. The pattern suggests contracts were designed and validated hard first, and the evaluator was written to pass happy-path tests. The highest-leverage testing investment is adversarial/property-based testing of the evaluator and bucket arithmetic (pure integer math, ideally suited to it) — plus fixtures at every timestamp precision, not just nanosecond.

### T4. The spec is the code

A second implementer (the Rust OTS side implied by `runtime_ranges: rust: ">=1.98"`) cannot derive from `specification/` alone: as-of tie-breaking, bucket-boundary exclusivity, that `linear` fill is Polars positional (not time-weighted) interpolation, the response envelope shape, per-operation payload schemas, or the canonical byte streams behind `portable_plan_hash` and `temporal_descriptor_hash`. The descriptor hash embeds Arrow IPC flatbuffer bytes (`descriptor.py:154-175`), which are **not stable across pyarrow 14→19, let alone arrow-rs** — cross-language hash agreement, the heart of the interop story, will break.

### T5. Workspace engineering lags the claims

"Independently released, framework-neutral" packages with: no LICENSE anywhere; two connectors (`google_sheets`, `feishu_bitable`) declaring **zero dependencies** while importing polars/pyarrow/contract (their wheels fail at import in a clean venv); exact `==0.1.0` inter-package pins that force lockstep releases; no tags, no CHANGELOG, no publish workflow, no CI, no lint/typecheck config, no `py.typed`; and docs whose first dev command (`uv sync --dev`) **uninstalls all 12 workspace packages** (verified via `--dry-run`; the correct command is `uv sync --all-packages --dev`). The README's flagship rule — "framework packages are never dependencies of the neutral packages" — has an enforcement helper that is only ever run against `tmp_path` fixtures, never the real packages.

---

## A. Correctness — silent wrong results and data loss (P0)

| # | Finding | Where |
|---|---------|-------|
| A1 | **[verified]** Calendar-bucket chaining drifts after DST spring-forward; GapFill's left join then **silently drops source rows** (Santiago fixture: row present in range, absent from output, receipt reports nothing) | `timeseries/buckets.py:52-70`, `timeseries/evaluator.py:379,397-423` |
| A2 | **[verified]** `count` with a `value_field` returns total row count (`pl.len()`), not non-null count — any SQL-lowering provider will disagree on the same plan | `timeseries/plan.py:263-269`, `evaluator.py:332-334` |
| A3 | SQLite temporal WHERE clauses compare **nanosecond** thresholds against **descriptor-precision** columns — for any non-ns precision, silently filters out all rows or misbuckets aggregates. Untestable today: every fixture in the workspace is nanosecond | `sqlite/temporal.py:225-230` vs `:751-761` |
| A4 | Postgres `readback()`/`read_snapshot()` run `SET TRANSACTION ISOLATION LEVEL` **after** five DDL statements in the same transaction — PostgreSQL error 25001; the entire snapshot-read half of the managed lifecycle is dead against a real server. Invisible because recording fakes accept any SQL and the live test is env-gated | `postgres/temporal.py:565,594,677` |
| A5 | `_observed_range` in both SQL stores formats every column as ns (receipt evidence wrong by 10³–10⁹ for s/ms/µs); the local_files copy was fixed, the copies weren't (see T2) | `postgres/temporal.py:947`, `sqlite/temporal.py:839` |
| A6 | `if_exists="error"` — the safety mode — **overwrites** on Google Sheets (falls through to PUT/replace) and **appends** on Feishu. Neither suite tests it. Postgres/SQLite implement it correctly | `google_sheets/connector.py:156-166`, `feishu_bitable/connector.py:158-166` |
| A7 | CLI CSV emitter routes cells through Markdown escaping (`\|` → `\\|`, newline → `\n`), corrupting values in `inspect`/`list`/summary CSV; row-data CSV uses a different, correct writer — two divergent CSV semantics in one package | `cli/output.py:54,110` |
| A8 | **[verified]** `arrow_content_fingerprint` hashes raw IPC stream bytes → equal tables with different chunking get different fingerprints; this primitive feeds readback verification and cross-framework parity | `contract/fingerprints.py:20-24` |
| A9 | Receipt honesty: `examined_rows` inflated to satisfy invariant; connector identity invented (see T1) | `evaluator.py:185,538` |
| A10 | `--from-format csv/excel/table` is **silently ignored** for local file paths — a content probe decides instead (honored only for stdio and json/jsonl; rejected loudly for connectors) | `cli/adapters.py:409-421` |
| A11 | SQLite qualified reads broken: the whole dotted name is quoted as one identifier, so the dataclass's own default `table="main.table"` cannot read itself | `sqlite/reader.py:79,213` |
| A12 | Google Sheets `#gid=` fragment (numeric worksheet id) is passed as the sheet **title** — normal shared URLs fail or read the wrong sheet | `google_sheets/connector.py:111` |
| A13 | `output_order` never validated against the operation's output shape — declared-but-absent fields escape as raw polars `ColumnNotFoundError` instead of `PROTOCOL_INVALID` **[verified]** | `plan.py:667-711`, `evaluator.py:426-442` |
| A14 | `sqlite:///:memory:` managed store opens a fresh empty DB per `_connection()` — all state silently lost between calls; should be rejected | `sqlite/temporal.py:825` |
| A15 | SQLite fixed-bucket arithmetic truncates toward zero — timestamps before the origin round **up**, diverging from Postgres `date_bin`; ns calendar origins silently truncated to µs despite plan validation demanding 9-digit fractions | `sqlite/temporal.py:151`, `timeseries/buckets.py:117-119` |

## B. Process transport (P0/P1)

The framed local transport is the wire other products will pin against, so robustness gaps here are contract gaps:

- **B1.** Frame header read is not short-read safe: `stream.read(4)` returning 1–3 bytes (legal on raw pipes) is treated as fatal corruption and kills the server, while the payload path correctly uses `_read_exact` (`process/framing.py:40-44`).
- **B2.** A handler result that fails JSON serialization is **silently dropped** on the worker path (future exception never inspected — client hangs to timeout) and on the inline path propagates an **unredacted traceback** to real stderr, bypassing the entire `BoundedDiagnostics`/redaction machinery (`process/server.py:395-420`, `process/__main__.py:24-31`).
- **B3.** Unbounded growth: `_messages`/`_sessions`/`_cancelled` are never pruned, and the read loop enqueues 16 MiB frames ahead of 4 workers with no backpressure — frame *size* is capped, frame *backlog* is not; that is the actual DoS surface (`server.py:82-99,403-420`).
- **B4.** The cancel/abort callback runs while holding the global state lock on the read-loop thread — the operation meant to unwedge a stuck server can freeze frame intake and every worker (`server.py:90-99,224-229`).
- **B5.** `"ok" in payload` is the request/response discriminator — key-sniffing that misroutes any request payload containing an `ok` field; use an explicit direction field (`process/envelope.py:126-138`).
- **B6.** Failed HELLO/CANCEL permanently burns the `message_id` (retry gets "already used"); rejected envelopes get no NACK frame at all; `BoundedDiagnostics` has a 16 KiB **lifetime** budget after which a long-lived server goes permanently mute (`server.py:90-110,353-374,412-415`).

## C. Specification & conformance (P1)

- **C1.** No normative semantics document — tie-breaks, grouping, bucket boundary rules, fill definitions, null ordering live only in `evaluator.py` (see T4).
- **C2.** Conformance expected values computed from the reference implementation at runtime; vendored fixture corpus never executed; the suite imports **package unit-test internals** (`conftest.py:31-38` imports `packages.local_files.tests.test_temporal_csv` etc.), so it cannot be pointed at a second implementation and refactoring unit tests silently rewrites the corpus.
- **C3.** Hash canonicalization unspecified and non-portable: `portable_plan_hash` = sha256 of Python `json.dumps(sort_keys=True)` (inherits Python float repr); `temporal_descriptor_hash` embeds Arrow IPC schema bytes (`plan.py:639`, `descriptor.py:154-175`). Specify RFC 8785-style canonical JSON and hash a defined *logical* schema encoding (name/type/nullability tuples), not IPC flatbuffers.
- **C4.** `postgres`/`maybe_sheet` are labeled `offline_verified` on stubs that ignore query semantics — the fake cursor returns all rows regardless of WHERE (`conftest.py:158-206`); a lowering bug is invisible because the connector-side evaluator re-filters. Label these honestly (`stub_verified`) and at minimum assert on generated SQL text/parameters.
- **C5.** Only the request half of the protocol is schema'd: `payload` is an open object; response envelope (`{"ok": ...}`), hello negotiation, and per-operation payload shapes exist only in code and e2e tests (`connector-process-envelope-v1.schema.json:48`).
- **C6.** Wire error codes (`protocol_invalid`, `resource_limit_exceeded`, …) are **outside** the closed 8-code enum of `connector-error-v1.schema.json` — the implementation's own errors don't validate against its own schema.
- **C7.** **[verified]** Schemas are far looser than the implementation: `2026-13-45T25:61:61Z` passes the timestamp pattern; `start > end` ranges pass; `returned_rows > examined_rows` passes; bogus timezones and `replace-latest` without an ingestion field pass the descriptor schema. Documents valid per the published schema get rejected by the reference implementation — the classic two-validators problem. Also: descriptor, capability-manifest, and connector-error schemas have no `schema_version` marker, so they're not self-identifying on the wire.
- **C8.** Capability identity has two representations (combined `id/1.0` string in plans, split fields in manifests) with no stated matching rule, and negotiation is exact-string equality — every minor bump is a breaking change, contradicting the `major.minor` format (`server.py:155`).
- **C9.** `neutralReceipt` and shared `$defs` are copy-pasted across 6+ schema files with no parity test — drift hazard for "closed" definitions.
- **C10.** The "cross-framework" suite doesn't cross frameworks: its YAML manifest (declaring decimal-precision comparisons) is never read by the test, which compares one connector's Arrow vs Polars paths in-process and asserts Excel decimals **as strings**.
- **C11.** Plan schema misses implementation-enforced invariants (duplicate predicates/measure outputs, fills referencing unknown fields, undefined `count(value_field)` semantics — the latter being exactly bug A2). Where JSON Schema can't express a rule, publish a normative MUST-list beside the schema.

## D. Security (P1)

- **D1.** Google Sheets writes use `valueInputOption=USER_ENTERED` → formula injection (`=IMPORTDATA(...)` exfiltration) and type coercion, for cell data that may come from untrusted tables. The workspace *elsewhere* defends against exactly this (local Excel writers force text cells). Use `RAW` (`google_sheets/connector.py:165`).
- **D2.** The Postgres "read-only" query gate (`startswith(("select","with"))`) is bypassable: psycopg2 executes `"SELECT 1; DELETE FROM t"`, and `WITH d AS (DELETE ... RETURNING *) SELECT ...` is a legal writing CTE. Enforce with a read-only transaction or document the query as trusted (`postgres/reader.py:69-70`).
- **D3.** **[verified]** `TableURI` credential scrubbing misses blank-valued params (`?token=&x=1`) and fragments (`#access_token=abc`) — the class's one job, enforced only for easy cases (`contract/uri.py:36-37`).
- **D4.** **[verified]** `ResolveContext.credentials` participates in the dataclass repr → raw credentials in logs/tracebacks; the timeseries package already uses `repr=False` for the same concept (`contract/resolve.py:28-31`).
- **D5.** maybe_sheet: env-key sanitization collides (`api-key` and `api_key` → same env var, silent overwrite); capability cache keyed on `id(client)` can hand a recycled address another client's proven capability set (`maybe_sheet/process.py:36-41`, `maybe_sheet/temporal.py:103-133`).
- **D6.** Bootstrap config: lstat-then-open TOCTOU (open with `O_NOFOLLOW` + `fstat`), and the subprocess binary may be a bare name resolved via inherited `PATH` with credential env vars passed down — require an absolute path (`process/bootstrap.py:141,155-164`).
- **D7.** `redact_text` misses JSON-style `"token": "..."` secrets; conversely `assert_receipt_safe` substring-scans the whole document and fails any receipt mentioning a table named `tokens` **[verified]** — over- and under-matching in the same subsystem.

## E. Design & API consistency (P2)

- **E1.** `--output-format` means three different things by subcommand (stdout encoding for `read`/`list`; summary encoding for `import`; destination file codec for `convert`, whose stdout summary is hard-forced JSONL) — and `convert --to dest.json --output-format table` writes a Markdown table into a `.json` file, pinned by a test. Reintroduce a destination-format flag for `convert`.
- **E2.** `read` and `convert` emit different JSONL for identical data (timestamp formats differ; NaN → `null` vs hard failure) — both behaviors pinned by tests. Route both through one codec.
- **E3.** Resource-limit semantics drift: `max_rows` silently truncates in six readers but hard-errors in json_connector and every temporal executor; truncating receipts carry no truncation marker, so a partial read is indistinguishable from a complete one. Pick one semantic in the contract; if truncation is allowed, record it in the receipt.
- **E4.** `BaseCoordinate` accepts conflicting identities and `to_wire()` silently drops the key **[verified]**; `Decimal("1.5")` and `"1.5"` collide in wire identity; no `from_wire` for coordinates (one-way contract) (`contract/coordinates.py`, `scalars.py`).
- **E5.** `NeutralReceipt` accepts any string for fingerprints while `TemporalReceipt` requires `^sha256:[0-9a-f]{64}$` — two rigor levels for the same concept in one wire family.
- **E6.** Conformance mandates `VisibilityGuarantee.ATOMIC`, making the schema-legal `non_atomic` value uncertifiable — either dead enum or wrongly rejected implementations; abort-before-commit is never exercised (`conformance/timeseries.py:99`).
- **E7.** CLI scheme surface inconsistent: `json://`/`jsonl://` are accepted by format inference but no adapter advertises them and `_is_local` excludes them → both `read` and `convert` fail on these documented-looking schemes; an explicit `--output-format` is silently overridden by the destination scheme.
- **E8.** Endpoint/format `ValueError`s (already credential-safe by construction and test) are flattened to `{"code":"usage","message":"invalid command input"}` — zero actionable detail (`cli/output.py:223-225`).
- **E9.** `ConnectorError` defaults store a list in a `Mapping`-typed field, and `_safe_value` drops legitimate `None` values indistinguishably from redaction (`contract/errors.py:33-50`).
- **E10.** **[verified]** `ArrowTableReader & PolarsTableReader` is an invalid type expression surviving only via lazy annotations; `typing.get_type_hints` raises on the conformance package's flagship entry point (`conformance/assertions.py:55`).
- **E11.** Capability naming is inconsistent inside one package: `capabilities.py` uses `"timeseries.scan.range/1.0"` strings, the evaluator emits `CapabilityIdentity("timeseries.scan.range", "1.0")`.
- **E12.** CLI registry: hardcoded per-connector https hosts, first-match-wins with silent shadowing, and three adapter `write` methods unreachable from any command (dead weight).

## F. Performance (P2)

- **F1.** The evaluator serializes tables to IPC up to four times per execution (byte-counting twice, receipt hashing twice) and computes bucket labels with a per-row Python loop (calendar path: regex parse + 4 tz conversions per row) — a million-row aggregation is minutes, not milliseconds (`evaluator.py:119,176-177,300-316,530-531`). Serialize once and reuse; vectorize fixed buckets (`anchor + ((ts-anchor)//width)*width`); compute calendar labels per unique value.
- **F2.** Projection pushdown is defeated: `_required_fields` is computed, then `read_bounded` requests **all** declared fields; the receipt's `source_revision` then hashes the *narrowed* table, making it projection-dependent (`evaluator.py:96-121,530-536`).
- **F3.** CLI materializes everything: whole-file string reads, table → dict-list → Arrow → pylist copies, `--limit` applied by slicing **after** a full read; `if_exists=error` preflight downloads the entire destination to check emptiness — pass `max_rows=1` (`cli/formats.py:136-153`, `cli/adapters.py:148-156,420`).
- **F4.** Feishu `batch_create` is unchunked (provider caps ~500 records/call → wholesale failure); both urllib transports read responses unbounded and collapse 401/403/timeout into one `EXECUTION_FAILED "unexpected transport exception"` — auth failures never map to `AUTHENTICATION`.

## G. Workspace engineering (P0 for the first three)

- **G1.** `packages/google_sheets/pyproject.toml` and `packages/feishu_bitable/pyproject.toml` declare **no dependencies** while importing contract/polars/pyarrow — their wheels fail at import in a clean venv **[verified]**. The workspace masks it; the package boundaries are never install-tested.
- **G2.** No LICENSE anywhere (no root file, no `license` field in any of 13 pyprojects) while the README's first command is `uv tool install open-table-connector`. Also no CHANGELOG, no CONTRIBUTING.
- **G3.** **[verified]** The documented `uv sync --dev` (README, getting-started, user-manual) would uninstall all 12 workspace packages (`--dry-run`: "Would uninstall 22 packages"); the current `.venv` is already broken this way (`open_table_connector.process` missing → 7 pytest collection errors; venv shebangs still point at the pre-rename `open-connectors` path, so `uv run pytest` fails to spawn). Document `uv sync --all-packages --dev` and regenerate the venv.
- **G4.** No CI, lint, typecheck, or pre-commit at all (`.gitignore` lists caches for tools that aren't configured). 765 tests and a cross-repo attestation story, none of it automated. The dependency-direction checker is never applied to the real packages, and nothing checks the intra-workspace DAG.
- **G5.** "Independently released" without release engineering: no tags, all packages frozen at `0.1.0`, inter-package pins `==0.1.0` (forcing lockstep — the opposite of independent trains), `dist/` still holding wheels under the old `open_connectors` name.
- **G6.** Rename residue and junk: dual old/new egg-info pairs inside `src/` trees, root egg-infos, `.DS_Store` (untracked but unignored), `tmp-review-universal/`, and 14 tracked `.superpowers/sdd/` reports despite a `*` gitignore there and a prior commit that removed only some of them.
- **G7.** Stale/conflicting pins: `pyarrow>=14,<20` (lock resolves 19.0.1 — early 2025) blocks coinstallation with modern stacks; the attestation YAML says `polars >=1.43.2` and `python <3.15` while packages say `polars>=1.0` and unbounded `>=3.11` — two sources of truth disagreeing.
- **G8.** Root pyproject builds a pointless empty distribution (`packages = []`); use a uv virtual workspace root. No `py.typed` in any package despite the heavily typed API. Seven of 12 packages have no README; `dbt` — framework-adjacent — is absent from the README package list and depended on by nothing, which sits oddly in a "framework-neutral" workspace.
- **G9.** Micro-packages (`dbt` 277 LOC, `google_sheets` 292, `feishu_bitable` 295) have packaging costs without packaging hygiene; either give them real hygiene (deps, README, py.typed) or fold them into the CLI package until an independent consumer exists.

## H. Test-quality assessment

Genuinely good: CLI credential-redaction and escaping round-trips; local_files crash/fault injection (both sides of the pointer swap, concurrency, traversal, symlinks); closed-schema recursive unknown-field rejection; the universal suite's behavioral assertions.

Systematic gaps, which map directly onto the confirmed bugs:

- Every temporal fixture in the workspace is `NANOSECOND` → A3/A5 are untestable today.
- Calendar/DST coverage exists only for `calendar_bucket_start`; `calendar_bucket_next`/domain chaining (where A1 lives) and gap-fill-with-calendar-buckets have zero tests.
- Postgres temporal is tested only against fakes that accept any SQL; the live test would catch A4 but is env-gated and evidently unrun.
- No tests for: `if_exists="error"` on hosted sheets (A6), CSV cells containing `|`/newlines (A7), fingerprint chunk invariance (A8), short header reads (B1), serialization-failing handler responses (B2), bootstrap permission rejections, `--from-format` on file paths (A10).
- `test_protocols.py` asserts parameter *names* only (near-tautological); no property-based tests for bucket arithmetic despite it being pure integer math.

---

## What is genuinely good

- `local_files/managed_snapshots.py`: fsync'd temp + `os.replace` + directory fsync, content-addressed dedupe, flock serialization, pointer-based crash reconciliation, symlink/ownership/mode/TOCTOU defenses, and real fault-injection tests.
- The wire-contract layer: closed-key `from_wire` everywhere, frozen dataclasses, aggressive `__post_init__` validation, no field-name drift found between `to_wire()` output and schema `required` lists.
- All 11 schemas pass the 2020-12 meta-schema; every vendored fixture validates; `additionalProperties: false` applied consistently including nested defs.
- Credential hygiene as a theme: `TableURI` rejecting embedded credentials at the root, `repr=False` on timeseries credential fields, CLI redaction tests, credential-free bootstrap design.
- Docs accurately describe the CLI surface (all five subcommands, flags, defaults verified against the parser) — the install commands are the weak spot, not the reference content.
- The design docs are unusually rigorous and the built packages match the plans well.

---

## Prioritized action plan

**P0 — silent wrong results, data loss, and broken paths (days):**
1. Fix DST calendar-bucket chaining; make gap-fill's join an outer join or assert domain coverage (A1).
2. Fix or reject `count(value_field)` (A2) and define its semantics in the spec (C11).
3. Scale plan timestamps by descriptor precision in one shared helper; add non-ns fixtures (A3, A5).
4. Fix Postgres `SET TRANSACTION`-after-DDL; run `_ensure_schema` once, in its own transaction; stand up a real-Postgres CI job (A4).
5. Make `if_exists="error"` actually error on Google Sheets/Feishu (A6); switch Sheets writes to `RAW` (D1).
6. Fix the CLI CSV emitter (A7), the frame-header short read (B1), and the swallowed/unredacted serialization failures (B2).
7. Fix the two dependency-less pyprojects, add a LICENSE, correct the `uv sync` docs, regenerate `.venv` (G1–G3).

**P1 — make the verification story honest (1–2 weeks):**
8. Truthful receipts: drop the `examined>=returned` fudge, injected connector identity (A9); chunk-canonical fingerprints (A8).
9. Pin golden expected outputs; execute the vendored fixture corpus; decouple conformance from package unit-test internals (C2).
10. Specify canonical hash inputs (RFC 8785 JSON; logical schema encoding instead of IPC bytes) (C3).
11. Schema completeness: response/per-operation payload schemas (C5), error-code alignment (C6), tightened timestamp/range constraints plus a normative invariant list (C7), `schema_version` on all wire docs, capability matching rule (C8).
12. Re-label stub-verified providers; define and CI-verify the attestation hashes; attest against tags (C4, T1).
13. Minimal CI: `uv sync --all-packages --dev`, pytest, ruff, per-package wheel build + clean-venv import smoke, dependency-direction check over the real packages (G4).
14. Process-server robustness: backpressure and state pruning (B3), callback outside the lock (B4), explicit envelope direction field (B5).

**P2 — structural debt (ongoing):**
15. Extract the shared SQL temporal-store core (dialect-parameterized) and one secure artifact reader (T2).
16. Unify resource-limit semantics with a truncation marker in receipts (E3).
17. CLI: dedicated convert destination-format flag, one codec for read/convert, actionable usage errors, coherent json/jsonl scheme handling (E1, E2, E7, E8).
18. Write the normative semantics document per operation (C1).
19. Performance pass on the evaluator (single serialization, vectorized bucketing, real projection) (F1, F2).
20. Release engineering: compatible-range pins, tags, CHANGELOG, `py.typed`, decide the fate of the micro-packages and `dbt` (G5, G8, G9).
