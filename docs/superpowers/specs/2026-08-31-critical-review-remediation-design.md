# Critical Review Remediation Design

## Status

Approved in chat on 2026-08-31.

The audited code baseline is commit `974d332855d017d955a9b281bb7fd25036eb555d`.
The source review is
`docs/reviews/2026-08-31-critical-review.md`, committed as
`5c82b34a69c10e0874bdfc91cbda47d2dd1553d0`.

This design governs the remediation program created from that review. It
corrects several review recommendations before they become implementation
requirements:

- `count` currently means row count in every implementation. Version 1 will
  document that behavior and reject a non-null `value_field` instead of
  changing one executor to count non-null values.
- Gap-fill retains its domain-left-join shape. Calendar-domain generation is
  fixed at the source and checked for aggregate buckets outside the domain;
  an outer join is not used to hide domain drift.
- Attestations continue to pin immutable commits. Scoped content manifests
  reduce unrelated re-attestation churn; tags do not replace commit pins.
- Process protocol v1 remains wire-compatible. Request and response decoding
  becomes context-specific instead of adding a required `direction` field.
- Cross-version hash instability, million-row runtime, and remote provider
  limits remain hypotheses until a reproducible experiment or authoritative
  source establishes them.

## Decision

Remediate the review through five independently reviewable implementation
plans joined by one evidence ledger and one compatibility policy. Work is
risk-first: normative decisions needed by correctness fixes land first,
silent-wrong-result and data-safety defects land next, and structural or
performance work waits until behavior is protected by regression tests.

The five plan scopes are:

1. correctness and data safety;
2. process transport and security;
3. specification and conformance integrity;
4. packaging, CI, and CLI consistency; and
5. structural and performance improvements.

Plan boundaries are review boundaries, not release branches. Each task must
produce an independently testable commit. A task may depend on an interface
defined by an earlier plan, but it must not mix unrelated cleanup into the
same commit.

## Goals

- Eliminate silent wrong results, data loss, ineffective safety modes, and
  broken managed-storage paths identified by the review.
- Make every compatibility and conformance claim traceable to independent,
  reproducible evidence.
- Preserve version 1 wire compatibility unless the existing wire cannot
  express a safe result; incompatible changes use a separately versioned
  schema and capability.
- Harden local process transport and credential handling without exposing
  secret values in frames, receipts, exceptions, or diagnostics.
- Make every workspace package installable and testable at its declared
  boundary.
- Establish CI gates for schemas, unit and conformance tests, clean-wheel
  imports, dependency direction, and configured live PostgreSQL behavior.
- Unify duplicated implementations only after the regression suite pins
  their intended behavior.
- Replace unsupported performance claims with measured baselines and
  repeatable benchmarks.

## Non-goals

- Do not add native TimescaleDB, ClickHouse, or TDengine features.
- Do not redesign ordinary connector APIs that are unrelated to a reviewed
  defect.
- Do not silently reinterpret a version 1 field to mean something different.
- Do not make hosted-sheet `if_exists="error"` a check-then-write promise when
  the provider cannot enforce atomic create-if-empty behavior.
- Do not treat a tag name as stronger evidence than an immutable commit and a
  verified content manifest.
- Do not optimize evaluator paths before equivalence tests and benchmarks
  exist.
- Do not require a sister repository checkout to run OTC tests.

## Evidence and Tracking Model

The opening task of Plan 3 creates
`docs/reviews/2026-08-31-critical-review-remediation.md`. It contains one row
for every finding and recommendation in the source review with these fields:

- finding identifier;
- evidence class;
- delivery priority;
- owning plan and task;
- regression test or inspection command;
- disposition; and
- resulting commit.

Evidence classes are closed:

- `reproduced`: a command or test demonstrates the behavior on the pinned
  baseline;
- `inspected`: the defect follows from a named code path but was not executed
  against the real dependency;
