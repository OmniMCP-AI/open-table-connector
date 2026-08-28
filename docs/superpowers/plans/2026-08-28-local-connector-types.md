# Local Connector Types Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the local file implementation into discoverable `csv`, `excel`, and `md` connector identities while preserving `local_files` and `file://` compatibility.

**Architecture:** Keep `packages/local_files` as the ownership seam, with three deep format-specific connector modules and one compatibility facade. The concrete modules own format-specific URI resolution, read/inspect behavior, manifests, receipts, and options; the facade probes `file://` resources and delegates internally while retaining the `local_files` identity in compatibility receipts. The CLI registers the three explicit schemes plus the existing facade route.

**Tech Stack:** Python 3.11+, `dataclasses`, `enum.StrEnum`, `pathlib`, `urllib.parse`, PyArrow, Polars, openpyxl, pytest, and the existing `uv` workspace.

**Spec:** `docs/superpowers/specs/2026-08-28-local-connector-types-design.md`

## Global Constraints

- Expose concrete connector identities for `csv`, `excel`, and `md`.
- Preserve the existing `local_files` identity as a compatibility facade.
- Preserve `file://` URIs and bare local paths through format autodetection.
- Add explicit URI schemes for direct format selection: `csv://`, `excel://`, and `md://`.
- Keep format-specific behavior behind small, testable connector interfaces.
- Keep neutral connector code independent of the CLI package.
- Preserve the existing CLI `--from`/`--to` conversion and import workflows.
- Do not add a new distribution for every local format; the existing local-files distribution owns all four implementations.
- Explicit concrete schemes reject mismatched payloads instead of silently falling back to another format.
- No credentials or network access are introduced for local formats.

## File map

- `packages/local_files/src/open_table_connector/local_files/csv_connector.py` — public CSV connector identity, options, request, resolver, reads, inspection, and manifest.
- `packages/local_files/src/open_table_connector/local_files/excel_connector.py` — public Excel connector identity, options, request, resolver, reads, inspection, and manifest.
- `packages/local_files/src/open_table_connector/local_files/markdown_connector.py` — public Markdown connector identity, options, request, parser-backed reads, inspection, and manifest.
- `packages/local_files/src/open_table_connector/local_files/excel_writer.py` — neutral XLSX writer used by CLI conversion destinations.
- `packages/local_files/src/open_table_connector/local_files/local_files_connector.py` — `file://`/bare-path compatibility facade and delegation.
- `packages/local_files/src/open_table_connector/local_files/markdown_reader.py` — neutral Markdown pipe-table parser and writer shared by the connector and CLI.
- `packages/local_files/src/open_table_connector/local_files/probe.py` — CSV, XLSX, and Markdown format detection.
- `packages/local_files/src/open_table_connector/local_files/receipts.py` — receipt construction parameterized by connector identity.
- `packages/local_files/src/open_table_connector/local_files/__init__.py` — stable exports for concrete connectors and compatibility names.
- `packages/cli/src/open_table_connector/cli/adapters.py` — explicit local-format adapters plus the compatibility local adapter.
- `packages/cli/src/open_table_connector/cli/formats.py` — reuse neutral Markdown parsing and local endpoint/path format selection.
- `packages/cli/src/open_table_connector/cli/model.py` — explicit local format names when needed by endpoint routing.
- `packages/cli/src/open_table_connector/cli/registry.py` — scheme registration and dispatch ordering.
- `packages/cli/src/open_table_connector/cli/pipeline.py` — treat explicit local format URIs as conversion destinations while preserving import rules.
- `packages/cli/pyproject.toml` — add the local-files workspace dependency for concrete adapters.
- `pyproject.toml`, `uv.lock` — workspace path and dependency metadata.
- `packages/local_files/tests/` — concrete connector and compatibility tests.
- `packages/cli/tests/` — CLI routing, listing, conversion, and compatibility tests.
- `specification/conformance/universal/` — named connector cases and universal matrix coverage.
- `README.md`, `packages/cli/README.md`, and the relevant design/plan docs — public names, schemes, and usage examples.

