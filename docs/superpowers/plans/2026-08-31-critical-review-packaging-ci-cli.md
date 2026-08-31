# Critical Review Packaging, CI, and CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the workspace reproducibly installable and releasable, automate its quality claims, and give the CLI one coherent format, routing, error, coordinate, and resource-limit model.

**Architecture:** The root becomes a non-package uv workspace with one supported-version policy. Every retained distribution declares its runtime boundary, typing marker, license, and README, and passes a clean-wheel import. CLI presentation and destination encoding are separate values served by one codec layer and an ambiguity-rejecting registry.

**Tech Stack:** Python 3.11–3.14, uv, setuptools, pytest 9, Ruff, mypy, PyArrow 14–19, Polars 1.x, GitHub Actions, and Apache-2.0.

**Spec:** `docs/superpowers/specs/2026-08-31-critical-review-remediation-design.md`

**Owned findings:** T5, E1, E2, E3, E4, E5, E6, E7, E8, E9, E10, E11, E12, G1, G2, G3, G4, G5, G6, G7, G8, and G9. E9's secret-safe error primitive lands in the transport/security plan; E11's identity primitive lands in specification/conformance; this plan closes their package/CLI integration.

**Prerequisites:** Complete the correctness, transport/security, and specification/conformance plans before Tasks 4–6 change public behavior. Task 1 may run early to repair the development environment.

## Global Constraints

- The root is a virtual workspace and does not build an empty distribution.
- Every package requires Python `>=3.11,<3.15`.
- Until interoperability evidence widens it, PyArrow remains `>=14,<20`; Polars remains `>=1,<2`.
- Internal packages use compatible `>=0.1,<0.2` ranges, not exact `==0.1.0` pins.
- Retain all 12 existing distributions for this remediation because they expose separately discoverable connector/capability or CLI dependency surfaces. Task 2 records that boundary evidence; if the audit disproves it for any package, stop and write a deprecation/folding design instead of silently changing its public import or distribution name.
- Use Apache-2.0, matching the related OpenCLI project; do not substitute another license during execution.
- `--output-format` controls stdout; `--to-format` controls convert destination encoding.
- Ordinary `ResourceLimits.max_rows` and temporal `ResourceBounds.max_rows` are hard completeness/execution bounds. Partial reads never claim completeness.
- CLI `--limit` remains a presentation limit and is not a completeness receipt.
- Work red-green-refactor. Each task ends with focused tests, the owning suite, `git diff --check`, a ledger update, and one Conventional Commit.

---

## File Map

- `pyproject.toml` — virtual workspace, supported versions, dev tools, and tool configuration.
- `packages/*/pyproject.toml` — dependencies, compatible ranges, license/readme, and typing metadata.
- `LICENSE`, `CHANGELOG.md`, `CONTRIBUTING.md` — publication contract.
- `scripts/check_package_metadata.py` — real workspace metadata and dependency-DAG validation.
- `scripts/smoke_wheels.py` — clean-environment wheel import tests.
- `.github/workflows/ci.yml` — quality, test matrix, package, and PostgreSQL jobs.
- `packages/cli/src/open_table_connector/cli/model.py` — separate destination and presentation formats.
- `packages/cli/src/open_table_connector/cli/formats.py` — shared local codecs.
- `packages/cli/src/open_table_connector/cli/registry.py` — explicit routes and collision rejection.
- `packages/contract/src/open_table_connector/contract/coordinates.py` — one coordinate identity and closed decoder.
- `packages/contract/src/open_table_connector/contract/receipts.py` — consistent hash validation.

### Task 1: Repair workspace metadata and standalone package dependencies

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: all `packages/*/pyproject.toml`
- Modify: `specification/compatibility/ots-otc-timeseries-v1.yaml`
- Modify: `README.md`
- Modify: `docs/getting-started.md`
- Modify: `docs/user-manual.md`
- Modify: `packages/cli/README.md`
- Create: `scripts/check_package_metadata.py`
- Create: `specification/conformance/universal/test_package_metadata.py`

**Interfaces:**
- Produces: virtual root `[tool.uv] package = false`; root `[tool.otc.support]` values for Python, PyArrow, and Polars; complete dependency declarations; `check_package_metadata(root: Path) -> list[str]` that rejects package/compatibility ranges drifting from the root policy.
- Consumes: the 12 workspace member paths and version floors in Global Constraints.