- `hypothesis`: a benchmark, cross-version matrix, real provider, or external
  source is still required;
- `invalid`: the original statement is contradicted by evidence;
- `superseded`: a narrower, evidence-backed formulation replaces the original
  statement.

Dispositions are `open`, `fixed`, `deferred`, `accepted`, or `invalid`.
`deferred` and `accepted` require a rationale and a named revisit condition.
No finding disappears merely because it is absent from a prioritized summary.

Priority has operational meaning:

- P0 blocks a trustworthy release because it can produce silent wrong data,
  lose data, bypass a declared safety property, expose credentials, or make a
  core advertised path unusable.
- P1 blocks a compatibility or reliability claim but does not silently alter
  ordinary results.
- P2 is maintainability, usability, or measured performance work protected by
  existing behavior tests.

Release hygiene such as a missing license may block publication, but it is
tracked as a release blocker rather than mislabeled as a runtime P0 defect.

## Program Architecture

```text
Pinned audit baseline + critical review
                 |
                 v
        remediation evidence ledger
                 |
       +---------+---------+------------------+
       |                   |                  |
       v                   v                  v
normative semantics   correctness fixes   protocol/security
       |                   |                  |
       +---------+---------+------------------+
                 |
                 v
      independent golden conformance
                 |
       +---------+---------+
       |                   |
       v                   v
 packaging/CI/CLI     structural/performance
       |                   |
       +---------+---------+
                 |
                 v
       verified compatibility record
```

The evidence ledger is the control plane. Code, schema, and documentation
changes remain in their owning packages. The ledger records proof and
disposition but never becomes a second source of behavioral semantics.
Normative semantics live under `specification/`; package tests prove local
implementation; conformance tests prove implementations against vendored
expected results.

## Cross-Plan Compatibility Rules

### Version 1 behavior

Existing valid v1 documents remain valid unless accepting them is itself the
reviewed defect. Tightening a Python constructor without tightening the
corresponding schema is prohibited. Tightening a schema without adding the
same semantic check to the Python codec is also prohibited.

For `AggregateMeasure`:

- `count` is row count, equivalent to SQL `COUNT(*)`;
- `count` requires `value_field` to be null;
- every other aggregate requires a declared value field; and
- duplicate output names remain invalid.

The rule matches existing fixtures and all three current execution paths. A
future non-null count is a new aggregate identity or a versioned plan change.

### Gap-fill domain

Calendar bucket generation must satisfy these invariants across supported
timezones and DST transitions:

- each next label is strictly greater than the current label;
- applying bucket-start to a generated label returns the same label;
- every aggregate bucket inside the half-open request range belongs to the
  generated domain; and
- the final output row count is checked after joining and filling.

The expanded domain remains the left side of the join. A bucket outside the
domain raises a stable protocol/execution error during development and is
prevented by the corrected bucket implementation in released code.

### Timestamp precision

One shared conversion module maps RFC 3339 UTC timestamps to and from the
descriptor's second, millisecond, microsecond, or nanosecond storage unit.
SQLite lowering, SQLite managed reads, PostgreSQL receipts, and local-file
receipts consume that module. No provider-local helper assumes nanoseconds.

### Process protocol

`otc.connector-process/v1` keeps its existing wire fields. The implementation
introduces distinct request and response decoders selected by transport
context. A server never guesses direction from payload keys. Payload schemas
become operation-specific and closed.

The server adds bounded work admission, completed-state pruning, cancellation
outside the global lock, and a result-observation path that converts handler
and serialization failures into bounded redacted responses. Rejected frames
or envelopes receive a response only when enough valid envelope identity is
available; raw malformed bytes remain bounded diagnostics.

### Hashes and attestations

Current hash behavior remains v1 until evidence establishes an interoperability
failure. The conformance plan first builds a Python-version/PyArrow-version
matrix and, when the sister implementation is available, compares Arrow Rust
outputs. If bytes differ for logically equal inputs, a new logical canonical
hash format is specified with fixtures and a versioned identity. Existing v1
hashes are not silently redefined.