---

### Task 1: Extract neutral Markdown codec and shared local format primitives

**Files:**
- Create: `packages/local_files/src/open_table_connector/local_files/markdown_reader.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/probe.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/__init__.py`
- Modify: `packages/cli/src/open_table_connector/cli/formats.py`
- Test: `packages/local_files/tests/test_markdown_reader.py`
- Test: `packages/local_files/tests/test_probe.py`
- Test: `packages/cli/tests/test_formats.py`

**Interfaces:**
- Consumes: the existing CLI Markdown grammar in `_read_markdown_table`, `write_markdown_table`, `_split_markdown_row`, and separator validation.
- Produces: `read_markdown_arrow(text: str, *, source: str) -> pyarrow.Table`, `write_markdown_table(headers, rows, stream)`, `is_markdown_payload(text: str) -> bool`, and `LocalFormat.MARKDOWN` for Tasks 2 and 3.

- [x] **Step 1: Write failing codec and detection tests**

```python
def test_markdown_reader_round_trips_escaped_cells_and_hyphen_rows() -> None:
    table = read_markdown_arrow(
        "| id | note |\n| --- | --- |\n| 1 | a \\| b |\n| - | - |\n",
        source="orders.md",
    )
    assert table.to_pylist() == [
        {"id": "1", "note": "a | b"},
        {"id": "-", "note": "-"},
    ]


def test_markdown_payload_requires_a_pipe_table_separator() -> None:
    assert is_markdown_payload("# title\nplain prose\n") is False
    assert is_markdown_payload("| id |\n| --- |\n| 1 |\n") is True


def test_probe_detects_markdown(tmp_path: Path) -> None:
    source = tmp_path / "orders.md"
    source.write_text("| id |\n| --- |\n| 1 |\n", encoding="utf-8")
    assert detect_format(source) is LocalFormat.MARKDOWN
```

Run: `uv run pytest packages/local_files/tests/test_markdown_reader.py packages/local_files/tests/test_probe.py packages/cli/tests/test_formats.py -q`

Expected: FAIL because the neutral Markdown module and `LocalFormat.MARKDOWN` do not exist yet.

- [x] **Step 2: Implement the neutral codec and probe branch**

Move the CLI parser’s grammar into `markdown_reader.py` without importing any CLI type. Keep source labels as plain strings so connector errors expose only the existing safe path label. Implement `is_markdown_payload` by requiring a non-empty first row, a valid second separator row, equal widths, and at least one pipe cell. Add `MARKDOWN = "md"` to `LocalFormat`; keep XLSX signature detection first and CSV delimiter detection second.

Update `formats.py` so `_read_markdown_table` delegates to `read_markdown_arrow` and its writer delegates to `write_markdown_table`. Preserve JSON/JSONL/CSV behavior and all existing error codes.

- [x] **Step 3: Run focused tests**

Run: `uv run pytest packages/local_files/tests/test_markdown_reader.py packages/local_files/tests/test_probe.py packages/cli/tests/test_formats.py -q`

Expected: PASS, including escaped cells, separator-looking data, empty cells, malformed widths, and Markdown detection.

- [x] **Step 4: Commit**

```bash
git add packages/local_files/src/open_table_connector/local_files/markdown_reader.py packages/local_files/src/open_table_connector/local_files/probe.py packages/local_files/src/open_table_connector/local_files/__init__.py packages/cli/src/open_table_connector/cli/formats.py packages/local_files/tests/test_markdown_reader.py packages/local_files/tests/test_probe.py packages/cli/tests/test_formats.py
git commit -m "refactor: extract neutral markdown codec"
```

---

### Task 2: Add concrete CSV, Excel, and Markdown connector modules

