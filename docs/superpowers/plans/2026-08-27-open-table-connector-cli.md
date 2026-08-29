# Open Table Connector CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an agent-first `otc` / `open-table-connector` CLI that reads, inspects, converts, and imports tables consistently across local formats, Google Sheets, Feishu Bitable, and MaybeSheet.

**Architecture:** Add a new CLI distribution with a small registry and adapter seam. The command layer handles endpoint parsing, format codecs, output events, exit codes, and pipeline orchestration; connector adapters translate that generic interface into the existing connector contract request types. Every data path normalizes through an Arrow table, so local-format conversion and connector-to-connector import share one implementation.

**Tech Stack:** Python 3.11+, `argparse`, `pathlib`, `csv`, `json`, `pyarrow`, `polars`, existing `open_table_connector.contract` roles, `pytest`, and the existing `uv` workspace.

**Spec:** `docs/superpowers/specs/2026-08-27-open-table-connector-cli-design.md`

## Global Constraints

- The short executable name is `otc`; the long executable name is `open-table-connector`.
- `open-connectors` is a deprecated command alias, not the repository or package name.
- `--from` and `--to` are the canonical endpoint flags for all commands that move or inspect table data.
- `--from-format` accepts `auto`, `csv`, `excel`, `json`, `jsonl`, and `table`; `--output-format` is the sole output/destination format flag.
- JSONL is the default agent output; `--output-format table` is the human-readable mode.
- Supported connector pipelines must use injected transports/process clients in tests and must not require network credentials.
- Credentials must not appear in URIs, JSONL, tables, receipts, errors, or persistent configuration files.
- Google Sheets credentials use `GOOGLE_SHEETS_ACCESS_TOKEN` and Feishu credentials use `FEISHU_TENANT_ACCESS_TOKEN`.
- MaybeSheet credentials continue through its credential-safe process environment mapping.
- Exit codes are `0` completed, `2` usage/input error, `3` unsupported capability, `4` authentication failure, `5` execution failure, and `6` conflict/write-policy failure.
- Existing connector contract types and provider adapters remain the source of truth for provider behavior.
- Every task ends with a focused test command and a separate commit containing only that task’s files.

## File Map

Create the CLI package under `packages/cli/`:

- `packages/cli/pyproject.toml`: distribution metadata, workspace dependencies, and the three console scripts.
- `packages/cli/README.md`: agent and human usage examples.
- `packages/cli/src/open_table_connector/cli/__init__.py`: public CLI package exports.
- `packages/cli/src/open_table_connector/cli/model.py`: endpoint, format, options, and pipeline result value objects.
- `packages/cli/src/open_table_connector/cli/formats.py`: local CSV/JSON/JSONL/Markdown-table readers and writers.
- `packages/cli/src/open_table_connector/cli/adapters.py`: the small generic adapter interface and provider-specific request translation.
- `packages/cli/src/open_table_connector/cli/registry.py`: URI-scheme registry and default adapter construction.
- `packages/cli/src/open_table_connector/cli/pipeline.py`: read/inspect/write/convert/import orchestration.
- `packages/cli/src/open_table_connector/cli/output.py`: JSONL events, JSON documents, CSV, table rendering, and safe error serialization.
- `packages/cli/src/open_table_connector/cli/commands.py`: command handlers over streams and the pipeline.
- `packages/cli/src/open_table_connector/cli/__main__.py`: `argparse` parser, environment resolution, and exit-code boundary.
- `packages/cli/tests/test_formats.py`: codec seam tests.
- `packages/cli/tests/test_registry.py`: URI dispatch and capability tests.
- `packages/cli/tests/test_pipeline.py`: conversion/import orchestration tests.
- `packages/cli/tests/test_commands.py`: parser, output, and exit-code tests.
- `packages/cli/tests/test_cli_e2e.py`: subprocess-level command tests using fake adapters/transports.

Modify the workspace and existing MaybeSheet package:

- `pyproject.toml`: add `packages/cli` to `tool.uv.workspace.members`; rename the root workspace project to `open-table-connector-workspace` if it still uses the former project name.
- `packages/maybe_sheet/src/open_table_connector/maybe_sheet/connector.py`: implement `table.write` through `ProcessClient` stdin.
- `packages/maybe_sheet/src/open_table_connector/maybe_sheet/process.py`: accept an optional stdin payload and pass it to `subprocess.run`.
- `packages/maybe_sheet/src/open_table_connector/maybe_sheet/identity.py`: add the `table.write` capability identity.
- `packages/maybe_sheet/src/open_table_connector/maybe_sheet/__init__.py`: export the write capability if the package exposes capability constants.
- `packages/maybe_sheet/tests/test_connector.py`: add write command, stdin, receipt, policy, and process-error tests.
- `README.md`: document the canonical `otc` commands and endpoint flag convention.

### Task 1: Scaffold the CLI distribution and shared models