- [ ] **Step 1: Write failing metadata tests against the real tree**

```python
def test_workspace_package_metadata_is_complete() -> None:
    assert check_package_metadata(ROOT) == []

def test_hosted_packages_declare_imported_dependencies() -> None:
    google = package_metadata(ROOT / "packages/google_sheets/pyproject.toml")
    assert set(google.dependencies) >= {
        "open-table-connector-contract", "polars", "pyarrow"
    }
```

The checker reports exact `package: missing dependency` and range errors.

- [ ] **Step 2: Run the test and confirm the red phase**

```bash
uv run --frozen python -m pytest specification/conformance/universal/test_package_metadata.py -q
```

Expected: Google Sheets and Feishu lack dependencies; root is a buildable empty project.

- [ ] **Step 3: Convert the root and normalize package metadata**

Add `[tool.uv] package = false`; remove root build-system/project/setuptools
tables. Define root support values `python = ">=3.11,<3.15"`,
`pyarrow = ">=14,<20"`, and `polars = ">=1,<2"`; the checker requires every
package and compatibility record to agree. Set every package to Apache-2.0
metadata and compatible internal ranges. Google/Feishu add contract, Polars,
PyArrow, and workspace source mappings.

- [ ] **Step 4: Correct documented setup**

Use exactly:

```bash
uv sync --all-packages --group dev
```

Use `uv run --frozen` for verification. Remove every recommendation to run
the root-only `uv sync --dev` command.

- [ ] **Step 5: Lock, sync, test, and commit**

```bash
uv lock
uv sync --all-packages --group dev
uv run --frozen python -m pytest specification/conformance/universal/test_package_metadata.py -q
git diff --check
git add pyproject.toml uv.lock packages/*/pyproject.toml README.md docs/getting-started.md docs/user-manual.md packages/cli/README.md scripts/check_package_metadata.py specification/compatibility/ots-otc-timeseries-v1.yaml specification/conformance/universal/test_package_metadata.py
git commit -m "build: repair workspace package metadata"
```

### Task 2: Add release artifacts, package docs, and typing markers

**Files:**
- Create: `LICENSE`
- Create: `CHANGELOG.md`
- Create: `CONTRIBUTING.md`
- Create: `docs/package-boundaries.md`
- Create: `packages/conformance/README.md`
- Create: `packages/contract/README.md`
- Create: `packages/dbt/README.md`
- Create: `packages/local_files/README.md`
- Create: `packages/maybe_sheet/README.md`
- Create: `packages/postgres/README.md`
- Create: `packages/sqlite/README.md`
- Create: `packages/*/src/open_table_connector/*/py.typed`
- Modify: all `packages/*/pyproject.toml`
- Modify: `scripts/check_package_metadata.py`

**Interfaces:**
- Produces: Apache-2.0 license; Keep-a-Changelog structure; package-data inclusion for `py.typed`; README purpose/install/import/support sections; evidence-backed disposition for each of the 12 distribution boundaries.
- Consumes: existing distribution names and public namespaces.

- [ ] **Step 1: Extend the failing metadata test**

```python
def test_release_artifacts_and_typing_markers_are_complete() -> None:
    errors = check_package_metadata(ROOT)
    assert not [error for error in errors if any(
        word in error for word in ("LICENSE", "README", "py.typed")
    )]
```

- [ ] **Step 2: Run the checker and confirm missing artifacts**

```bash
uv run --frozen python -m pytest specification/conformance/universal/test_package_metadata.py -q
```

- [ ] **Step 3: Add exact release artifacts**

Copy the unmodified Apache License 2.0 text into `LICENSE`. Start
`CHANGELOG.md` with `Unreleased` and an undated 0.1.0 surface summary.
`CONTRIBUTING.md` gives the exact sync, focused/full test, lint, type, and build
commands. Each package README includes one minimal public-import example.
`docs/package-boundaries.md` records distribution name, public namespace,
capability/manifest role, in-workspace consumers, independent-release reason,
and retain/fold disposition. Record the approved retain decision only where
that evidence is present; an unsupported boundary triggers a separate
deprecation design instead of an in-task fold.

- [ ] **Step 4: Ship typing markers without replacing manifest data**

Add empty `py.typed` files and merge them into existing package-data tables:

```toml
[tool.setuptools.package-data]
"open_table_connector.<package>" = ["py.typed"]
```

