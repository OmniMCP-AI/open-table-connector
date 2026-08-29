"""Reusable assertions for the portable temporal and managed-storage surfaces."""

from __future__ import annotations

from dataclasses import dataclass

import pyarrow as pa

from open_table_connector.timeseries import (
    AbortDisposition,
    ManagedAbortRequest,
    ManagedCommitRequest,
    ManagedReadbackRequest,
    ManagedReadbackResult,
    ManagedStageRequest,
    ManagedTemporalStore,
    PortableTemporalExecutor,
    ResourceBounds,
    TemporalExecutionRequest,
    TemporalExecutionResult,
    VisibilityGuarantee,
)


@dataclass(frozen=True, slots=True)
class TemporalSemanticCase:
    request: TemporalExecutionRequest
    expected: pa.Table

    def __post_init__(self) -> None:
        if not isinstance(self.request, TemporalExecutionRequest):
            raise TypeError("request must be a TemporalExecutionRequest")
        if not isinstance(self.expected, pa.Table):
            raise TypeError("expected must be a pyarrow.Table")


@dataclass(frozen=True, slots=True)
class ManagedLifecycleCase:
    stage_request: ManagedStageRequest
    commit_operation_id: str
    readback_operation_id: str
    abort_operation_id: str
    resource_bounds: ResourceBounds


@dataclass(frozen=True, slots=True)
class ManagedLifecycleResult:
    stage: object
    commit: object
    readback: ManagedReadbackResult
    abort: object


def assert_temporal_semantics(
    executor: PortableTemporalExecutor,
    case: TemporalSemanticCase,
) -> TemporalExecutionResult:
    """Execute one case and compare normalized Arrow schema, rows, nulls, and order."""

    if not isinstance(executor, PortableTemporalExecutor):
        raise TypeError("executor must implement PortableTemporalExecutor")
    if not isinstance(case, TemporalSemanticCase):
        raise TypeError("case must be a TemporalSemanticCase")
    result = executor.execute(case.request)
    if result.table is None:
        raise AssertionError("semantic conformance requires an in-process Arrow result")
    _assert_normalized_arrow_equal(result.table, case.expected)
    receipt = result.receipt
    assert receipt is not None
    assert receipt.plan_schema_version == case.request.plan.schema_version
    assert receipt.resource_bounds == case.request.plan.resource_bounds
    assert receipt.returned_rows == result.table.num_rows
    assert receipt.returned_rows <= receipt.examined_rows <= receipt.resource_bounds.max_rows
    assert receipt.returned_bytes <= receipt.examined_bytes <= receipt.resource_bounds.max_bytes
    return result


def assert_managed_lifecycle(
    store: ManagedTemporalStore,
    case: ManagedLifecycleCase,
) -> ManagedLifecycleResult:
    """Certify idempotent stage/commit, independent readback, and safe abort."""

    if not isinstance(store, ManagedTemporalStore):
        raise TypeError("store must implement ManagedTemporalStore")
    if not isinstance(case, ManagedLifecycleCase):
        raise TypeError("case must be a ManagedLifecycleCase")
    stage = store.stage(case.stage_request)
    assert stage.visible is False
    assert store.stage(case.stage_request) == stage
    commit_request = ManagedCommitRequest(
        case.commit_operation_id,
        case.stage_request.logical_target,
        stage.stage_id,
        stage.idempotency_key,
        case.resource_bounds,
    )
    commit = store.commit(commit_request)
    assert commit.visibility is VisibilityGuarantee.ATOMIC
    assert store.commit(commit_request) == commit
    readback = store.readback(
        ManagedReadbackRequest(
            case.readback_operation_id,
            case.stage_request.logical_target,
            commit.snapshot_id,
            commit.snapshot_reference,
            case.resource_bounds,
        )
    )
    assert readback.receipt.snapshot_id == commit.snapshot_id
    assert readback.receipt.observed_rows <= case.resource_bounds.max_rows
    assert readback.receipt.observed_bytes <= case.resource_bounds.max_bytes
    abort = store.abort(
        ManagedAbortRequest(
            case.abort_operation_id,
            case.stage_request.logical_target,
            stage.stage_id,
        )
    )
    assert abort.disposition is AbortDisposition.ALREADY_COMMITTED
    return ManagedLifecycleResult(stage, commit, readback, abort)


def _assert_normalized_arrow_equal(actual: pa.Table, expected: pa.Table) -> None:
    assert _schema_signature(actual.schema) == _schema_signature(expected.schema), (
        f"temporal schema mismatch: {_schema_signature(actual.schema)!r} != "
        f"{_schema_signature(expected.schema)!r}"
    )
    assert _logical_columns(actual) == _logical_columns(expected), (
        "temporal ordered values, nulls, or timestamp precision differ"
    )


def _logical_columns(table: pa.Table) -> tuple[tuple[object, ...], ...]:
    result: list[tuple[object, ...]] = []
    for field, column in zip(table.schema, table.columns, strict=True):
        values = column.combine_chunks()
        if pa.types.is_timestamp(field.type):
            values = values.cast(pa.int64())
        result.append(tuple(values.to_pylist()))
    return tuple(result)


def _schema_signature(schema: pa.Schema) -> tuple[tuple[str, str, bool], ...]:
    def logical_type(value: pa.DataType) -> str:
        if pa.types.is_string(value) or pa.types.is_large_string(value):
            return "utf8"
        return str(value)

    return tuple((field.name, logical_type(field.type), field.nullable) for field in schema)


__all__ = [
    "ManagedLifecycleCase",
    "ManagedLifecycleResult",
    "TemporalSemanticCase",
    "assert_managed_lifecycle",
    "assert_temporal_semantics",
]