**Files:**
- Create: `packages/cli/pyproject.toml`
- Create: `packages/cli/README.md`
- Create: `packages/cli/src/open_table_connector/cli/__init__.py`
- Create: `packages/cli/src/open_table_connector/cli/model.py`
- Modify: `pyproject.toml`
- Test: `packages/cli/tests/test_model.py`

**Interfaces:**
- Produces `Endpoint(raw: str, uri: TableURI | None, path: Path | None, is_stdio: bool)`, `FormatName(StrEnum)`, `CliOptions`, and `PipelineSummary` for later tasks.
- `parse_endpoint(value: str) -> Endpoint` treats strings with a non-file URI scheme as connector URIs, `file://` as an absolute local path, `-` as stdio, and all other strings as local paths.
- `parse_format(value: str | None) -> FormatName` returns `AUTO` for `None` and rejects values outside `auto`, `csv`, `json`, `jsonl`, and `table` with `ValueError`.

- [ ] **Step 1: Write the failing model tests**

```python
from pathlib import Path

import pytest

from open_table_connector.cli.model import FormatName, parse_endpoint, parse_format


def test_parse_endpoint_keeps_connector_uri_opaque() -> None:
    endpoint = parse_endpoint("gsheets://book/Orders")
    assert endpoint.uri.value == "gsheets://book/Orders"
    assert endpoint.path is None


def test_parse_endpoint_normalizes_file_uri_to_path() -> None:
    endpoint = parse_endpoint("file:///tmp/orders.csv")
    assert endpoint.uri is None
    assert endpoint.path == Path("/tmp/orders.csv")


def test_parse_format_defaults_to_auto_and_rejects_unknown_values() -> None:
    assert parse_format(None) is FormatName.AUTO
    with pytest.raises(ValueError, match="unsupported format"):
        parse_format("yaml")
```

- [ ] **Step 2: Run the model tests to verify they fail**

Run: `uv run pytest packages/cli/tests/test_model.py -q`

Expected: collection fails because `packages/cli` and `open_table_connector.cli.model` do not exist.

- [ ] **Step 3: Add the package and implement the model seam**

Create the package metadata with these exact scripts and workspace dependencies:

```toml
[project.scripts]
otc = "open_table_connector.cli.__main__:main"
open-table-connector = "open_table_connector.cli.__main__:main"
open-connectors = "open_table_connector.cli.__main__:main"
```

Implement `FormatName` as a `StrEnum` with lower-case values `auto`, `csv`, `json`, `jsonl`, and `table`. `parse_endpoint` must use `TableURI` validation for connector URIs and convert `file://` paths through `url2pathname`; a bare path must remain a `Path` without requiring the file to exist. `CliOptions` must be an immutable dataclass with defaults `from_format=FormatName.AUTO`, `to_format=FormatName.AUTO`, `output_format=FormatName.JSONL`, `limit=None`, `timeout=None`, `sheet=None`, `range=None`, `field_names=()`, `if_exists="error"`, `token=None`, and `target=None`; validate positive limits/timeouts and convert field names to a tuple. `PipelineSummary` must contain `status`, `rows_read`, `rows_written`, `source_receipt`, and `destination_receipt`.

- [ ] **Step 4: Run the model tests to verify they pass**

Run: `uv run pytest packages/cli/tests/test_model.py -q`

Expected: 3 passed.

- [ ] **Step 5: Commit the scaffold**

```bash
git add pyproject.toml packages/cli
git commit -m "feat: scaffold open table connector cli"
```

### Task 2: Implement local format codecs

**Files:**
- Create: `packages/cli/src/open_table_connector/cli/formats.py`
- Test: `packages/cli/tests/test_formats.py`

**Interfaces:**
- Produces `read_local(source: Endpoint, format_name: FormatName, stream: TextIO | None = None) -> pa.Table`.
- Produces `write_local(table: pa.Table, destination: Endpoint, format_name: FormatName, stream: TextIO | None = None) -> None`.
- Produces `infer_format(endpoint: Endpoint, explicit: FormatName) -> FormatName`.
- `read_local` accepts CSV, JSON arrays of objects, JSONL objects, and Markdown pipe tables; `write_local` emits CSV, JSON arrays, JSONL, or aligned human-readable tables.

- [ ] **Step 1: Write failing codec tests**