- [ ] **Step 5: Build all packages and commit**

```bash
uv run --frozen python scripts/check_package_metadata.py
uv run --frozen python -m pytest specification/conformance/universal/test_package_metadata.py -q
git diff --check
git add LICENSE CHANGELOG.md CONTRIBUTING.md docs/package-boundaries.md packages/*/README.md packages/*/pyproject.toml packages/*/src/open_table_connector/*/py.typed scripts/check_package_metadata.py specification/conformance/universal/test_package_metadata.py
git commit -m "docs: add release and package metadata"
```

### Task 3: Add real dependency, wheel, quality, and PostgreSQL CI gates

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/release.yml`
- Create: `scripts/check_package_boundaries.py`
- Create: `scripts/smoke_wheels.py`
- Create: `specification/conformance/universal/test_package_boundaries.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `.gitignore`
- Remove from index: tracked generated `.superpowers/sdd/*` and reproducible stale build metadata

**Interfaces:**
- Produces: `check_boundaries(root: Path) -> list[str]`; `build_all_wheels(root: Path, dist: Path) -> tuple[Path, ...]`; `smoke_wheels(dist: Path) -> list[str]`; `scripts/smoke_wheels.py --build`; CI jobs `quality`, `tests`, `packages`, and `postgres-live`; tag-gated independent package releases.
- Consumes: dependency direction `contract <- timeseries <- providers <- process/cli`; conformance depends only on contract/timeseries.

- [ ] **Step 1: Write failing real-boundary and wheel tests**

```python
def test_real_workspace_dependency_direction() -> None:
    assert check_boundaries(ROOT) == []

def test_built_wheels_import_with_declared_dependencies(tmp_path: Path) -> None:
    assert smoke_wheels(build_all_wheels(tmp_path)) == []
```

- [ ] **Step 2: Run the tests and capture current failures**

```bash
uv run --frozen python -m pytest specification/conformance/universal/test_package_boundaries.py -q
```

- [ ] **Step 3: Configure local quality commands**

Add `ruff>=0.12,<1` and `mypy>=1.17,<2`. Ruff targets Python 3.11, 100
characters, and `E,F,I,UP,B,SIM`. Mypy enables `check_untyped_defs` and
`no_implicit_optional`; exclude build outputs, not production packages.

- [ ] **Step 4: Implement CI jobs**

`quality` runs Ruff, mypy, `git diff --check`, schemas, dependency checks, and
the compatibility verifier. `tests` uses Python 3.11–3.14. `packages` builds
all wheels and clean-imports each. `postgres-live` starts PostgreSQL 17 and
sets `OTC_TEST_POSTGRES_DSN` for the live lifecycle test.

`release.yml` accepts tags of the form `<distribution>/v<version>`, maps the
distribution to exactly one workspace member, verifies the tag version equals
that package's `project.version`, runs its declared-dependency clean install
and the full CI gates, builds only that sdist/wheel, then publishes through a
protected `pypi` environment with trusted-publisher OIDC. Reject unknown
distributions, dirty generated metadata, and an internal dependency version
not already satisfiable from the configured index. Never publish on a branch
push or pull request.

- [ ] **Step 5: Ignore generated artifacts without deleting user files**

Add `.DS_Store`, `/tmp-review-*`, `/.superpowers/brainstorm/`, and
`/.superpowers/sdd/`. Use `git rm --cached` for tracked generated reports so
working copies remain. The audited baseline has only `/.superpowers/sdd/`
generated reports tracked, so use `git rm --cached -r .superpowers/sdd`
after inspecting `git ls-files .superpowers/sdd`; do not stage or delete the
untracked user artifact directories. Remove tracked egg-info/dist outputs only
after their wheel source is verified.

- [ ] **Step 6: Run local CI equivalents and commit**

```bash
uv lock
uv run --frozen ruff check .
uv run --frozen mypy packages
uv run --frozen python -m pytest -q
uv run --frozen python scripts/check_package_boundaries.py
uv run --frozen python scripts/smoke_wheels.py --build
uv run --frozen python scripts/verify_compatibility.py
git diff --check
git rm --cached -r .superpowers/sdd
git add .github/workflows/ci.yml .github/workflows/release.yml .gitignore pyproject.toml uv.lock scripts/check_package_boundaries.py scripts/smoke_wheels.py specification/conformance/universal/test_package_boundaries.py docs/reviews/2026-08-31-critical-review-remediation.md
git commit -m "ci: enforce workspace and package boundaries"
```