Compatibility records pin:

- the exact OTC commit;
- the exact sister-product commit when applicable;
- a manifest hash over named normative schemas and fixtures; and
- per-provider evidence artifacts with defined byte inputs.

CI recomputes every hash. A manifest changes only when a file in its declared
surface changes, avoiding churn from unrelated documentation or CLI commits.

### Provider write safety

Google Sheets writes use raw value input. Feishu and Google connectors
advertise only policies they can enforce. If a provider lacks atomic
create-if-empty, `if_exists="error"` fails before mutation with a stable
unsupported-capability error. A read-before-write probe is not described as
atomic safety.

SQL read-only execution is enforced by database transaction controls rather
than a string prefix check. Qualified identifiers are parsed into validated
components and quoted component-by-component.

## Plan 1: Correctness and Data Safety

This plan owns A1-A15 after applying the corrected A2 and A1 formulations.
It begins after Plan 3 delivers the normative COUNT rule and gap-fill
invariants.

Delivery slices are:

1. calendar-domain and DST regression fixtures, bucket progression, domain
   membership assertion, and post-join row bound;
2. COUNT validation and parity across Polars, SQLite, and PostgreSQL;
3. descriptor-precision conversion shared by SQLite filtering and SQL/local
   observed-range receipts;
4. PostgreSQL schema initialization separated from repeatable-read snapshot
   transactions, verified against a real PostgreSQL service;
5. hosted write-policy enforcement and Google Sheets raw values;
6. CSV cell encoding through the real CSV writer without Markdown escaping;
7. canonical content fingerprint behavior for equal chunked tables, versioned
   if the corrected bytes change a public identity;
8. truthful receipt accounting and injected connector identity;
9. explicit local input-format routing;
10. component-wise SQLite qualified names and rejection of managed
    `:memory:` stores;
11. Google `gid` resolution through sheet metadata rather than treating an ID
    as a title;
12. output-order validation with stable protocol errors; and
13. floor-division fixed buckets plus precision-safe calendar origins.

Every slice starts with a focused failing regression. Data-changing fixes add
cross-provider parity coverage when more than one executor implements the
operation.

## Plan 2: Process Transport and Security

This plan owns B1-B6 and D1-D7, except hosted-write changes already delivered
with Plan 1 are referenced rather than duplicated.

Delivery slices are:

1. exact-length frame-header reads and adversarial segmented-stream tests;
2. observed worker futures and redacted serialization-failure responses;
3. bounded queue admission and pruning for messages, sessions, and cancelled
   operations;
4. cancellation callbacks executed outside the state lock;
5. context-specific v1 request/response decoders and closed operation payloads;
6. stable negative acknowledgements and reusable identifiers for requests
   rejected before admission;
7. database-enforced PostgreSQL read-only execution;
8. URI rejection for blank secret parameters and secret fragments;
9. secret-free `ResolveContext` representations;
10. collision-free MaybeSheet credential environment keys and weak-reference
    or object-keyed capability caching;
11. descriptor-relative, no-follow bootstrap file opening with post-open
    metadata validation and absolute executable paths; and
12. structured redaction that recognizes JSON secrets without substring
    false positives in safe identifiers.

Memory and concurrency tests use deterministic barriers and bounded fake
streams rather than timing-sensitive sleeps.

## Plan 3: Specification and Conformance Integrity

This plan owns T1, T4, and C1-C11. Its first task is a prerequisite for Plan
1; its remaining tasks run after the P0 regression fixes so golden outputs
capture corrected behavior.

Delivery slices are:

1. the pinned remediation ledger and corrected evidence classifications;
2. normative v1 semantic errata for COUNT, half-open ranges, duplicate
   resolution, ordering, bucket boundaries, fill behavior, and null handling;