```python
import io

import pyarrow as pa

from open_table_connector.cli.formats import read_local, write_local
from open_table_connector.cli.model import Endpoint, FormatName, parse_endpoint


def test_json_array_reader_unions_object_keys(tmp_path) -> None:
    source = tmp_path / "rows.json"
    source.write_text('[{"id":"a","amount":1},{"id":"b","name":"Bee"}]')
    table = read_local(parse_endpoint(str(source)), FormatName.JSON)
    assert table.column_names == ["id", "amount", "name"]
    assert table.to_pylist() == [
        {"id": "a", "amount": 1, "name": None},
        {"id": "b", "amount": None, "name": "Bee"},
    ]


def test_jsonl_reader_ignores_blank_lines(tmp_path) -> None:
    source = tmp_path / "rows.jsonl"
    source.write_text('{"id":"a"}\n\n{"id":"b"}\n')
    assert read_local(parse_endpoint(str(source)), FormatName.JSONL).num_rows == 2


def test_markdown_table_reader_accepts_separator_row(tmp_path) -> None:
    source = tmp_path / "rows.table"
    source.write_text("| id | amount |\n| --- | ---: |\n| a | 1 |\n")
    assert read_local(parse_endpoint(str(source)), FormatName.TABLE).to_pylist() == [{"id": "a", "amount": "1"}]


def test_jsonl_writer_emits_one_object_per_line() -> None:
    stream = io.StringIO()
    write_local(pa.table({"id": ["a"], "amount": [1]}), parse_endpoint("-"), FormatName.JSONL, stream)
    assert stream.getvalue() == '{"id":"a","amount":1}\n'
```

- [ ] **Step 2: Run codec tests to verify they fail**

Run: `uv run pytest packages/cli/tests/test_formats.py -q`

Expected: collection fails because `formats.py` is missing.

- [ ] **Step 3: Implement codecs with explicit parsing rules**

Use `csv.DictReader` for CSV and preserve empty cells as `None`. For JSON, require a top-level list of mappings. For JSONL, reject non-object records and include the 1-based line number in `ConnectorError.safe_details`. For Markdown tables, split pipe-delimited rows, trim cells, recognize an optional separator row when every cell matches `:?-+:?`, and reject inconsistent column counts. Use a deterministic union-of-keys order based on first appearance. Convert nested list/mapping values to canonical JSON strings before creating Arrow arrays. For output, write UTF-8 text, use compact sorted-key JSON for JSONL, and use `csv.writer` for CSV. When destination is `-`, write to the passed stream and never close it.

- [ ] **Step 4: Run codec tests to verify they pass**

Run: `uv run pytest packages/cli/tests/test_formats.py -q`

Expected: 4 passed.

- [ ] **Step 5: Commit the codecs**

```bash
git add packages/cli/src/open_table_connector/cli/formats.py packages/cli/tests/test_formats.py
git commit -m "feat: add otc table format codecs"
```

### Task 3: Add MaybeSheet table writing

**Files:**
- Modify: `packages/maybe_sheet/src/open_table_connector/maybe_sheet/process.py`
- Modify: `packages/maybe_sheet/src/open_table_connector/maybe_sheet/connector.py`
- Modify: `packages/maybe_sheet/src/open_table_connector/maybe_sheet/identity.py`
- Modify: `packages/maybe_sheet/src/open_table_connector/maybe_sheet/__init__.py`
- Test: `packages/maybe_sheet/tests/test_connector.py`

**Interfaces:**
- Extends `ProcessClient.run` to `run(argv: tuple[str, ...], *, credentials: Mapping[str, str] | None = None, stdin: str | None = None) -> Mapping[str, Any]`.
- `MaybeSheetConnector.write(request: TableWriteRequest) -> TableWriteResult` uses `request.table` as the MaybeSheet target, defaults to base mode, and sends JSONL rows through stdin.
- `append` is supported; `replace` and `error` raise `ConnectorErrorCode.UNSUPPORTED_CAPABILITY` with safe `if_exists` details until the process protocol exposes an explicit replace/preflight operation.

- [ ] **Step 1: Write failing MaybeSheet writer tests**

```python
import polars as pl
import pytest

from open_table_connector.contract import ConnectorError, ConnectorErrorCode, TableWriteRequest, TableURI
from open_table_connector.maybe_sheet import MaybeSheetConnector


class Process:
    def __init__(self):
        self.calls = []

    def run(self, argv, *, credentials=None, stdin=None):
        self.calls.append((argv, credentials, stdin))
        return {"status": "completed", "rows_written": 1, "receipt_id": "safe-ref"}


def test_maybe_sheet_write_sends_jsonl_to_process() -> None:
    process = Process()
    result = MaybeSheetConnector(process).write(
        TableWriteRequest(TableURI("https://www.maybe.ai/docs/spreadsheets/d/doc"), pl.DataFrame({"id": ["1"]}), table="R_orders", if_exists="append")
    )
    assert process.calls[0][0] == ("mbs", "db-table", "write", "--uri", "https://www.maybe.ai/docs/spreadsheets/d/doc", "--target", "R_orders", "--input", "-")
    assert process.calls[0][2] == '{"id":"1"}\n'
    assert result.affected_rows == 1
    assert result.receipt.vendor_receipt_ref == "safe-ref"


@pytest.mark.parametrize("if_exists", ["replace", "error"])
def test_maybe_sheet_rejects_unsupported_write_policies(if_exists) -> None:
    with pytest.raises(ConnectorError) as error:
        MaybeSheetConnector(Process()).write(
            TableWriteRequest(TableURI("https://www.maybe.ai/docs/spreadsheets/d/doc"), pl.DataFrame({"id": ["1"]}), table="R_orders", if_exists=if_exists)
        )
    assert error.value.code is ConnectorErrorCode.UNSUPPORTED_CAPABILITY
```