### Task 4: Separate convert destination codec from stdout and unify codecs

**Files:**
- Modify: `packages/cli/src/open_table_connector/cli/__main__.py`
- Modify: `packages/cli/src/open_table_connector/cli/model.py`
- Modify: `packages/cli/src/open_table_connector/cli/commands.py`
- Modify: `packages/cli/src/open_table_connector/cli/pipeline.py`
- Modify: `packages/cli/src/open_table_connector/cli/formats.py`
- Modify: `packages/cli/src/open_table_connector/cli/output.py`
- Modify: `packages/cli/tests/test_commands.py`
- Modify: `packages/cli/tests/test_formats.py`
- Modify: `packages/cli/tests/test_pipeline.py`
- Modify: `packages/cli/tests/test_cli_e2e.py`
- Modify: `README.md`, `docs/getting-started.md`, `docs/user-manual.md`, `packages/cli/README.md`

**Interfaces:**
- Produces: `CliOptions.to_format: FormatName = AUTO`; `table_to_json_rows(table) -> list[dict[str, JsonValue]]`; `--output-format` always controls stdout.
- Consumes: `infer_format(destination, options.to_format)` and one `json_safe_value()` policy.

- [ ] **Step 1: Write failing separation and parity tests**

```python
def test_convert_separates_destination_and_summary_formats(tmp_path, capsys) -> None:
    destination = tmp_path / "orders.data"
    code = main(["convert", "--from", str(FIXTURE), "--to", str(destination),
                 "--to-format", "json", "--output-format", "table"])
    assert code == 0
    assert json.loads(destination.read_text()) == [{"id": "a"}]
    assert "| status" in capsys.readouterr().out

def test_read_and_convert_share_jsonl_bytes(tmp_path) -> None:
    assert convert_jsonl(TIMESTAMP_NAN_FIXTURE, tmp_path) == read_jsonl(TIMESTAMP_NAN_FIXTURE)
```

- [ ] **Step 2: Run CLI tests and confirm the red phase**

```bash
uv run --frozen python -m pytest packages/cli/tests/test_commands.py packages/cli/tests/test_formats.py packages/cli/tests/test_pipeline.py packages/cli/tests/test_cli_e2e.py -q
```

- [ ] **Step 3: Add `to_format` and one codec path**

All commands default stdout to JSONL. Convert infers destination format from
`--to-format` and endpoint; stdio defaults to JSONL only when AUTO. Move all
Arrow-to-JSON normalization into `formats.py`: RFC 3339 timestamps, scale-
preserving decimal strings, JSON null for non-finite floats, and stable nested
values. Read/output calls the same functions as convert.

- [ ] **Step 4: Update docs, run CLI tests, and commit**

```bash
uv run --frozen python -m pytest packages/cli/tests specification/conformance/universal/test_cli_surface.py -q
git diff --check
git add packages/cli/src/open_table_connector/cli/__main__.py packages/cli/src/open_table_connector/cli/model.py packages/cli/src/open_table_connector/cli/commands.py packages/cli/src/open_table_connector/cli/pipeline.py packages/cli/src/open_table_connector/cli/formats.py packages/cli/src/open_table_connector/cli/output.py packages/cli/tests/test_commands.py packages/cli/tests/test_formats.py packages/cli/tests/test_pipeline.py packages/cli/tests/test_cli_e2e.py README.md docs/getting-started.md docs/user-manual.md packages/cli/README.md specification/conformance/universal/test_cli_surface.py
git commit -m "fix: separate and unify CLI formats"
```

### Task 5: Make local schemes, registry routes, and usage errors explicit

**Files:**
- Modify: `packages/cli/src/open_table_connector/cli/adapters.py`
- Modify: `packages/cli/src/open_table_connector/cli/pipeline.py`
- Modify: `packages/cli/src/open_table_connector/cli/registry.py`
- Modify: `packages/cli/src/open_table_connector/cli/output.py`
- Modify: `packages/cli/tests/test_registry.py`
- Modify: `packages/cli/tests/test_cli_e2e.py`

