# OTC Python SDK implementation plan

> Execution rule: implement each task test-first. After each task, run its focused tests and review the diff before continuing. Keep the public surface small and preserve compatibility with the existing connector packages.

## Goal

Implement the pure-Python OTC SDK agreed in the architecture docs. The SDK normalizes table operations across base-mode and sheet-mode connectors, uses Polars DataFrame as the concrete data value, exposes SQL and time-series queries, and provides one operation-result/receipt model. The CLI becomes a thin demonstration wrapper. The Rust/OTS bridge remains deferred to its separate design.

## Global constraints

- Table is the only public physical connector-backed handle. polars.DataFrame is the in-memory value. Query is the only deferred table-producing value.
- Do not add TableRef, TableHandle, logical Table, MaterializedTable, Table.frame(), clear(), append(), replace(), or a copy-result type.
- Mutations are insert, keyed update, required-predicate delete(where=...), and drop; Client.materialize(source, to=...) is create-only and conflicts if the destination exists.
- Base/sheet wire values are "base-mode" and "sheet-mode"; accept old "base"/"sheet" only at compatibility boundaries.
- Use SQLGlot only for parsing, normalization, and policy checks. Execute the supported SQL subset through a Polars plan mapper; do not add DuckDB now (document it as future reference).
- Physical connector reads use bounded Arrow tables. Local evaluation runs in a disposable, killable worker with resource limits.
- Keep existing provider packages and old contract protocols working; adapt them at the SDK boundary.
- Do not modify the Rust/OTS bridge design or implement Rust code in this plan.

## File map

New package:

- packages/sdk/pyproject.toml
- packages/sdk/src/open_table_connector/sdk/{__init__,model,result,predicates,connector,registry,config,credentials,table,client,query,sql,temporal}.py
- packages/sdk/tests/{conftest,test_model,test_result,test_predicates,test_registry,test_client,test_table,test_query,test_sql,test_temporal,test_legacy_provider_integration,test_sdk_surface}.py

Existing files likely updated:

- root pyproject.toml (workspace member/dev dependency and lock)
- packages/cli/pyproject.toml
- packages/cli/src/open_table_connector/cli/{configuration,credentials,configured_registry,registry,pipeline,commands}.py
- CLI tests, provider conformance tests, package/readme/changelog docs.

## Task 1 — scaffold SDK values, errors, and operation results

Files: create the SDK package files for model.py, result.py, and predicates.py; add package metadata and tests; update root workspace metadata.

1. Write failing unit tests for TableMode with canonical base-mode/sheet-mode wires and compatibility decoding; source/destination/address/range-source value objects and safe redaction; OperationResult[T], Receipt, outcome/commit/verification states, typed OTCError, reconciliation details, and serialization; required predicates and all_rows() escape hatch.
2. Implement the smallest immutable value objects and result algebra. Expose only the approved names from sdk.__init__.
3. Add Polars and SQLGlot dependency constraints (polars>=1,<2, sqlglot>=30,<31, Arrow compatible with the workspace).
4. Run focused tests and ruff for the new package; review the public export list.

## Task 2 — connector bridge, registry, Client, and Table

Files: create connector.py, registry.py, config.py, credentials.py, table.py, client.py; add fixtures and focused tests.

1. Write failing tests using an in-memory fake connector for explicit connector injection, deterministic registry routing, lazy activation, and Client.from_config; Client.table(...) returning a physical Table, Client affinity checks, and close behavior; inspect/capabilities/read/read-page and bounded Arrow-to-Polars conversion; insert, keyed update, required delete(where=...), drop, and transaction context; Client.materialize(source, to=...) create-only conflict behavior.
2. Implement the SDK connector protocol/adapter. Wrap current ConnectorAdapter providers without changing their code; translate legacy receipts/results into the SDK result model and return typed unsupported-capability errors where necessary.
3. Implement registry/config/credential loading in the SDK, preserving the CLI deterministic entry-point routing and redaction rules.
4. Implement Table and Client with no ambient/global client state. Foreign physical handles must be rejected before connector I/O.
5. Run focused SDK tests plus existing contract tests.

## Task 3 — SQLGlot policy, Query, and Polars plan mapper

Files: create query.py, sql.py; add SQL tests; lock SQLGlot.

1. Write failing tests for the three SQL lanes: relational lite (explicit sources, projection, aliases, predicates, joins, grouping/aggregates, order, and limit); temporal lite (AS OF, latest-per-key, range, bucket aggregate, and gap-fill forms); provider-native SQL (explicit opt-in and read-only enforcement). Reject unbound sources, DDL/DML, offset, unsafe expressions, and silent fallback.
2. Implement Client.sql(...) and otc.sql(...) returning Query; bind physical sources to the originating Client.
3. Implement SQLGlot parse/normalization/policy with the AST discarded after validation.
4. Implement PolarsPlanMapper that produces/evaluates Polars plans from DataFrame inputs and collected physical tables, with conservative row/byte admission and no DuckDB dependency.
5. Run SQL-focused tests and existing connector tests.

## Task 4 — time-series facade and managed lifecycle

Files: create temporal.py; extend query.py, client.py, and exports; add temporal tests.

1. Write failing tests for typed temporal query builders (range, latest, as_of, bucket, gap_fill), temporal insert/upsert, and the managed stage/commit/readback/abort lifecycle.
2. Implement the facade over the existing timeseries descriptors/executor and managed protocols. Preserve typed values (ManagedStage, ManagedSnapshot, DataFrame, AbortDisposition) inside OperationResult[T].
3. Enforce stage lease expiry separately from snapshot retention and return reconciliation details on ambiguous commit/abort.
4. Run focused temporal tests and the full existing timeseries suite.

## Task 5 — cut the CLI over to the SDK

Files: update CLI metadata/modules and tests.

1. Add failing delegation tests proving CLI parsing/rendering calls Client methods and does not import or route directly through provider adapters.
2. Re-export SDK configuration/credentials/registry from CLI compatibility modules; keep old CLI command names and output stable.
3. Reduce pipeline.py to argument validation, SDK calls, and rendering. Use SDK Table, Query, and OperationResult throughout.
4. Run all CLI tests and a subprocess smoke test for the documented commands.

## Task 6 — provider compatibility and conformance

Files: add integration/conformance tests; make only compatibility-boundary changes in provider/contract packages; update package-boundary docs.

1. Exercise CSV/local-files, SQLite, Postgres (mocked), Google Sheets, Feishu Bitable, Maybe base-mode, and Excelize sheet-mode through the SDK registry/adapter.
2. Verify canonical mode wires, safe URI redaction, capability negotiation, and typed unsupported operations. Verify no SDK import cycle into providers.
3. Preserve existing provider conformance and CLI behavior; update README/API examples to the normalized surface.

## Task 7 — final verification, documentation, commit, and push

1. Update SDK README, root README, changelog, and package-boundary documentation with the final API, SQL lanes, base-mode/sheet-mode terminology, DuckDB future note, and deferred Rust bridge.
2. Run uv run --frozen ruff check ., uv run --frozen mypy for configured packages, all SDK/CLI/provider/conformance tests, git diff --check, and a forbidden-API scan for clear, append, replace, TableRef, TableHandle, and Table.frame.
3. Confirm no Rust/OTS design files changed and no CLI/provider module imports the SDK in the wrong direction.
4. Review the complete diff, commit the implementation, and push codex/critical-review-remediation to origin.
