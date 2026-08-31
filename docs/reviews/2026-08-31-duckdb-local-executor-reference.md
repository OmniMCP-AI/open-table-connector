# Deferred DuckDB Local Executor Reference

**Status:** non-normative research note. It does not change the approved
SQL Lite v1 contract or add a runtime dependency.

## Decision

SQL Lite v1 remains:

```text
SQLGlot parser -> OTC Portable Plan -> PolarsPlanMapper -> Polars/Arrow result
```

SQLGlot is parse-only. The OTC-owned, versioned portable plan defines the
grammar, types, resource policy, plan hash, and semantics; the third-party AST
does not. `PolarsPlanMapper` is the only normative local evaluator in v1.

DuckDB is a deferred, non-normative implementation candidate. Its future seam
is deliberately below the portable plan:

```text
OTC Portable Plan -> DuckDB lowerer -> Arrow RecordBatchReader -> Polars frame
```

The lowerer must consume only a validated plan and typed parameter values. It
must register already-authorized Arrow/Polars inputs under generated internal
names, never let SQL text discover a URI, file, network location, extension,
or catalog object. DuckDB's efficient Arrow/Polars interoperability and
Arrow-batch output make this a credible future implementation
([DuckDB Polars integration](https://duckdb.org/docs/current/guides/python/polars),
[Python relational output](https://duckdb.org/docs/stable/clients/python/relational_api)).
They do not make DuckDB SQL the OTC language.

## Why it is deferred

- DuckDB could improve local joins, sorting, grouping, and large Parquet/Arrow
  execution while retaining an Arrow/Polars boundary. The benefit must be
  demonstrated against the bounded Polars baseline; it is not a reason to
  expand SQL Lite.
- Its SQL defaults are not OTC semantics. Null ordering, collations, decimal
  widening/rounding, floating-point values, casts, timestamp precision and
  timezone handling, aggregate/window behavior, ordering ties, and calendar
  buckets must be lowered explicitly or rejected. DuckDB-only syntax,
  functions, ASOF joins, `read_*`, macros, extensions, and native SQL are not
  portable-plan nodes.
- DuckDB's configuration limits are necessary but insufficient. Its documented
  `memory_limit` applies only to the buffer manager, and its default temporary
  storage allowance is much broader than OTC can accept
  ([limits](https://duckdb.org/docs/current/operations_manual/limits)). The
  lowerer must separately enforce OTC input rows, output rows, bytes, duration,
  and cancellation, and run with bounded threads, memory, temporary-directory
  size, and a deployment-owned temporary directory.
- Never execute caller SQL. DuckDB documents that untrusted SQL and even
  non-SQL paths or expressions can read files, access the network, or consume
  resources; its settings are defense in depth rather than a sandbox
  ([security guidance](https://duckdb.org/docs/current/operations_manual/securing_duckdb/overview)).
  A future implementation therefore disables external access, extension
  autoload/install and community extensions, prohibits secrets and arbitrary
  `ATTACH`/`COPY`/`read_*`, locks configuration, uses prepared value bindings,
  and runs inside an OS/container sandbox. No security setting substitutes for
  the sandbox.
- The native Python wheel and its Arrow/Polars integration are an optional,
  version-pinned package concern, not a core SDK dependency. Any future extra
  must declare compatible DuckDB, Polars, and PyArrow ranges; install and
  import tests must cover every supported platform.

## Capability and receipt rules

There is **no DuckDB capability in v1** and no public `engine=` option. Normal
`pushdown` continues to mean certified execution by the physical provider; a
local DuckDB lowerer is connector-side execution and must never be reported as
provider pushdown.

If a later plan version admits it, the public semantic capability remains the
same versioned SQL Lite query capability. DuckDB may have an internal
implementation identity only after the gates below pass. The SDK still selects
it internally from the complete plan, source kinds, policy, and configured
limits; callers cannot force it and there is no silent fallback after it has
selected DuckDB for a certified execution. A missing optional package or an
unsupported plan fails before data-bearing I/O (or the normal Polars path is
chosen *before* execution under the ordinary policy).

The result remains the normal OTC `OperationResult[DataFrame]` with plural
physical `Receipt` entries, not a DuckDB relation or a DuckDB-specific result
type. It must retain the portable plan hash, SQL Lite version, source read
receipts and pinned snapshots, normalized output schema/order/content facts,
enforced limits, warnings, and `execution_location="connector"`. A future
receipt may add a safe `local_evaluator="duckdb"` fact; it cannot replace source
physical receipts or imply provider pushdown, provider transaction semantics,
or portable semantics for native SQL.

## Admission gates

A DuckDB lowerer is admissible only when all of the following are true:

1. It lowers the closed portable plan, not SQLGlot ASTs or SQL strings, and
   rejects every unsupported node before source data is read.
2. Differential conformance against `PolarsPlanMapper` passes the full SQL Lite
   corpus for each declared scalar, null behavior, type/overflow rule,
   projection, predicate, aggregate, join, set operation, total ordering,
   limit, and allowed window frame. Results, errors, order, schema, and
   receipt facts must agree.
3. Temporal admission is separate: range boundaries, UTC precision, duplicate
   policy, latest/as-of ties, fixed and calendar buckets across DST, and every
   fill rule must match. Until then DuckDB is unavailable for temporal plans.
4. Adversarial tests prove no SQL/file/network/extension/secret escape, no
   ambient-Python-frame discovery, redacted diagnostics, and no configuration
   mutation across requests. Tests also prove cancellation, time/memory/temp
   limits, cleanup, and bounded Arrow batch output under joins/sorts/spills.
5. Reproducible benchmarks establish a material benefit on declared workload
   classes without weakening limits or receipts. The optional package's exact
   supported versions and platform installs are tested in CI.

Only these gates can make DuckDB a future certified local implementation. They
cannot change v1 SQL Lite, widen a provider's advertised capability, or permit
a fallback that changes observable semantics.