- [ ] **Step 2: Run the new writer tests to verify they fail**

Run: `uv run pytest packages/maybe_sheet/tests/test_connector.py -q`

Expected: the write test fails because the current connector rejects `table.write`.

- [ ] **Step 3: Implement stdin transport and writer**

Add `stdin` to the protocol and to `SubprocessProcessClient.run`; pass it as `input=stdin` to `subprocess.run`. In `MaybeSheetConnector.write`, validate `if_exists`, validate a non-empty `request.table`, serialize each frame row as a compact JSON object plus newline, select `db-table` as the process verb, and invoke `ProcessClient.run(("mbs", "db-table", "write", "--uri", request.uri.value, "--target", request.table, "--input", "-"), credentials=None, stdin=payload)`. Build a `NeutralReceipt` from the response hash, schema/content fingerprints, `BaseConvention(ordinal_snapshot_id=revision)`, and `TABLE_WRITE_CAPABILITY`. Map process `ConnectorError` unchanged and wrap unexpected exceptions as `EXECUTION_FAILED`.

- [ ] **Step 4: Run all MaybeSheet tests**

Run: `uv run pytest packages/maybe_sheet/tests -q`

Expected: existing read/process tests and the new write tests pass.

- [ ] **Step 5: Commit MaybeSheet writing**

```bash
git add packages/maybe_sheet
git commit -m "feat: add maybe_sheet table writes"
```

### Task 4: Define the registry and generic connector adapters

**Files:**
- Create: `packages/cli/src/open_table_connector/cli/adapters.py`
- Create: `packages/cli/src/open_table_connector/cli/registry.py`
- Test: `packages/cli/tests/test_registry.py`

**Interfaces:**
- Produces `ConnectorAdapter` with `schemes: tuple[str, ...]`, `identity`, `capabilities`, `read(endpoint: Endpoint, options: CliOptions) -> ArrowReadResult`, `inspect(endpoint: Endpoint, options: CliOptions) -> TableInspection`, and `write(endpoint: Endpoint, table: pa.Table, options: CliOptions) -> TableWriteResult`.
- Produces `ConnectorRegistry.register(adapter)`, `connector_for(endpoint)`, `list()`, and `require_capability(endpoint, capability_id)`.
- Produces `build_default_registry(env: Mapping[str, str] | None = None, transports: Mapping[str, Any] | None = None) -> ConnectorRegistry`.

- [ ] **Step 1: Write failing registry tests**

```python
import pytest

from open_table_connector.cli.model import parse_endpoint
from open_table_connector.cli.registry import build_default_registry
from open_table_connector.contract import ConnectorError, ConnectorErrorCode


def test_default_registry_lists_all_supported_adapter_schemes() -> None:
    schemes = {scheme for adapter in build_default_registry(env={}).list() for scheme in adapter.schemes}
    assert {"gsheets", "https", "feishu", "feishu_bitable", "maybe", "file"}.issubset(schemes)


def test_registry_dispatches_google_sheet_uri() -> None:
    adapter = build_default_registry(env={}).connector_for(parse_endpoint("gsheets://book/Orders"))
    assert adapter.identity.connector_id == "google_sheets"


def test_registry_reports_unsupported_capability_before_writing() -> None:
    registry = build_default_registry(env={})
    with pytest.raises(ConnectorError) as error:
        registry.require_capability(parse_endpoint("maybe://doc/target"), "table.replace")
    assert error.value.code is ConnectorErrorCode.UNSUPPORTED_CAPABILITY
```

- [ ] **Step 2: Run registry tests to verify they fail**

Run: `uv run pytest packages/cli/tests/test_registry.py -q`

Expected: collection fails because the registry and adapter modules are missing.

- [ ] **Step 3: Implement adapter translations and registry**

Implement one adapter wrapper per provider. The Google wrapper constructs `GoogleSheetsTableReadRequest` with `GoogleSheetsReadOptions(range=options.range, sheet=options.sheet)` and obtains its token from `options.token` or `GOOGLE_SHEETS_ACCESS_TOKEN`. The Feishu wrapper constructs `FeishuBitableTableReadRequest` with `FeishuBitableReadOptions(field_names=options.field_names)` and obtains `FEISHU_TENANT_ACCESS_TOKEN`. The MaybeSheet wrapper parses `maybe://DOCUMENT/TARGET` into the URI plus `request.table=TARGET` and constructs `MaybeSheetReadRequest` for reads; its write method delegates to the new writer. The local adapter delegates to `formats.py` and reports `table.read.arrow`, `table.read.polars`, `table.inspect`, and `table.write`.

Register `gsheets`, Google Sheets `https` URLs, `feishu`, `feishu_bitable`, `maybe`, `file`, and bare local paths. Restrict `https` dispatch to `docs.google.com` for Google Sheets and `www.maybe.ai` for MaybeSheet; reject other hosts with `INVALID_URI`. Construct provider connectors with injected transports from the optional `transports` mapping so tests can assert exact HTTP requests. `require_capability` must raise `UNSUPPORTED_CAPABILITY` with `scheme` and `capability` safe details.

