from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pyarrow as pa
import pytest

from open_table_connector.contract import TableURI
from open_table_connector.conformance import (
    ManagedLifecycleCase,
    TemporalSemanticCase,
    load_temporal_cases,
)
from open_table_connector.local_files import (
    CsvManagedTemporalStore,
    CsvTemporalExecutor,
    ExcelTemporalExecutor,
    JsonTemporalExecutor,
    encode_json_table,
    encode_jsonl_table,
)
from open_table_connector.maybe_sheet import MaybeSheetTemporalExecutor
from open_table_connector.postgres import PostgresTemporalExecutor
from open_table_connector.sqlite import SQLiteTemporalExecutor
from open_table_connector.timeseries import (
    ArrowArtifactReference,
    ManagedCommitRequest,
    ManagedStageRequest,
    PolarsTemporalExecutor,
    ResourceBounds,
    TemporalExecutionRequest,
    temporal_descriptor_hash,
)
from specification.conformance.timeseries.support import (
    MemoryTemporalSource,
    RecordingTemporalProcess,
    create_ticks,
    descriptor,
    sqlite_uri,
    ticks_table,
    value_workbook,
)


FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures/timeseries/v1"


@pytest.fixture(
    params=load_temporal_cases(FIXTURE_ROOT),
    ids=lambda case: case.case_id,
)
def semantic_case(request) -> TemporalSemanticCase:
    return request.param


def put_artifact(root: Path, table: pa.Table | None = None) -> ArrowArtifactReference:
    value = table if table is not None else ticks_table()
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, value.schema) as writer:
        writer.write_table(value)
    data = sink.getvalue().to_pybytes()
    digest = hashlib.sha256(data).hexdigest()
    relative = Path("sha256") / f"{digest}.arrow"
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(0o600)
    return ArrowArtifactReference(relative.as_posix(), f"sha256:{digest}", len(data))


def lifecycle_case(artifact_root: Path, target: TableURI) -> ManagedLifecycleCase:
    table = ticks_table()
    bounds = ResourceBounds(max_rows=1000, max_bytes=1000000, max_duration_ms=5000)
    stage = ManagedStageRequest(
        "conformance-stage",
        put_artifact(artifact_root, table),
        temporal_descriptor_hash(descriptor(), table.schema),
        target,
        target,
        "conformance-idempotency",
        bounds,
    )
    return ManagedLifecycleCase(
        stage_request=stage,
        commit_operation_id="conformance-commit",
        readback_operation_id="conformance-readback",
        abort_operation_id="conformance-abort",
        resource_bounds=bounds,
    )


@pytest.fixture(
    params=("polars", "csv", "json", "jsonl", "sqlite", "postgres", "excel", "maybe_sheet")
)
def provider_semantic_case(request, semantic_case, tmp_path):
    provider = request.param
    plan = semantic_case.request.plan
    operation_id = f"{provider}-{plan.operation.to_wire()['kind']}"
    snapshot_reference = None
    if provider == "polars":
        executor = PolarsTemporalExecutor(MemoryTemporalSource())
        target = semantic_case.request.target
    elif provider == "csv":
        artifact_root = tmp_path / "csv-artifacts"
        target = TableURI(
            (tmp_path / "csv-ticks").as_uri().replace("file://", "managed+csv://", 1)
        )
        store = CsvManagedTemporalStore(artifact_root, descriptor())
        lifecycle = lifecycle_case(artifact_root, target)
        staged = store.stage(lifecycle.stage_request)
        committed = store.commit(
            ManagedCommitRequest(
                lifecycle.commit_operation_id,
                target,
                staged.stage_id,
                staged.idempotency_key,
                lifecycle.resource_bounds,
            )
        )
        snapshot_reference = committed.snapshot_reference
        executor = CsvTemporalExecutor(descriptor(), store)
    elif provider in {"json", "jsonl"}:
        path = tmp_path / f"ticks.{provider}"
        encoder = encode_json_table if provider == "json" else encode_jsonl_table
        path.write_text(encoder(ticks_table()), encoding="utf-8")
        target = TableURI(path.as_uri().replace("file://", f"{provider}://", 1))
        executor = JsonTemporalExecutor(descriptor())
    elif provider == "sqlite":
        path = tmp_path / "ticks.db"
        create_ticks(path)
        target = sqlite_uri(path)
        executor = SQLiteTemporalExecutor(descriptor(), "ticks")
    elif provider == "postgres":
        target = TableURI("postgres://localhost/conformance")
        executor = PostgresTemporalExecutor(
            descriptor(),
            "ticks",
            connection_factory=_PostgresFactory(ticks_table()),
        )
    elif provider == "excel":
        path = value_workbook(tmp_path / "ticks.xlsx")
        target = TableURI(f"excel://{path.as_posix()}#sheet=Ticks")
        executor = ExcelTemporalExecutor(descriptor(), worksheet="Ticks")
    else:
        target = TableURI("maybe://document/ticks")
        executor = MaybeSheetTemporalExecutor(RecordingTemporalProcess(), descriptor())
    execution = TemporalExecutionRequest(
        target,
        plan,
        None,
        operation_id,
        snapshot_reference,
    )
    return provider, executor, TemporalSemanticCase(
        semantic_case.case_id,
        execution,
        semantic_case.expected,
    )


class _PostgresCursor:
    description = ()

    def __init__(self, table: pa.Table) -> None:
        self.table = table
        self.statement = ""

    def execute(self, statement, parameters=()):
        del parameters
        self.statement = statement

    def fetchmany(self, size):
        fields = re.findall(r'"([A-Za-z_][A-Za-z0-9_]*)"', self.statement.split(" FROM ", 1)[0])
        columns = []
        for name in fields:
            column = self.table[name]
            if pa.types.is_timestamp(column.type):
                column = column.cast(pa.int64())
            columns.append(column.to_pylist())
        return [tuple(column[index] for column in columns) for index in range(min(size, self.table.num_rows))]

    def close(self):
        return None


class _PostgresConnection:
    def __init__(self, table: pa.Table) -> None:
        self.table = table

    def cursor(self):
        return _PostgresCursor(self.table)

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


class _PostgresFactory:
    def __init__(self, table: pa.Table) -> None:
        self.table = table

    def __call__(self, **kwargs):
        del kwargs
        return _PostgresConnection(self.table)