**Files:**
- Create: `packages/local_files/src/open_table_connector/local_files/csv_connector.py`
- Create: `packages/local_files/src/open_table_connector/local_files/excel_connector.py`
- Create: `packages/local_files/src/open_table_connector/local_files/markdown_connector.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/identity.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/manifest.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/receipts.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/inspection.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/__init__.py`
- Test: `packages/local_files/tests/test_csv_connector.py`
- Test: `packages/local_files/tests/test_excel_connector.py`
- Test: `packages/local_files/tests/test_markdown_connector.py`

**Interfaces:**
- Consumes: `read_csv_arrow`, `read_excel_arrow`, `read_markdown_arrow`, `ResourceLimits`, `TableReadRequest`, `InspectRequest`, and the existing contract result types.
- Produces:
  - `CsvReadOptions(separator: str = ",", encoding: str = "utf8")`, `CsvTableReadRequest`, and `CsvConnector` with `identity.connector_id == "csv"` and `manifest.uri_schemes == ("csv",)`.
  - `ExcelReadOptions(sheet: str | None = None, header_row: int = 1)`, `ExcelTableReadRequest`, and `ExcelConnector` with `identity.connector_id == "excel"` and `manifest.uri_schemes == ("excel",)`.
  - `MarkdownReadOptions(encoding: str = "utf8")`, `MarkdownTableReadRequest`, and `MarkdownConnector` with `identity.connector_id == "md"` and `manifest.uri_schemes == ("md",)`.
  - Each manifest advertises `uri.resolve`, `table.inspect`, `table.read.arrow`, and `table.read.polars` in `TableMode.SHEET`.

- [x] **Step 1: Write failing identity, URI, and read tests**

```python
@pytest.mark.parametrize(
    ("connector", "scheme", "connector_id"),
    (
        (CsvConnector(), "csv", "csv"),
        (ExcelConnector(), "excel", "excel"),
        (MarkdownConnector(), "md", "md"),
    ),
)
def test_concrete_connector_identity_and_scheme(connector, scheme, connector_id) -> None:
    assert connector.identity.connector_id == connector_id
    assert connector.manifest.uri_schemes == (scheme,)


def test_csv_connector_reads_only_csv_scheme(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    source.write_text("id,note\n1,ok\n", encoding="utf8")
    result = CsvConnector().read_arrow(
        CsvTableReadRequest(TableURI(f"csv://{source}"), ResourceLimits())
    )
    assert result.table.to_pylist() == [{"id": "1", "note": "ok"}]


def test_excel_connector_rejects_csv_payload(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    source.write_text("id\n1\n", encoding="utf8")
    with pytest.raises(ConnectorError) as caught:
        ExcelConnector().read_arrow(
            ExcelTableReadRequest(TableURI(f"excel://{source}"), ResourceLimits())
        )
    assert caught.value.code is ConnectorErrorCode.INVALID_URI


def test_markdown_connector_reads_pipe_table(tmp_path: Path) -> None:
    source = tmp_path / "orders.md"
    source.write_text("| id |\n| --- |\n| 1 |\n", encoding="utf8")
    result = MarkdownConnector().read_arrow(
        MarkdownTableReadRequest(TableURI(f"md://{source}"), ResourceLimits())
    )
    assert result.table.to_pylist() == [{"id": "1"}]
```

Run: `uv run pytest packages/local_files/tests/test_csv_connector.py packages/local_files/tests/test_excel_connector.py packages/local_files/tests/test_markdown_connector.py -q`

Expected: FAIL because the concrete connector classes, requests, and manifests are not present.

- [x] **Step 2: Implement concrete request and connector interfaces**

Give each request a `resolve_context` property returning `ResolveContext(resource_limits=self.resource_limits)`. Use a shared private absolute-path parser for explicit schemes; reject query parameters, unsupported hosts, relative paths, missing files, and format mismatches with stable `ConnectorError` codes. Construct receipts with the concrete `ConnectorIdentity` and the requested capability. Use `SheetConvention(sheet="data", header_rows=1, first_data_row=2)` for CSV and Markdown; use the selected worksheet and header row for Excel.