**Interfaces:**
- Produces: LocalAdapter schemes `("file", "json", "jsonl")`; `Route(scheme, host, adapter_id)`; duplicate route registration raises `CONFLICT`; `CliUsageError(message, safe_details)`.
- Consumes: adapter-owned optional `hosts`, never connector-ID branches in the registry.

- [ ] **Step 1: Write failing scheme, collision, and error tests**

```python
@pytest.mark.parametrize("scheme", ["json", "jsonl"])
def test_local_json_schemes_route_to_local_adapter(scheme, tmp_path) -> None:
    endpoint = parse_endpoint(f"{scheme}://{tmp_path}/rows.{scheme}")
    assert registry.connector_for(endpoint).identity.connector_id == "local_files"

def test_duplicate_route_is_rejected() -> None:
    registry.register(adapter("https", hosts=("docs.google.com",)))
    with pytest.raises(ConnectorError) as raised:
        registry.register(adapter("https", hosts=("docs.google.com",)))
    assert raised.value.code is ConnectorErrorCode.CONFLICT
```

Add a parser case whose safe details are exactly
`{"option": "from-format", "value": "parquet"}`.

- [ ] **Step 2: Run registry/e2e tests and confirm the red phase**

```bash
uv run --frozen python -m pytest packages/cli/tests/test_registry.py packages/cli/tests/test_cli_e2e.py -q
```

- [ ] **Step 3: Implement routes and credential-safe usage errors**

Treat JSON/JSONL as local in registry and pipeline. Registration expands
adapter schemes/hosts and rejects duplicates. Remove hard-coded connector IDs.
Remove unreachable adapter write methods or expose them through convert; add a
test enumerating reachable capabilities. `CliUsageError` emits allow-listed
details; generic `ValueError` retains the fixed redacted fallback.

- [ ] **Step 4: Run CLI suite and commit**

```bash
uv run --frozen python -m pytest packages/cli/tests specification/conformance/universal/test_cli_surface.py -q
git diff --check
git add packages/cli/src/open_table_connector/cli/adapters.py packages/cli/src/open_table_connector/cli/pipeline.py packages/cli/src/open_table_connector/cli/registry.py packages/cli/src/open_table_connector/cli/output.py packages/cli/tests/test_registry.py packages/cli/tests/test_cli_e2e.py specification/conformance/universal/test_cli_surface.py docs/reviews/2026-08-31-critical-review-remediation.md
git commit -m "fix: make CLI routing and usage explicit"
```

### Task 6: Tighten coordinates, receipts, typing, visibility, and limits

**Files:**
- Modify: `packages/contract/src/open_table_connector/contract/coordinates.py`
- Modify: `packages/contract/src/open_table_connector/contract/scalars.py`
- Modify: `packages/contract/src/open_table_connector/contract/receipts.py`
- Modify: `packages/contract/tests/test_coordinates.py`
- Modify: `packages/contract/tests/test_receipts.py`
- Modify: `packages/conformance/src/open_table_connector/conformance/assertions.py`
- Modify: `packages/conformance/src/open_table_connector/conformance/timeseries.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/csv_reader.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/excel_reader.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/json_connector.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/markdown_connector.py`
- Modify: `packages/local_files/tests/test_csv_reader.py`
- Modify: `packages/local_files/tests/test_excel_reader.py`
- Modify: `packages/local_files/tests/test_json_connector.py`
- Modify: `packages/local_files/tests/test_markdown_connector.py`
- Modify: `packages/google_sheets/src/open_table_connector/google_sheets/connector.py`
- Modify: `packages/google_sheets/tests/test_connector.py`
- Modify: `packages/feishu_bitable/src/open_table_connector/feishu_bitable/connector.py`
- Modify: `packages/feishu_bitable/tests/test_connector.py`
- Modify: `packages/maybe_sheet/src/open_table_connector/maybe_sheet/connector.py`
- Modify: `packages/maybe_sheet/tests/test_connector.py`
- Modify: `packages/sqlite/src/open_table_connector/sqlite/reader.py`
- Modify: `packages/sqlite/tests/test_reader.py`
- Modify: `packages/postgres/src/open_table_connector/postgres/reader.py`
- Modify: `packages/postgres/tests/test_reader.py`
- Modify: `packages/cli/src/open_table_connector/cli/adapters.py`

**Interfaces:**
- Produces: `BaseCoordinate.from_wire()`; exactly one coordinate identity; `_ReadConnector(ArrowTableReader, PolarsTableReader, Protocol)`; consistent `sha256:` receipt validation; expected visibility parameter.
- Consumes: ordinary `ResourceLimits.max_rows` as a hard bound; temporal bounds unchanged.

