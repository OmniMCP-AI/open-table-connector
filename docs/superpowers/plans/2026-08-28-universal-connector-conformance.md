# Universal Connector Conformance Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (\`- [ ]\`) syntax for tracking.

**Goal:** Build an offline universal conformance suite with at least 120 collected, named tests covering every connector package in the workspace.

**Architecture:** Add a dedicated \`specification/conformance/universal/\` test package with a small case registry and fixture protocol. Shared assertions consume normalized connector cases; provider-specific fixture adapters own only deterministic setup and protocol details. The suite tests declared capabilities rather than forcing unsupported operations onto connectors that do not advertise them.

**Tech Stack:** Python 3.12, pytest 9, PyArrow, Polars, temporary files/databases, recording transports/process clients, and the existing \`open_connectors.contract\` interfaces.

**Spec:** \`docs/superpowers/specs/2026-08-28-universal-connector-conformance-design.md\`

**Current status (2026-08-28):** Tasks 1–8 are complete. Final-review round 1
added independent literal metadata expectations for all seven connectors,
credential-isolated subprocess coverage, exact MaybeSheet JSONL bytes, and the
approved formula-negative and timeout tests. The dedicated suite collects and
passes 245 cases, and the full workspace passes 432 tests. Dependency sync and
lock checks, bytecode compilation, \`uv build --all-packages\`, ordered
collection-ID determinism, and offline CLI smoke checks pass. Exact commands,
exit statuses, build artifacts, and remaining concerns are recorded in
\`.superpowers/sdd/2026-08-28-universal-connector-conformance/task-8-report.md\`.
Independent release artifacts/tags and owner-supplied live evidence remain
outside this test-only plan.

## Global Constraints

- The suite covers \`local_files\`, \`google_sheets\`, \`feishu_bitable\`, \`maybesheet\`, \`sqlite\`, \`postgres\`, and \`dbt\`.
- The suite is offline and deterministic: no credentials, network calls, vendor binaries, external database services, or shared mutable databases.
- The dedicated suite collects at least 120 named test cases; parametrized cases must have descriptive IDs and be spread across multiple behavior-focused test functions.
- Common assertions test neutral contract guarantees; capability-specific assertions run only for declared capabilities, while unsupported calls are checked for explicit safe failures where exposed.
- Error assertions inspect stable error codes and safe details, never raw provider payloads or credentials.
- Existing provider behavior remains the source of truth; universal tests must not weaken provider-specific tests or alter production behavior.
- Full workspace tests must continue to pass after the universal suite is added.
- Test results must document the connector case, capability, fixture, and invariant that failed.

---

## File Map

Create these focused files:

- \`specification/conformance/universal/__init__.py\` — package marker and public case names.
- \`specification/conformance/universal/cases.py\` — \`ConnectorCase\`, capability constants, and seven deterministic case definitions.
- \`specification/conformance/universal/fixtures.py\` — temporary files/databases and recording transport/process doubles.
- \`specification/conformance/universal/assertions.py\` — small reusable contract assertions with explicit inputs and outputs.
- \`specification/conformance/universal/conftest.py\` — pytest fixtures for case lookup, temporary resources, and safe environment isolation.
- \`specification/conformance/universal/test_discovery.py\` — identity, manifest, mode, scheme, and capability tests.
- \`specification/conformance/universal/test_contract.py\` — URI, wire, receipt, error, and determinism tests.
- \`specification/conformance/universal/test_table_connectors.py\` — local files, Google Sheets, Feishu Bitable, and MaybeSheet matrix tests.
- \`specification/conformance/universal/test_database_connectors.py\` — SQLite and Postgres matrix tests.
- \`specification/conformance/universal/test_dbt_connector.py\` — dbt compile/run/cancel/artifact matrix tests.
- \`specification/conformance/universal/test_cli_surface.py\` — registry, codec, CLI output, conversion, and redaction tests.
- \`specification/conformance/universal/test_suite_count.py\` — executable minimum-count guard.
- \`specification/conformance/universal/README.md\` — commands, fixture policy, connector matrix, and test-count reporting.

Do not modify production connector code unless a universal test demonstrates a pre-existing contract violation that is explicitly included as a separately approved fix. This plan is for tests and test fixtures.

## Interfaces

\`cases.py\` exposes a frozen case record:

\`\`\`python
@dataclass(frozen=True)
class ConnectorCase:
    name: str
    connector: object
    identity: ConnectorIdentity
    capabilities: frozenset[str]
    modes: frozenset[TableMode]
    schemes: frozenset[str]
    table_uri: TableURI
    make_read_request: Callable[[ResourceLimits], object] | None
    make_inspect_request: Callable[[ResourceLimits], InspectRequest] | None
    make_write_request: Callable[[pl.DataFrame, str], TableWriteRequest] | None
    read_arrow: Callable[[ResourceLimits], ArrowReadResult] | None
    read_polars: Callable[[ResourceLimits], PolarsReadResult] | None
    inspect: Callable[[ResourceLimits], TableInspection] | None
    write: Callable[[pl.DataFrame, str], TableWriteResult] | None

def all_cases() -> tuple[ConnectorCase, ...]: ...
def case(name: str) -> ConnectorCase: ...
def cases_with(capability: str) -> tuple[ConnectorCase, ...]: ...
\`\`\`

\`fixtures.py\` exposes recording doubles with stable public state:

\`\`\`python
class RecordingSheetsTransport:
    requests: list[RecordedRequest]
    def request(self, method: str, url: str, *, headers: Mapping[str, str],
                body: Mapping[str, Any] | None = None,
                timeout: int | None = None) -> Mapping[str, Any]: ...

class RecordingProcessClient:
    calls: list[RecordedProcessCall]
    def run(self, argv: tuple[str, ...], *,
            credentials: Mapping[str, str] | None = None,
            stdin: Iterable[str] | None = None,
            timeout: int | None = None) -> Mapping[str, Any]: ...
\`\`\`

### Task 1: Build the case registry and deterministic fixture boundary

**Files:**
- Create: \`specification/conformance/universal/__init__.py\`
- Create: \`specification/conformance/universal/cases.py\`
- Create: \`specification/conformance/universal/fixtures.py\`
- Create: \`specification/conformance/universal/conftest.py\`
- Create: \`specification/conformance/universal/test_discovery.py\`

**Interfaces:**
- Consumes: existing connector identities, manifests, request classes, and injected transport/process seams.
- Produces: \`ConnectorCase\`, \`all_cases()\`, \`case()\`, \`cases_with()\`, \`RecordingSheetsTransport\`, and \`RecordingProcessClient\`.

- [ ] **Step 1: Write failing registry tests**

Add tests requiring exactly these seven case names and stable lookup:

\`\`\`python
def test_all_current_connectors_have_named_cases() -> None:
    assert {item.name for item in all_cases()} == {
        "local_files", "google_sheets", "feishu_bitable", "maybesheet",
        "sqlite", "postgres", "dbt",
    }

def test_case_lookup_rejects_unknown_connector() -> None:
    with pytest.raises(KeyError, match="unknown connector case"):
        case("missing")
\`\`\`

- [ ] **Step 2: Run the focused tests to verify the expected red phase**

Run:

\`\`\`bash
uv run python -m pytest specification/conformance/universal/test_discovery.py -q
\`\`\`

Expected: collection or assertion failures because the registry files do not yet exist.

- [ ] **Step 3: Implement the minimal fixture boundary**

Create deterministic fixtures:

- local files: temporary CSV and XLSX fixtures created by pytest;
- Google Sheets: \`GoogleSheetsConnector(RecordingSheetsTransport(...), access_token="fixture-token")\` with stable values payloads;
- Feishu Bitable: \`FeishuBitableConnector(RecordingSheetsTransport(...), tenant_access_token="fixture-token")\` with stable record payloads;
- MaybeSheet: \`MaybeSheetConnector(RecordingProcessClient(...))\` returning stable JSON payloads and recording argv/stdin/credentials;
- SQLite: \`SqliteConnector\` against a unique \`tmp_path / "fixture.sqlite"\` database;
- Postgres: \`PostgresConnector\` against a recording DB-API connection factory;
- dbt: \`DbtConnector\` against a recording runner returning stable compile/run payloads.

Every case must expose the actual connector identity, declared capabilities, modes, schemes, and one valid fixture URI. Case factories must not read ambient provider tokens or call external services.

- [ ] **Step 4: Run focused tests to verify green**

Run the same command. Expected: PASS, with a descriptive failure if any case metadata is inconsistent.

- [ ] **Step 5: Commit**

\`\`\`bash
git add specification/conformance/universal
git commit -m "test: add universal connector case registry"
\`\`\`

### Task 2: Add shared discovery and contract invariants

**Files:**
- Create: \`specification/conformance/universal/assertions.py\`
- Modify: \`specification/conformance/universal/conftest.py\`
- Modify: \`specification/conformance/universal/test_discovery.py\`
- Create: \`specification/conformance/universal/test_contract.py\`

**Interfaces:**
- Consumes: \`ConnectorCase\` and fixture boundary from Task 1.
- Produces: reusable assertions for identity, capabilities, URI safety, wire shape, errors, and deterministic metadata.

- [ ] **Step 1: Write failing shared invariant tests**

Use separate behavior-focused functions, each parametrized over \`all_cases()\` with IDs equal to the case name:

\`\`\`python
@pytest.mark.parametrize("connector_case", all_cases(), ids=lambda item: item.name)
def test_connector_identity_is_closed_and_stable(connector_case: ConnectorCase) -> None:
    wire = connector_case.identity.to_wire()
    assert ConnectorIdentity.from_wire(wire) == connector_case.identity
    assert set(wire) == {"connector_id", "connector_version", "contract_version"}

@pytest.mark.parametrize("connector_case", all_cases(), ids=lambda item: item.name)
def test_case_uri_is_absolute_and_credential_free(connector_case: ConnectorCase) -> None:
    parsed = TableURI(connector_case.table_uri.value)
    assert parsed.scheme in connector_case.schemes
    assert "token=" not in parsed.value.casefold()
\`\`\`

Add separate tests for manifest capabilities, mode validity, unique capability IDs, capability wire shape, receipt wire keys, safe error wire keys, stable case ordering, and invalid URI credentials/secret queries.

- [ ] **Step 2: Run focused tests to verify red**

\`\`\`bash
uv run python -m pytest specification/conformance/universal/test_discovery.py specification/conformance/universal/test_contract.py -q
\`\`\`

Expected: failures for missing assertion helpers and metadata mismatches exposed by real fixtures.

- [ ] **Step 3: Implement assertion helpers only**

Add focused functions such as \`assert_identity_round_trip\`, \`assert_capabilities_are_unique\`, \`assert_safe_uri\`, \`assert_receipt_matches_table\`, and \`assert_error_is_safe\`. Each accepts concrete values and performs no fixture construction or hidden I/O.

- [ ] **Step 4: Run focused tests to verify green**

Run the same command. Expected: all discovery/contract tests pass and errors contain no fixture token.

- [ ] **Step 5: Commit**

\`\`\`bash
git add specification/conformance/universal/assertions.py specification/conformance/universal/conftest.py specification/conformance/universal/test_discovery.py specification/conformance/universal/test_contract.py
git commit -m "test: cover universal connector contract invariants"
\`\`\`

### Task 3: Add table-connector universal tests

**Files:**
- Modify: \`specification/conformance/universal/cases.py\`
- Modify: \`specification/conformance/universal/fixtures.py\`
- Create: \`specification/conformance/universal/test_table_connectors.py\`

**Interfaces:**
- Consumes: \`ConnectorCase\`, shared assertions, and provider-specific recording fixtures.
- Produces: universal table behavior coverage for \`local_files\`, \`google_sheets\`, \`feishu_bitable\`, and \`maybesheet\`.

- [ ] **Step 1: Write failing behavior tests first**

Create separate functions using capability-filtered cases and descriptive IDs:

\`\`\`python
@pytest.mark.parametrize("connector_case", cases_with("table.read.arrow"), ids=lambda item: item.name)
def test_table_read_arrow_returns_bounded_rows(connector_case: ConnectorCase) -> None:
    result = connector_case.read_arrow(ResourceLimits(max_rows=2))
    assert result.table.num_rows <= 2
    assert result.receipt.row_count == result.table.num_rows

@pytest.mark.parametrize("connector_case", cases_with("table.inspect"), ids=lambda item: item.name)
def test_table_inspection_matches_read_schema(connector_case: ConnectorCase) -> None:
    inspection = connector_case.inspect(ResourceLimits(max_rows=2))
    result = connector_case.read_arrow(ResourceLimits(max_rows=2))
    assert inspection.columns == tuple(result.table.column_names)
    assert inspection.row_count == result.table.num_rows
\`\`\`

Add distinct test families for Arrow/Polars parity, stable columns, receipt fingerprints, coordinate conventions, pagination/request limits, write request shape, affected-row counts, supported write policies, Feishu \`_record_id\`, MaybeSheet stdin JSONL, provider failure redaction, local CSV/XLSX formats, and repeated reads.

- [ ] **Step 2: Run the table suite and verify red**

\`\`\`bash
uv run python -m pytest specification/conformance/universal/test_table_connectors.py -q
\`\`\`

Expected: failures for missing table case operations and incomplete recording assertions.

- [ ] **Step 3: Complete case factories and recording assertions**

Adapt only the case layer. For every provider call, assert method, URL/argv, timeout, selected fields/ranges, and credential locality using recording state. Return payloads exercising empty cells, mixed types, multiple pages, and over-returned rows. Use \`ResourceLimits(max_rows=2, timeout_seconds=3)\` in limit tests and assert request propagation plus bounded result/receipt state.

- [ ] **Step 4: Run focused table tests to verify green**

Run the same command. Expected: all table cases pass without network access; credentials appear only in recording input state and never in assertion output.

- [ ] **Step 5: Commit**

\`\`\`bash
git add specification/conformance/universal/cases.py specification/conformance/universal/fixtures.py specification/conformance/universal/test_table_connectors.py
git commit -m "test: add universal table connector conformance"
\`\`\`

### Task 4: Add SQLite and Postgres universal tests

**Files:**
- Modify: \`specification/conformance/universal/cases.py\`
- Modify: \`specification/conformance/universal/fixtures.py\`
- Create: \`specification/conformance/universal/test_database_connectors.py\`

**Interfaces:**
- Consumes: shared table assertions and database case factories from Task 1.
- Produces: deterministic database contract coverage without a live Postgres service.

- [ ] **Step 1: Write failing database behavior tests**

Cover separate functions for URI resolution, bounded reads, Arrow/Polars parity, inspect/read agreement, SQL/table option selection, write policies, transaction/close behavior, receipts, and stable authentication/execution failures. Use a recording DB-API connection for Postgres and a temporary SQLite database with two rows.

\`\`\`python
@pytest.mark.parametrize("connector_case", (case("sqlite"), case("postgres")), ids=lambda item: item.name)
def test_database_reads_honor_max_rows(connector_case: ConnectorCase) -> None:
    result = connector_case.read_arrow(ResourceLimits(max_rows=1))
    assert result.table.num_rows == 1
    assert result.receipt.row_count == 1

def test_postgres_fixture_never_opens_a_network_connection(postgres_case) -> None:
    result = postgres_case.read_arrow(ResourceLimits(max_rows=2))
    assert result.table.to_pylist()
    assert postgres_case.fixture.connection_factory.calls
\`\`\`

- [ ] **Step 2: Run focused tests and verify red**

\`\`\`bash
uv run python -m pytest specification/conformance/universal/test_database_connectors.py -q
\`\`\`

Expected: failures until the database case factories and recording DB-API protocol are wired.

- [ ] **Step 3: Implement the deterministic database fixture boundary**

Initialize SQLite under pytest \`tmp_path\`, never a repository path. The Postgres recording cursor implements \`execute\`, \`fetchmany\`, \`description\`, \`rowcount\`, \`executemany\`, commit, rollback, and close state so tests can assert actual behavior. Keep rows and SQL statements fixture-local.

- [ ] **Step 4: Run focused tests to verify green**

Run the same command. Expected: all SQLite/Postgres tests pass offline and no external DB adapter is required.

- [ ] **Step 5: Commit**

\`\`\`bash
git add specification/conformance/universal/cases.py specification/conformance/universal/fixtures.py specification/conformance/universal/test_database_connectors.py
git commit -m "test: add universal database connector conformance"
\`\`\`

### Task 5: Add dbt universal lifecycle tests

**Files:**
- Modify: \`specification/conformance/universal/cases.py\`
- Modify: \`specification/conformance/universal/fixtures.py\`
- Create: \`specification/conformance/universal/test_dbt_connector.py\`

**Interfaces:**
- Consumes: existing dbt request/result types and the recording runner fixture.
- Produces: deterministic dbt compile, run, cancel, artifact, readback, identity, and failure coverage.

- [ ] **Step 1: Write failing dbt behavior tests**

Create distinct tests for compile argv construction, select/exclude/target/vars propagation, invocation ID determinism, artifact hash determinism, run status/result mapping, cancellation mapping, artifact lookup, readback facts, unsupported runner behavior, runner failure mapping, and safe error details.

\`\`\`python
def test_dbt_compile_invocation_is_deterministic(dbt_case, tmp_path) -> None:
    first = dbt_case.connector.compile(DbtCompileRequest(tmp_path, select=("orders",), target="fixture"))
    second = dbt_case.connector.compile(DbtCompileRequest(tmp_path, select=("orders",), target="fixture"))
    assert first.invocation_id == second.invocation_id
    assert first.artifact_hash == second.artifact_hash
\`\`\`

- [ ] **Step 2: Run focused tests and verify red**

\`\`\`bash
uv run python -m pytest specification/conformance/universal/test_dbt_connector.py -q
\`\`\`

Expected: failures until the recording runner and temporary dbt project fixture are wired.

- [ ] **Step 3: Implement the recording runner fixture**

The runner records argv and project directory and returns stable \`artifacts\`, \`status\`, \`run_results\`, and \`artifact_refs\`. The temporary project contains only fixture files. Tests assert no global dbt command is launched and no credential-bearing variables enter argv or metadata.

- [ ] **Step 4: Run focused tests to verify green**

Run the same command. Expected: all dbt tests pass without the dbt executable installed.

- [ ] **Step 5: Commit**

\`\`\`bash
git add specification/conformance/universal/cases.py specification/conformance/universal/fixtures.py specification/conformance/universal/test_dbt_connector.py
git commit -m "test: add universal dbt conformance"
\`\`\`

### Task 6: Add CLI, format, import, and security matrix tests

**Files:**
- Create: \`specification/conformance/universal/test_cli_surface.py\`
- Modify: \`specification/conformance/universal/fixtures.py\`
- Modify: \`specification/conformance/universal/assertions.py\`

**Interfaces:**
- Consumes: CLI parser/commands, \`ConnectorRegistry\`, local codecs, and table-capable case fixtures.
- Produces: offline end-to-end coverage for unified \`otc\` behavior across connector cases.

- [ ] **Step 1: Write failing CLI matrix tests**

Add separate tests for:

- \`list\` discovery returns every registered connector and safe capabilities/modes;
- \`inspect --from\` selects the correct URI scheme and reports safe metadata;
- \`read --from\` defaults to JSONL row events followed by one summary;
- local CSV/JSON/JSONL/table conversion round trips preserve rows and columns;
- \`convert --from --to\` uses local format inference and explicit overrides;
- \`import --from --to\` preserves source and destination receipts;
- \`--limit\`, \`--timeout\`, \`--if-exists\`, \`--sheet\`, \`--range\`, \`--field-name\`, and \`--target\` reach the owning adapter;
- provider format overrides fail before provider I/O;
- unsupported schemes/capabilities map to stable exit codes;
- CSV, JSON, JSONL, and table outputs are truthful and safe;
- malformed input, auth failures, conflicts, and provider exceptions redact fixture tokens;
- conversion to stdout contains only the selected codec;
- repeated CLI runs produce deterministic JSONL and table output.

Use real \`run_command\` calls with \`Namespace\` objects and in-memory streams, plus a small number of subprocess calls to \`uv run otc\` for parser/entry-point behavior. Do not invoke network transports.

- [ ] **Step 2: Run focused tests and verify red**

\`\`\`bash
uv run python -m pytest specification/conformance/universal/test_cli_surface.py -q
\`\`\`

Expected: failures for missing case-to-CLI bridges and uncovered matrix behavior.

- [ ] **Step 3: Implement only test-side CLI bridges**

Add helpers that construct \`CliOptions\`, registry adapters, in-memory streams, and temporary local paths. Assert parsed JSON with strict \`json.loads(..., parse_constant=...)\`, parse CSV with \`csv.DictReader\`, and compare table output as escaped Markdown rows. Keep credentials in fixture inputs and assert they never appear in output.

- [ ] **Step 4: Run focused tests to verify green**

Run the same command. Expected: all CLI matrix tests pass offline and stdout/stderr ownership remains explicit.

- [ ] **Step 5: Commit**

\`\`\`bash
git add specification/conformance/universal/test_cli_surface.py specification/conformance/universal/fixtures.py specification/conformance/universal/assertions.py
git commit -m "test: add universal cli and security matrix"
\`\`\`

### Task 7: Enforce the 120-test floor and document the suite

**Files:**
- Create: \`specification/conformance/universal/test_suite_count.py\`
- Create: \`specification/conformance/universal/README.md\`
- Modify: \`pyproject.toml\` only if a pytest marker or collection setting is required by the implemented suite.

**Interfaces:**
- Consumes: all universal tests and case IDs from Tasks 1–6.
- Produces: a repeatable count guard and contributor-facing run instructions.

- [x] **Step 1: Write the failing count guard**

The count guard collects the dedicated directory in a subprocess and fails with the actual count below 120. Its assertion message includes the command and observed count:

\`\`\`python
MINIMUM_UNIVERSAL_TESTS = 120

def test_universal_suite_has_minimum_collected_cases() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", str(UNIVERSAL_DIR), "--collect-only", "-q"],
        check=True, capture_output=True, text=True,
    )
    count = parse_collected_count(completed.stdout)
    assert count >= MINIMUM_UNIVERSAL_TESTS, (
        f"universal suite collected {count}; expected at least {MINIMUM_UNIVERSAL_TESTS}"
    )
\`\`\`

\`parse_collected_count\` must use the pytest summary line, not a hard-coded name list. The README shows:

\`\`\`bash
uv run python -m pytest specification/conformance/universal --collect-only -q
uv run python -m pytest specification/conformance/universal -q
\`\`\`

- [x] **Step 2: Run the count guard and verify red if below the floor**

\`\`\`bash
uv run python -m pytest specification/conformance/universal/test_suite_count.py -q
\`\`\`

Expected: FAIL with the observed collected count if the suite has fewer than 120 tests.

- [x] **Step 3: Expand named behavior functions until the floor is met**

Add missing behavior-focused tests in the relevant task file, not one giant parameter list. Every parametrized test uses stable descriptive IDs. The final directory contains at least eight behavior-focused test modules/functions families and at least 120 collected cases.

- [x] **Step 4: Run the count guard and dedicated suite to verify green**

Run both README commands. Expected: count at least 120, dedicated suite passes, and count guard reports no failure.

- [x] **Step 5: Commit**

\`\`\`bash
git add specification/conformance/universal/test_suite_count.py specification/conformance/universal/README.md pyproject.toml
git commit -m "test: enforce universal conformance suite size"
\`\`\`

### Task 8: Run the complete workspace gate and final review

**Files:**
- Modify: none unless a test-only issue is found and fixed through a new red-green cycle.

**Interfaces:**
- Consumes: completed universal suite and existing workspace tests.
- Produces: verified full test/build evidence and reviewable final diff.

- [x] **Step 1: Run the dedicated suite and record its count**

\`\`\`bash
uv run python -m pytest specification/conformance/universal --collect-only -q
uv run python -m pytest specification/conformance/universal -q
\`\`\`

Expected: at least 120 collected tests and zero failures.

- [x] **Step 2: Run the full workspace tests**

\`\`\`bash
uv sync --all-packages --group dev
uv lock --check
uv run python -m pytest
\`\`\`

Expected: the original suite plus the universal suite pass.

- [x] **Step 3: Run static/build checks**

\`\`\`bash
git diff --check
python3 -m compileall -q packages specification/conformance/universal
uv build --all-packages
\`\`\`

Expected: all commands exit zero.

- [x] **Step 4: Run offline/security smoke checks**

\`\`\`bash
uv run otc list --output-format jsonl
uv run otc --help
uv run open-table-connector --help
uv run open-connectors --help
\`\`\`

Expected: four connector discovery records and successful help output for all entry points; no credentials or network calls.

- [x] **Step 5: Prepare the final review package**

\`\`\`bash
BASE=$(git merge-base origin/main HEAD)
/Users/admin/.codex/plugins/cache/openai-curated-remote/superpowers/6.3.0/skills/subagent-driven-development/scripts/review-package \\
  docs/superpowers/plans/2026-08-28-universal-connector-conformance.md "$BASE" HEAD
\`\`\`

Request separate standards/spec review against \`docs/superpowers/specs/2026-08-28-universal-connector-conformance-design.md\`. Resolve every Critical or Important finding with a fresh test and focused commit before handoff.

- [x] **Step 6: Commit any final test-only correction and report verification**

Use a specific message such as:

\`\`\`bash
git add specification/conformance/universal
git commit -m "test: tighten universal conformance coverage"
\`\`\`

Report the exact collected count, full-suite result, build result, and any accepted Minor concern.