Keep `table.read.arrow` and `table.read.polars` over one canonical Arrow read so content/schema fingerprints remain identical. `inspect` must not import CLI code and must report format-appropriate columns, row count, schema fingerprint, and worksheet facts.

- [x] **Step 3: Run concrete connector tests**

Run: `uv run pytest packages/local_files/tests/test_csv_connector.py packages/local_files/tests/test_excel_connector.py packages/local_files/tests/test_markdown_connector.py -q`

Expected: PASS, including identity, explicit scheme routing, Arrow/Polars parity, inspection, limits, malformed inputs, missing files, and receipt identity assertions.

- [x] **Step 4: Commit**

```bash
git add packages/local_files/src/open_table_connector/local_files packages/local_files/tests/test_csv_connector.py packages/local_files/tests/test_excel_connector.py packages/local_files/tests/test_markdown_connector.py
git commit -m "feat: add concrete local format connectors"
```

---

### Task 3: Preserve `local_files` as a delegating compatibility facade

**Files:**
- Create: `packages/local_files/src/open_table_connector/local_files/local_files_connector.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/reader.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/resolver.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/probe.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/__init__.py`
- Test: `packages/local_files/tests/test_resolver.py`
- Test: `packages/local_files/tests/test_conformance.py`
- Test: `packages/local_files/tests/test_local_files_connector.py`

**Interfaces:**
- Consumes: `CsvConnector`, `ExcelConnector`, `MarkdownConnector`, `LocalURIResolver`, `LocalReadOptions`, and `LocalTableReadRequest`.
- Produces: `LocalFilesConnector` with its current public constructor and methods, `LocalReadOptions`, `LocalTableReadRequest`, `LocalURIResolver`, and `ResolvedLocalTable`; compatibility receipts retain `connector_id == "local_files"`.

- [x] **Step 1: Write failing facade delegation tests**

```python
@pytest.mark.parametrize(
    ("filename", "payload", "expected_format"),
    (
        ("orders.csv", "id\n1\n", LocalFormat.CSV),
        ("orders.md", "| id |\n| --- |\n| 1 |\n", LocalFormat.MARKDOWN),
    ),
)
def test_file_facade_autodetects_and_reads_supported_text_formats(
    tmp_path: Path, filename: str, payload: str, expected_format: LocalFormat
) -> None:
    source = tmp_path / filename
    source.write_text(payload, encoding="utf8")
    connector = LocalFilesConnector()
    resolved = connector.resolve(TableURI(source.as_uri()), ResolveContext())
    assert resolved.resource.format is expected_format
    result = connector.read_arrow(LocalTableReadRequest(TableURI(source.as_uri())))
    assert result.receipt.connector.connector_id == "local_files"
    assert result.table.num_rows == 1


def test_file_facade_still_reads_xlsx_and_preserves_existing_imports(tmp_path: Path) -> None:
    source = tmp_path / "orders.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["id"])
    worksheet.append(["1"])
    workbook.save(source)
    result = LocalFilesConnector().read_arrow(
        LocalTableReadRequest(TableURI(source.as_uri()))
    )
    assert result.table.column_names == ["id"]
    assert result.receipt.connector.connector_id == "local_files"
```

Run: `uv run pytest packages/local_files/tests/test_local_files_connector.py packages/local_files/tests/test_resolver.py packages/local_files/tests/test_conformance.py -q`

Expected: FAIL because the facade does not yet delegate Markdown and the compatibility reader remains format-branching code.

- [x] **Step 2: Implement the facade and format-aware resolver**

Move the existing `LocalFilesConnector` implementation into `local_files_connector.py`; keep `reader.py` as a compatibility re-export for `LocalFilesConnector`, `LocalReadOptions`, and `LocalTableReadRequest`. Extend `ResolvedLocalTable` and `LocalFormat` to include Markdown. Select a concrete connector from the resolved format and pass the existing options into its request. Use the existing low-level readers where this avoids a needless conversion, but construct the final compatibility receipt with `local_files` identity. Preserve sheet-fragment handling for XLSX and reject a CSV/Markdown request that supplies a sheet option.