3. pinned input and expected-output fixtures independent of the reference
   evaluator;
4. conformance fixtures that do not import package unit-test internals;
5. response, hello, cancellation, and per-operation process schemas;
6. one closed, shared error-code vocabulary across schemas and code;
7. schema/Python parity for timestamps, ordered ranges, receipt counts,
   timezones, descriptor invariants, and schema-version markers;
8. one capability identity representation and a documented compatibility
   rule;
9. generated or referenced shared schema definitions with parity tests;
10. a real cross-framework manifest-driven suite with typed decimal
   comparisons;
11. explicit semantic invariant lists for rules JSON Schema cannot express;
12. empirical cross-version and cross-language hash fixtures;
13. defined compatibility-manifest and provider-evidence hash inputs; and
14. CI verification of the complete compatibility record.

Provider status distinguishes unit, recording-stub, configured-live, and
cross-implementation evidence. A permissive fake cannot produce a live or
offline-real-provider claim.

## Plan 4: Packaging, CI, and CLI Consistency

This plan owns E1-E12 and G1-G9. Its environment bootstrap instructions may
run before other plans, but behavior changes wait until Plans 1-3 establish
their contracts.

Delivery slices are:

1. correct dependencies for every independently built wheel and clean-venv
   import smoke tests;
2. repository license metadata and publication documentation;
3. correct workspace synchronization commands and a virtual workspace root;
4. CI for supported Python versions, schemas, pytest, lint, type checking,
   package builds, dependency direction, and configured PostgreSQL;
5. compatible inter-package ranges and release metadata without stale build
   artifacts;
6. removal or ignoring of rename residue and generated workspace junk without
   deleting user artifacts;
7. one supported-version source rendered into package and compatibility
   metadata;
8. `py.typed` and package README coverage or an explicit decision to fold a
   micro-package into an owning distribution;
9. separate stdout presentation format from convert destination codec;
10. one JSON/JSONL and CSV codec path for equivalent data;
11. one documented resource-limit semantic with an explicit truncation marker
    if truncation remains supported;
12. coordinate and receipt validation parity;
13. actionable credential-safe CLI usage errors;
14. coherent local `json://` and `jsonl://` routing; and
15. explicit adapter registry collision errors plus removal or exposure of
    unreachable write methods.

The package-folding decision is evidence-based: retain a package when it has
an independent consumer or release reason; otherwise fold it without changing
the public CLI surface.

## Plan 5: Structural and Performance Improvements

This plan owns T2 and F1-F4 and starts only after all affected behavior has
regression coverage.

Delivery slices are:

1. extract a shared precision-safe artifact reader;
2. extract a managed SQL store core parameterized by a small SQLite/PostgreSQL
   dialect interface;
3. serialize evaluator inputs and outputs once per execution and reuse the
   measured bytes and fingerprints;
4. vectorize fixed buckets and compute calendar labels per unique timestamp;
5. pass the real required projection to bounded sources and define a
   projection-independent source revision;
6. stream or incrementally bound CLI reads and apply existence probes with a
   one-row request;
7. validate the official Feishu batch limit, then chunk writes to the sourced
   limit with bounded responses and typed provider error mapping; and
8. publish repeatable benchmark inputs, environment metadata, and before/after
   results.

Refactoring follows characterization tests. Provider dialects contain only
placeholder style, quoting, transaction setup, upsert/current-pointer SQL,
and capability differences; lifecycle policy remains in the shared core.

## Delivery Order and Gates

1. Synchronize the environment with all workspace packages and record the
   pinned baseline without changing product behavior.
2. Create the remediation ledger and classify every finding.
3. Deliver Plan 3's normative semantic errata.
4. Deliver Plan 1 in independent red-green slices.
5. Deliver Plan 2 in independent security and transport slices.
6. Complete Plan 3's golden corpus, schema closure, and compatibility checks.
7. Deliver Plan 4, running package and CLI changes behind the established
   conformance gates.