- [ ] **Step 4: Run registry tests to verify they pass**

Run: `uv run pytest packages/cli/tests/test_registry.py -q`

Expected: 3 passed.

- [ ] **Step 5: Commit the registry seam**

```bash
git add packages/cli/src/open_table_connector/cli/adapters.py packages/cli/src/open_table_connector/cli/registry.py packages/cli/tests/test_registry.py
git commit -m "feat: add otc connector registry"
```

### Task 5: Implement the Arrow pipeline for read, inspect, convert, and import

**Files:**
- Create: `packages/cli/src/open_table_connector/cli/pipeline.py`
- Test: `packages/cli/tests/test_pipeline.py`

**Interfaces:**
- Produces `read_endpoint(endpoint: Endpoint, registry: ConnectorRegistry, options: CliOptions) -> ArrowReadResult`.
- Produces `inspect_endpoint(endpoint: Endpoint, registry: ConnectorRegistry, options: CliOptions) -> TableInspection`.
- Produces `convert_endpoint(source: Endpoint, destination: Endpoint, registry: ConnectorRegistry, options: CliOptions) -> PipelineSummary`.
- Produces `import_endpoint(source: Endpoint, destination: Endpoint, registry: ConnectorRegistry, options: CliOptions) -> PipelineSummary`.
- Both conversion and import read exactly once into Arrow, then write exactly once; `convert` requires a local destination codec and `import` requires a writable destination adapter.

- [ ] **Step 1: Write failing pipeline tests**

```python
import json

import pyarrow as pa

from open_table_connector.cli.pipeline import convert_endpoint, import_endpoint
from open_table_connector.cli.model import CliOptions, parse_endpoint
from open_table_connector.cli.registry import build_default_registry


def test_convert_csv_to_json_writes_union_rows(tmp_path) -> None:
    source = tmp_path / "orders.csv"
    destination = tmp_path / "orders.json"
    source.write_text("id,amount\na,1\n")
    summary = convert_endpoint(parse_endpoint(str(source)), parse_endpoint(str(destination)), build_default_registry(env={}), CliOptions())
    assert summary.status == "completed"
    assert json.loads(destination.read_text()) == [{"id": "a", "amount": "1"}]
    assert summary.rows_read == 1


def test_import_uses_destination_adapter_and_returns_both_receipts(fake_registry, tmp_path) -> None:
    source = tmp_path / "orders.jsonl"
    source.write_text('{"id":"a"}\n')
    summary = import_endpoint(parse_endpoint(str(source)), parse_endpoint("gsheets://book/Orders"), fake_registry, CliOptions(token="token"))
    assert summary.rows_read == 1
    assert summary.rows_written == 1
    assert summary.source_receipt is not None
    assert summary.destination_receipt is not None
```

- [ ] **Step 2: Run pipeline tests to verify they fail**

Run: `uv run pytest packages/cli/tests/test_pipeline.py -q`

Expected: collection fails because `pipeline.py` is missing.

- [ ] **Step 3: Implement the pipeline**

For local sources, call `read_local`; for connector sources, call the adapter’s `read` method. Apply `ResourceLimits(max_rows=options.limit, timeout_seconds=options.timeout)` in adapter request construction. `read_endpoint` must return the provider’s receipt unchanged. `inspect_endpoint` must call the adapter’s inspect method and never materialize a second independent read in the CLI layer.

For `convert_endpoint`, reject connector destinations with `UNSUPPORTED_CAPABILITY`; infer the destination codec from `--output-format` or extension, default stdout to JSONL, write with `write_local`, and return a summary with `rows_written=table.num_rows` and the source receipt. For `import_endpoint`, reject local destinations with `UNSUPPORTED_CAPABILITY` because `convert` owns local writes; call `require_capability(destination, "table.write")` before reading, then invoke the destination adapter exactly once. Drop `_record_id` only when writing from Feishu to a local/other destination if the destination adapter explicitly marks it provider-owned; otherwise preserve all columns. Return source and destination receipts in `PipelineSummary`.

- [ ] **Step 4: Run pipeline tests to verify they pass**

Run: `uv run pytest packages/cli/tests/test_pipeline.py -q`

Expected: 2 passed.

- [ ] **Step 5: Commit the pipeline**

```bash
git add packages/cli/src/open_table_connector/cli/pipeline.py packages/cli/tests/test_pipeline.py
git commit -m "feat: add otc table pipelines"
```

### Task 6: Implement structured output and command handlers

**Files:**
- Create: `packages/cli/src/open_table_connector/cli/output.py`
- Create: `packages/cli/src/open_table_connector/cli/commands.py`
- Test: `packages/cli/tests/test_commands.py`