Update probe errors to name all three supported formats. Ensure repeated reads, byte limits, absolute URI validation, and missing-file behavior remain unchanged.

- [x] **Step 3: Run compatibility tests**

Run: `uv run pytest packages/local_files/tests/test_local_files_connector.py packages/local_files/tests/test_resolver.py packages/local_files/tests/test_conformance.py packages/local_files/tests/test_csv_reader.py packages/local_files/tests/test_excel_reader.py packages/local_files/tests/test_probe.py -q`

Expected: PASS with existing CSV/XLSX behavior unchanged and Markdown added to `file://` autodetection.

- [x] **Step 4: Commit**

```bash
git add packages/local_files/src/open_table_connector/local_files packages/local_files/tests
git commit -m "feat: preserve local files as format facade"
```

---

### Task 4: Register explicit CLI adapters and conversion routes

**Files:**
- Modify: `packages/cli/src/open_table_connector/cli/adapters.py`
- Modify: `packages/cli/src/open_table_connector/cli/formats.py`
- Modify: `packages/cli/src/open_table_connector/cli/model.py`
- Modify: `packages/cli/src/open_table_connector/cli/registry.py`
- Modify: `packages/cli/src/open_table_connector/cli/pipeline.py`
- Modify: `packages/cli/pyproject.toml`
- Create: `packages/local_files/src/open_table_connector/local_files/excel_writer.py`
- Modify: `packages/cli/tests/test_registry.py`
- Modify: `packages/cli/tests/test_pipeline.py`
- Modify: `packages/cli/tests/test_commands.py`
- Modify: `packages/cli/tests/test_cli_e2e.py`
- Test: `packages/cli/tests/test_local_format_adapters.py`
- Test: `packages/local_files/tests/test_excel_writer.py`

**Interfaces:**
- Consumes: concrete connector classes and manifests from Task 2, `LocalFilesConnector` from Task 3, and the existing `ConnectorAdapter` protocol.
- Produces: `CsvAdapter`, `ExcelAdapter`, `MarkdownAdapter`, and the compatibility `LocalAdapter`; `build_adapters()` registers all four local identities; `csv://`, `excel://`, and `md://` are routable CLI endpoints.

- [x] **Step 1: Write failing registry and CLI tests**

```python
def test_cli_lists_concrete_local_connector_types() -> None:
    registry = build_default_registry()
    identities = {adapter.identity.connector_id for adapter in registry.list()}
    assert {"local_files", "csv", "excel", "md"} <= identities


@pytest.mark.parametrize(
    ("raw", "connector_id"),
    (("csv:///tmp/orders.csv", "csv"), ("excel:///tmp/orders.xlsx", "excel"), ("md:///tmp/orders.md", "md")),
)
def test_registry_routes_explicit_local_scheme(raw: str, connector_id: str) -> None:
    adapter = build_default_registry().connector_for(parse_endpoint(raw))
    assert adapter.identity.connector_id == connector_id


def test_cli_converts_csv_to_explicit_markdown_destination(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    destination = tmp_path / "orders.md"
    source.write_text("id\n1\n", encoding="utf8")
    summary = convert_endpoint(
        parse_endpoint(str(source)),
        parse_endpoint(f"md://{destination}"),
        build_default_registry(),
        CliOptions(),
    )
    assert summary.rows_written == 1
    assert "| id |" in destination.read_text(encoding="utf8")


def test_cli_converts_csv_to_explicit_excel_destination(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    destination = tmp_path / "orders.xlsx"
    source.write_text("id\n1\n", encoding="utf8")
    summary = convert_endpoint(
        parse_endpoint(str(source)),
        parse_endpoint(f"excel://{destination}"),
        build_default_registry(),
        CliOptions(),
    )
    assert summary.rows_written == 1
    workbook = load_workbook(destination, read_only=True, data_only=True)
    assert list(workbook.active.values) == [("id",), ("1",)]
    workbook.close()
```