8. Capture performance baselines, then deliver Plan 5.
9. Re-run the complete ledger, configured-live jobs, clean-wheel matrix, and
   compatibility-manifest verifier.

A gate fails when a required command cannot run. Environment breakage is not
reported as a product-test failure, but it must be fixed or isolated before
the task proceeds. Provider-live jobs may be conditional on configured
credentials, but a provider cannot claim configured-live status when the job
did not run.

## Testing Strategy

### Unit and property tests

- Boundary arithmetic covers timestamps before and after origins, every
  precision, negative epochs, month ends, leap years, and DST gaps/folds.
- Contract tests reject unknown fields, bool-as-int values, duplicate names,
  invalid ranges, and unsafe credentials.
- Process tests cover segmented reads, malformed UTF-8/JSON, duplicate keys,
  queue saturation, cancellation races, handler exceptions, and
  serialization failures.

### Provider tests

- Recording fakes assert exact SQL, parameters, HTTP method, URL, bounded body,
  and timeout behavior.
- SQLite tests exercise seconds, milliseconds, microseconds, and nanoseconds.
- PostgreSQL managed lifecycle runs against a real supported server in CI.
- Hosted connectors test every advertised `if_exists` policy before mutation.

### Conformance tests

- Expected outputs are vendored data, never computed by the implementation
  under test during the test run.
- The fixture manifest is consumed by the suite.
- Provider labels state exactly which evidence tier passed.
- Schema fixtures validate with JSON Schema and round-trip through Python
  codecs.

### Packaging and release tests

- Every wheel builds and imports in a clean environment with only declared
  dependencies.
- The real package dependency graph is checked, not only synthetic fixtures.
- CI runs the documented setup path.
- Compatibility hashes are recomputed from their declared file lists.

### Performance tests

- Benchmarks record Python, PyArrow, Polars, CPU, row count, schema, chunking,
  and operation.
- Correctness comparisons run before timing comparisons.
- Results report measured distributions; no unmeasured latency claim is a
  release criterion.

## Commit and Review Strategy

Each implementation task follows strict red-green-refactor:

1. commit or show the failing regression when practical;
2. implement the minimum coherent fix;
3. run focused tests and the owning package suite;
4. run `git diff --check`;
5. update the evidence ledger; and
6. create one Conventional Commit.

Schema and code changes that define one behavior land together. Broad
mechanical refactors do not share commits with semantic fixes. Generated
artifacts are committed only when the repository treats them as release
inputs and their generator/check command is documented.

## Completion Criteria

The remediation program is complete only when:

- every source-review finding has a terminal ledger disposition;
- every fixed P0/P1 finding has a regression or a reproducible verification
  command;
- invalid or superseded findings contain evidence and corrected wording;
- all schemas and Python codecs agree on accepted documents;
- conformance expected values are independent of the implementation under
  test;
- advertised live-provider claims have current live evidence;
- every package passes clean-wheel import testing;
- the documented setup command is exercised by CI;
- the compatibility manifest verifier passes on the exact release commit;
- performance statements cite current benchmark artifacts; and
- the full test, schema, package, and lint/typecheck gates pass with zero
  unexplained skips.

## Implementation Plan Outputs

After user review of this written design, the writing-plans workflow creates:

- `docs/superpowers/plans/2026-08-31-critical-review-correctness-data-safety.md`;
- `docs/superpowers/plans/2026-08-31-critical-review-process-transport-security.md`;
- `docs/superpowers/plans/2026-08-31-critical-review-specification-conformance.md`;
- `docs/superpowers/plans/2026-08-31-critical-review-packaging-ci-cli.md`; and
- `docs/superpowers/plans/2026-08-31-critical-review-structure-performance.md`.

Each plan repeats the relevant global constraints, names exact files and
interfaces, gives runnable red-green steps, and identifies cross-plan
prerequisites explicitly.