- [ ] **Step 1: Write failing contract and typing tests**

```python
def test_base_coordinate_rejects_conflicting_identities() -> None:
    with pytest.raises(ValueError, match="exactly one identity"):
        BaseCoordinate(record_id="r1", key={"id": "r1"})

def test_base_coordinate_round_trips_closed_wire() -> None:
    value = BaseCoordinate(key={"id": "r1"})
    assert BaseCoordinate.from_wire(value.to_wire()) == value

def test_conformance_type_hints_resolve() -> None:
    assert get_type_hints(assert_read_connector_conformance)
```

Add invalid fingerprint strings and over-limit ordinary readers.

- [ ] **Step 2: Run contract/conformance tests and confirm the red phase**

```bash
uv run --frozen python -m pytest packages/contract/tests packages/conformance/tests -q
```

- [ ] **Step 3: Make v1 identity and receipt rules injective**

Require exactly one of record ID, key, or ordinal. Accept only string, int,
finite float, and bool in v1 coordinate keys; reject Decimal/date/datetime
because current wire strings collide. Add a closed decoder. Validate receipt
revision/fingerprints with the same lower-case `sha256:` rule and update
producers. Replace the invalid protocol intersection annotation with a combined
Protocol class.

- [ ] **Step 4: Align visibility and limit behavior**

Parameterize managed conformance with `expected_visibility`; atomic eligibility
is a separate assertion. Ordinary readers read one row beyond
`ResourceLimits.max_rows` and hard-error instead of truncating. Stop mapping
CLI `--limit` to this bound; slice only a complete read. Record a versioned
bounded-read receipt as the revisit condition for streaming truncation.

- [ ] **Step 5: Run full affected suites and commit**

```bash
uv run --frozen python -m pytest packages/contract/tests packages/conformance/tests packages/local_files/tests packages/google_sheets/tests packages/feishu_bitable/tests packages/maybe_sheet/tests packages/sqlite/tests packages/postgres/tests packages/cli/tests specification/conformance/universal -q
git diff --check
git add packages/contract/src/open_table_connector/contract/coordinates.py packages/contract/src/open_table_connector/contract/scalars.py packages/contract/src/open_table_connector/contract/receipts.py packages/contract/tests/test_coordinates.py packages/contract/tests/test_receipts.py packages/conformance/src/open_table_connector/conformance/assertions.py packages/conformance/src/open_table_connector/conformance/timeseries.py packages/local_files/src/open_table_connector/local_files/csv_reader.py packages/local_files/src/open_table_connector/local_files/excel_reader.py packages/local_files/src/open_table_connector/local_files/json_connector.py packages/local_files/src/open_table_connector/local_files/markdown_connector.py packages/local_files/tests/test_csv_reader.py packages/local_files/tests/test_excel_reader.py packages/local_files/tests/test_json_connector.py packages/local_files/tests/test_markdown_connector.py packages/google_sheets/src/open_table_connector/google_sheets/connector.py packages/google_sheets/tests/test_connector.py packages/feishu_bitable/src/open_table_connector/feishu_bitable/connector.py packages/feishu_bitable/tests/test_connector.py packages/maybe_sheet/src/open_table_connector/maybe_sheet/connector.py packages/maybe_sheet/tests/test_connector.py packages/sqlite/src/open_table_connector/sqlite/reader.py packages/sqlite/tests/test_reader.py packages/postgres/src/open_table_connector/postgres/reader.py packages/postgres/tests/test_reader.py packages/cli/src/open_table_connector/cli/adapters.py docs/reviews/2026-08-31-critical-review-remediation.md
git commit -m "fix: align contract identities and read bounds"
```

## Plan Verification

After all six tasks:

```bash
uv sync --all-packages --group dev
uv run --frozen ruff check .
uv run --frozen mypy packages
uv run --frozen python -m pytest -q
uv run --frozen python scripts/check_package_boundaries.py
uv run --frozen python scripts/smoke_wheels.py --build
uv run --frozen python scripts/verify_compatibility.py
git diff --check
```

Expected: every wheel imports independently, documented setup works, CLI
formats/routes are coherent, no partial receipt claims completeness, and every
E/G finding has a ledger disposition.