**Interfaces:**
- Produces `emit_read(result: ArrowReadResult, output_format: FormatName, out: TextIO) -> None`.
- Produces `emit_summary(summary: PipelineSummary, out: TextIO) -> None`.
- Produces `emit_error(error: BaseException, err: TextIO) -> int`.
- Produces `run_command(args: Namespace, registry: ConnectorRegistry, out: TextIO, err: TextIO) -> int`.

- [ ] **Step 1: Write failing command/output tests**

```python
import io
import json

from open_table_connector.cli.commands import run_command


def test_read_defaults_to_jsonl_row_events_then_summary(fake_registry) -> None:
    out, err = io.StringIO(), io.StringIO()
    code = run_command(Namespace(command="read", from_value="data.jsonl", output_format="jsonl"), fake_registry, out, err)
    events = [json.loads(line) for line in out.getvalue().splitlines()]
    assert code == 0
    assert events[0]["event"] == "row"
    assert events[-1]["event"] == "summary"
    assert err.getvalue() == ""


def test_auth_error_is_safe_json_on_stderr(fake_registry) -> None:
    out, err = io.StringIO(), io.StringIO()
    code = run_command(Namespace(command="read", from_value="gsheets://book/Orders", output_format="jsonl"), fake_registry, out, err)
    payload = json.loads(err.getvalue())
    assert code == 4
    assert payload["code"] == "authentication"
    assert "token" not in err.getvalue().casefold()
```

- [ ] **Step 2: Run command tests to verify they fail**

Run: `uv run pytest packages/cli/tests/test_commands.py -q`

Expected: collection fails because `output.py` and `commands.py` are missing.

- [ ] **Step 3: Implement output events and handlers**

JSONL read output must emit `{"event":"row","row":{...}}` once per row followed by `{"event":"summary","status":"completed","rows":N,"receipt":...}`. JSON output must emit one object with `rows` and `receipt`; CSV output must emit a header and rows; table output must emit aligned columns without event wrappers. Import output must emit one completion object with status, source/destination receipts, and row counts. `emit_error` must recognize `ConnectorError`, map its code to the global exit table, serialize only `error.to_wire()`, and map `ValueError`/`OSError` to usage or execution errors without including exception text that may contain credentials.

Handlers must use only the endpoint flags from the parser namespace: `from_value`, `to_value`, `from_format`, `to_format`, `output_format`, `if_exists`, `limit`, `timeout`, `sheet`, `range`, `field_name`, `token`, and `target`. `list` emits one JSON object per registered adapter with connector ID, schemes, capabilities, and modes. `inspect` emits a single JSON object containing the inspection fields. `read` calls `read_endpoint` and `emit_read`. `convert` and `import` call their respective pipeline functions and emit one summary.

- [ ] **Step 4: Run command tests to verify they pass**

Run: `uv run pytest packages/cli/tests/test_commands.py -q`

Expected: 2 passed.

- [ ] **Step 5: Commit output and handlers**

```bash
git add packages/cli/src/open_table_connector/cli/output.py packages/cli/src/open_table_connector/cli/commands.py packages/cli/tests/test_commands.py
git commit -m "feat: add otc structured command output"
```

### Task 7: Add the executable parser, environment credentials, and end-to-end tests

**Files:**
- Create: `packages/cli/src/open_table_connector/cli/__main__.py`
- Create: `packages/cli/tests/test_cli_e2e.py`
- Modify: `packages/cli/src/open_table_connector/cli/__init__.py`
- Modify: `packages/cli/README.md`
- Modify: `README.md`

**Interfaces:**
- Produces `build_parser() -> argparse.ArgumentParser` and `main(argv: Sequence[str] | None = None) -> int`.
- The parser requires `--from` for `inspect`/`read`, requires both `--from` and `--to` for `convert`/`import`, and accepts `--from-format`, `--output-format`, `--if-exists`, `--limit`, `--timeout`, `--sheet`, `--range`, repeated `--field-name`, `--token`, and `--target`.

- [ ] **Step 1: Write failing parser and subprocess tests**

```python
import json
import subprocess
import sys


def test_parser_requires_explicit_from_and_to_for_import() -> None:
    result = subprocess.run([sys.executable, "-m", "open_table_connector.cli", "import", "--from", "rows.csv"], capture_output=True, text=True)
    assert result.returncode == 2
    assert "--to" in result.stderr


def test_otc_convert_csv_to_jsonl(tmp_path) -> None:
    source = tmp_path / "rows.csv"
    source.write_text("id\na\n")
    result = subprocess.run(["otc", "convert", "--from", str(source), "--to", "-", "--output-format", "jsonl"], capture_output=True, text=True)
    assert result.returncode == 0
    assert json.loads(result.stdout.splitlines()[0]) == {"id": "a"}
```

- [ ] **Step 2: Run executable tests to verify they fail**

Run: `uv run pytest packages/cli/tests/test_cli_e2e.py -q`

Expected: the module and console scripts are not available.

- [ ] **Step 3: Implement parser and entrypoint**