Run: `uv run pytest packages/cli/tests/test_local_format_adapters.py packages/cli/tests/test_registry.py packages/cli/tests/test_pipeline.py packages/cli/tests/test_commands.py packages/cli/tests/test_cli_e2e.py -q`

Expected: FAIL because the CLI currently registers only `local_files`, treats only paths/stdin as local conversion destinations, and does not depend on the local-files distribution.

- [x] **Step 2: Implement concrete adapters and registry routing**

Add the local-files workspace dependency to `packages/cli/pyproject.toml`. Each explicit adapter converts its endpoint URI into an absolute `Path`, builds its format-specific request, delegates reads/inspection to the corresponding connector, and uses the neutral local writer for conversion targets. Add `FormatName.EXCEL`, map `.xlsx` and `excel://` to it, and implement `write_excel(table, path, sheet)` in `excel_writer.py` with openpyxl: create one workbook, write headers and rows to the selected sheet (default `Sheet1`), save it, and map file errors to the existing execution error. The compatibility `LocalAdapter` continues to own `file` and bare-path routing.

Make `_is_local` recognize `file`, `csv`, `excel`, and `md` endpoints for `convert`, while `import` still rejects all local destinations. `infer_format` must map explicit URI schemes to `FormatName.CSV`, `FormatName.EXCEL`, and `FormatName.TABLE`, and map `.csv`, `.xlsx`, `.md`, `.markdown`, and `.table` suffixes to the corresponding local codecs. Keep the existing `open-connectors` executable compatibility alias and route it to the new `open_table_connector` entry point; do not reintroduce the old Python namespace.

Register explicit adapters before the compatibility adapter so scheme routing is deterministic. Ensure `https` provider host restrictions are unaffected and `list` emits the concrete local manifests.

- [x] **Step 3: Run CLI tests and smoke commands**

Run: `uv run pytest packages/cli/tests/test_local_format_adapters.py packages/cli/tests/test_registry.py packages/cli/tests/test_pipeline.py packages/cli/tests/test_commands.py packages/cli/tests/test_cli_e2e.py -q && uv run otc --help && uv run otc list --output-format jsonl`

Expected: PASS; list output contains `csv`, `excel`, `md`, and `local_files`, explicit reads route to the concrete adapters, and existing provider CLI behavior remains green.

- [x] **Step 4: Commit**

```bash
git add packages/cli packages/cli/pyproject.toml
git commit -m "feat: route explicit local connector schemes"
```

---

### Task 5: Expand universal conformance cases and documentation

**Files:**
- Modify: `specification/conformance/universal/cases.py`
- Modify: `specification/conformance/universal/fixtures.py`
- Modify: `specification/conformance/universal/test_contract.py`
- Modify: `specification/conformance/universal/test_discovery.py`
- Modify: `specification/conformance/universal/test_table_connectors.py`
- Modify: `specification/conformance/universal/test_cli_surface.py`
- Modify: `specification/conformance/universal/README.md`
- Modify: `README.md`
- Modify: `packages/cli/README.md`
- Modify: `docs/superpowers/specs/2026-08-28-local-connector-types-design.md`
- Modify: `docs/superpowers/plans/2026-08-28-local-connector-types.md`

**Interfaces:**
- Consumes: concrete connector identities/manifests, fixture bundles, and CLI adapters from Tasks 2–4.
- Produces: named universal cases `csv`, `excel`, `md`, and `local_files`; literal metadata matrices for all four; explicit scheme and facade routing coverage; updated usage documentation.

- [ ] **Step 1: Write failing universal case and discovery tests**

```python
def test_all_current_connectors_have_named_cases() -> None:
    assert tuple(item.name for item in all_cases()) == (
        "csv",
        "excel",
        "md",
        "local_files",
        "google_sheets",
        "feishu_bitable",
        "maybe_sheet",
        "sqlite",
        "postgres",
        "dbt",
    )


@pytest.mark.parametrize("raw", ("csv:///tmp/orders.csv", "excel:///tmp/orders.xlsx", "md:///tmp/orders.md"))
def test_universal_cli_fixture_routes_explicit_local_schemes(raw: str) -> None:
    adapter = build_default_registry().connector_for(parse_endpoint(raw))
    assert adapter.identity.connector_id in {"csv", "excel", "md"}
```

Run: `uv run pytest specification/conformance/universal/test_discovery.py specification/conformance/universal/test_contract.py specification/conformance/universal/test_cli_surface.py -q`

Expected: FAIL because the universal registry still has one local case and the CLI fixture bridge has no concrete local adapters.

- [ ] **Step 2: Add concrete cases and capability bindings**

Create CSV, Excel, and Markdown fixture resources in the existing temporary bundle. Give each case literal identity, capability, mode, and scheme metadata. Reuse shared Arrow/Polars parity, receipt, inspection, limits, and malformed-input assertions. Keep `local_files` as a separate compatibility case using the CSV fixture and add a Markdown facade read assertion.

Update CLI fixture bridges to inject concrete local adapters and verify exact scheme dispatch, list output, explicit reads, compatibility file reads, and CSV-to-Markdown conversion. Keep all fixtures offline and temporary.

- [ ] **Step 3: Update docs and run the dedicated suite**

Document the four local identities, three explicit schemes, and compatibility `file://` behavior in both READMEs. Update the approved spec’s verification section only where the implementation makes an explicit behavior more precise. Run:

`uv run python -m pytest specification/conformance/universal --collect-only -q`

Expected: collection includes the four named local cases and remains above the project’s 120-test floor.

Then run: `uv run pytest specification/conformance/universal -q`

Expected: PASS with all universal connector and CLI cases green.

- [ ] **Step 4: Commit**

```bash
git add specification/conformance/universal README.md packages/cli/README.md docs/superpowers/specs/2026-08-28-local-connector-types-design.md docs/superpowers/plans/2026-08-28-local-connector-types.md
git commit -m "test: cover concrete local connector types"
```

---

### Task 6: Refresh metadata and complete verification

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `packages/local_files/pyproject.toml`
- Modify: `packages/cli/pyproject.toml`
- Test: `packages/local_files/tests/`
- Test: `packages/cli/tests/`
- Test: `specification/conformance/universal/`

**Interfaces:**
- Consumes: all completed connector, facade, CLI, and conformance work.
- Produces: a locked, buildable workspace with the four local connector identities and no CLI-to-neutral dependency cycle.

- [ ] **Step 1: Refresh and validate the lockfile**

Run:

```bash
uv sync --all-packages --group dev
uv lock --check
```

Expected: the environment installs the existing local-files distribution and the lockfile reports no drift.

- [ ] **Step 2: Run focused and full verification**

Run:

```bash
uv run pytest packages/local_files/tests packages/cli/tests -q
uv run pytest specification/conformance/universal -q
uv run pytest -q
python3 -m compileall -q packages specification/conformance
git diff --check
```

Expected: all tests pass, compilation succeeds, and `git diff --check` is silent.

- [ ] **Step 3: Build every workspace package and run CLI smoke checks**

Run:

```bash
uv build --all-packages
uv run otc list --output-format jsonl
uv run otc --help
uv run open-table-connector --help
```

Expected: every package builds successfully; list output contains `csv`, `excel`, `md`, and `local_files`; all help commands exit zero.

- [ ] **Step 4: Review tracked old-name and compatibility surfaces**

Run:

```bash
if git grep -n 'open_connectors'; then exit 1; fi
if git grep -n 'maybesheet'; then exit 1; fi
git status --short
```

Expected: no old Python namespace or old lowercase MaybeSheet identifier remains in tracked files; only pre-existing untracked scratch files may remain.