Create subparsers for `list`, `inspect`, `read`, `convert`, and `import`. Use `dest="from_value"` for `--from` because `from` is a Python keyword. Use `action="append"` for `--field-name`. Resolve tokens from `--token` first, then provider environment variables in `build_default_registry`; never put the token into an endpoint or output object. `main` must catch parser errors as exit code 2, build the default registry, route to `run_command`, flush output, and return the handler code. Add the package’s `__main__` guard and document examples using `otc` plus the long-form command.

Add a compatibility alias test by invoking `python -m open_table_connector.cli` and `otc`; the console-script aliases are verified by `uv run otc --help`, `uv run open-table-connector --help`, and `uv run open-connectors --help`.

- [ ] **Step 4: Run end-to-end tests and help commands**

Run: `uv run pytest packages/cli/tests/test_cli_e2e.py -q && uv run otc --help && uv run open-table-connector --help && uv run open-connectors --help`

Expected: 2 end-to-end tests pass and all three help commands exit 0.

- [ ] **Step 5: Commit the executable and docs**

```bash
git add packages/cli/src/open_table_connector/cli/__main__.py packages/cli/src/open_table_connector/cli/__init__.py packages/cli/tests/test_cli_e2e.py packages/cli/README.md README.md
git commit -m "feat: expose otc command line interface"
```

### Task 8: Add provider-specific pipeline coverage and harden security/error behavior

**Files:**
- Modify: `packages/cli/tests/test_pipeline.py`
- Modify: `packages/cli/tests/test_commands.py`
- Modify: `packages/cli/tests/test_registry.py`
- Modify: `packages/google_sheets/tests/test_connector.py`
- Modify: `packages/feishu_bitable/tests/test_connector.py`
- Modify: `packages/maybe_sheet/tests/test_connector.py`

**Interfaces:**
- No new public interface; this task verifies that the existing adapters and CLI seam compose correctly for the named cross-connector flows.

- [ ] **Step 1: Add failing cross-connector and security tests**

Add tests with fake provider transports/process clients for:

```python
def test_csv_to_google_sheets_import_sends_header_and_rows(tmp_path):
    source = tmp_path / "orders.csv"
    source.write_text("id,amount\na,1\n")
    transport = RecordingTransport({"GET": {"values": [["unused"]]}, "PUT": {"updatedRows": 2}})
    registry = build_default_registry(env={"GOOGLE_SHEETS_ACCESS_TOKEN": "token"}, transports={"google_sheets": transport})
    summary = import_endpoint(parse_endpoint(str(source)), parse_endpoint("gsheets://book/Orders"), registry, CliOptions(if_exists="replace"))
    assert summary.rows_read == 1
    assert transport.calls[0].body["values"] == [["id", "amount"], ["a", "1"]]


def test_google_sheets_to_maybe_sheet_import_sends_jsonl_to_process(tmp_path):
    source = tmp_path / "orders.jsonl"
    source.write_text('{"id":"a"}\n')
    process = RecordingProcess()
    registry = build_default_registry(env={"MAYBE_SHEET_ACCESS_TOKEN": "token"}, processes={"maybe_sheet": process})
    summary = import_endpoint(parse_endpoint(str(source)), parse_endpoint("maybe://doc/R_orders"), registry, CliOptions(if_exists="append"))
    assert summary.rows_written == 1
    assert process.stdin_payload == '{"id":"a"}\n'


def test_feishu_to_jsonl_preserves_record_id(tmp_path):
    destination = tmp_path / "records.jsonl"
    transport = RecordingTransport({"GET": {"code": 0, "data": {"items": [{"record_id": "rec_1", "fields": {"name": "Ada"}}], "has_more": False}}})
    registry = build_default_registry(env={"FEISHU_TENANT_ACCESS_TOKEN": "token"}, transports={"feishu_bitable": transport})
    summary = convert_endpoint(parse_endpoint("feishu://app/table"), parse_endpoint(str(destination)), registry, CliOptions())
    assert summary.rows_read == 1
    assert json.loads(destination.read_text()) == [{"_record_id": "rec_1", "name": "Ada"}]


def test_provider_auth_failure_maps_to_exit_code_four(fake_registry):
    code = run_command(Namespace(command="read", from_value="gsheets://book/Orders", output_format="jsonl"), fake_registry, io.StringIO(), io.StringIO())
    assert code == 4


def test_connector_error_output_contains_no_access_token(fake_registry):
    error = ConnectorError.authentication("authentication failed", safe_details={"token": "access-token"})
    output = io.StringIO()
    assert emit_error(error, output) == 4
    assert "access-token" not in output.getvalue()


def test_row_limit_is_applied_before_destination_write(tmp_path):
    source = tmp_path / "rows.jsonl"
    source.write_text('{"id":"a"}\n{"id":"b"}\n')
    transport = RecordingTransport({"PUT": {"updatedRows": 2}})
    registry = build_default_registry(env={"GOOGLE_SHEETS_ACCESS_TOKEN": "token"}, transports={"google_sheets": transport})
    summary = import_endpoint(parse_endpoint(str(source)), parse_endpoint("gsheets://book/Orders"), registry, CliOptions(limit=1, if_exists="replace"))
    assert summary.rows_read == 1
    assert transport.calls[0].body["values"] == [["id"], ["a"]]
```

Each test must assert exact destination request bodies/argv, row counts, receipt presence, and absence of the token string from stdout and stderr. Define `RecordingTransport` with `calls: list[RecordedCall]` and a response map keyed by HTTP method, and define `RecordingProcess` with `calls`, `stdin_payload`, and a `run(argv, *, credentials=None, stdin=None)` method that records the arguments and returns a completed response. Do not use live network calls.

- [ ] **Step 2: Run the new integration tests to verify the missing behavior**

Run: `uv run pytest packages/cli/tests/test_pipeline.py packages/cli/tests/test_commands.py packages/cli/tests/test_registry.py packages/google_sheets/tests packages/feishu_bitable/tests packages/maybe_sheet/tests -q`

Expected: at least the Google-to-MaybeSheet import test fails until the MaybeSheet adapter target mapping and write receipt path are complete; all failures identify concrete missing behavior.

- [ ] **Step 3: Implement only the failing behavior**

Ensure the source row limit is enforced in the adapter request, destination writes receive exactly the limited Arrow table, Feishu `_record_id` remains available to non-Feishu destinations, provider errors map to the documented exit codes, and `ConnectorError.to_wire()` output is the only error payload serialized by the CLI. Do not add retries, schema mapping, formula handling, or persistent credentials.

- [ ] **Step 4: Run the integration tests to verify they pass**

Run: `uv run pytest packages/cli/tests/test_pipeline.py packages/cli/tests/test_commands.py packages/cli/tests/test_registry.py packages/google_sheets/tests packages/feishu_bitable/tests packages/maybe_sheet/tests -q`

Expected: all selected tests pass.

- [ ] **Step 5: Commit integration coverage**

```bash
git add packages/cli/tests packages/google_sheets/tests packages/feishu_bitable/tests packages/maybe_sheet/tests
git commit -m "test: cover otc connector pipelines"
```

### Task 9: Complete workspace verification, packaging, and repository handoff

**Files:**
- Modify: `pyproject.toml` to add `packages/cli` as a workspace member and use `open-table-connector-workspace` for the root workspace project name.
- Modify: `uv.lock` by running `uv lock` after the workspace member change.
- Test: all existing tests plus all CLI tests.

**Interfaces:**
- No new interface; this task proves the spec requirements against the complete current workspace and verifies the published package includes the CLI entry points and connector manifests.

- [ ] **Step 1: Sync the expanded workspace**

Run: `uv sync --all-packages`

Expected: dependency resolution completes without changing provider versions outside the new CLI workspace member.

- [ ] **Step 2: Run the full test suite**

Run: `uv run pytest`

Expected: all existing tests and new CLI/MaybeSheet tests pass with zero failures.

- [ ] **Step 3: Run static and packaging checks**

Run: `git diff --check && python3 -m compileall -q packages && uv build --all-packages`

Expected: no whitespace errors, no compile errors, and successful source/wheel builds for the CLI and all existing workspace packages. Inspect the build output or wheel contents to confirm the three console scripts and `manifest.json` files are included.

- [ ] **Step 4: Run command smoke tests**

Run: `uv run otc list --output-format jsonl`, `uv run otc --help`, `uv run open-table-connector --help`, and `uv run open-connectors --help`.

Expected: help commands exit 0; `list` emits one valid JSON object per registered adapter and never emits credentials.

- [ ] **Step 5: Verify git and remote state**

Run: `git status --short --branch`, `git log -5 --oneline`, and `git ls-remote origin refs/heads/main`.

Expected: only intentionally preserved unrelated `.DS_Store` files remain untracked, the branch tracks `origin/main`, and the final pushed commit hash matches the local HEAD after the user-authorized push.

- [ ] **Step 6: Commit lockfile/metadata changes and push**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: finalize open table connector cli workspace"
git push origin main
```

## Completion Audit

Before claiming completion, verify each requirement against the following evidence:

1. `otc`, `open-table-connector`, and `open-connectors --help` prove the executable names and compatibility alias.
2. `test_cli_e2e.py` proves `--from`/`--to` are accepted consistently and required for movement commands.
3. `test_formats.py` proves CSV, JSON, JSONL, and Markdown table input plus JSON/JSONL/CSV/table output.
4. `test_pipeline.py` and provider integration tests prove CSV to Google Sheets and Google Sheets to MaybeSheet.
5. `test_registry.py` proves scheme discovery and capability failures before writes.
6. Command tests prove JSONL default row/summary events, human table output, safe errors, and exit-code mapping.
7. MaybeSheet tests prove stdin write invocation, append support, explicit rejection of unsupported policies, and safe process errors.
8. Full `uv run pytest` and `uv build --all-packages` prove workspace-wide test and build health.
9. `git ls-remote` proves the final implementation is pushed to `OmniMCP-AI/open-table-connector`.
