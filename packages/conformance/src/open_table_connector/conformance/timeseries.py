"""Reusable assertions for the portable temporal and managed-storage surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path

import pyarrow as pa

from open_table_connector.contract import TableURI

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
    TemporalExecutionRequest,
    VisibilityGuarantee,
)


@dataclass(frozen=True, slots=True)
class TemporalSemanticCase:
    case_id: str
    request: TemporalExecutionRequest
    expected: pa.Table

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or not self.case_id:
            raise TypeError("case_id must be a non-empty string")
        if not isinstance(self.request, TemporalExecutionRequest):
            raise TypeError("request must be a TemporalExecutionRequest")
        if not isinstance(self.expected, pa.Table):
            raise TypeError("expected must be a pyarrow.Table")


_EXPECTED_TYPES = {
    "string": pa.string,
    "double": pa.float64,
    "int64": pa.int64,
    "bool": pa.bool_,
}


def _expected_table(document: dict[str, object]) -> pa.Table:
    schema_entries = document.get("schema")
    rows = document.get("rows")
    if not isinstance(schema_entries, list) or not isinstance(rows, list):
        raise ValueError("expected fixture requires schema and rows arrays")
    fields: list[pa.Field] = []
    for entry in schema_entries:
        if not isinstance(entry, dict) or set(entry) != {"name", "type", "nullable"}:
            raise ValueError("expected schema entries must contain name, type, nullable")
        name = entry["name"]
        type_name = entry["type"]
        nullable = entry["nullable"]
        if not isinstance(name, str) or not name or not isinstance(type_name, str):
            raise ValueError("expected schema names and types must be strings")
        if not isinstance(nullable, bool):
            raise ValueError("expected schema nullable must be boolean")
        if type_name.startswith("timestamp[") and type_name.endswith("]"):
            inner = type_name[10:-1]
            unit, _, timezone = inner.partition(", tz=")
            arrow_type = pa.timestamp(unit, tz=timezone or None)
        else:
            try:
                arrow_type = _EXPECTED_TYPES[type_name]()
            except KeyError as exc:
                raise ValueError(f"unsupported expected Arrow type: {type_name}") from exc
        fields.append(pa.field(name, arrow_type, nullable=nullable))
    names = [field.name for field in fields]
    if len(names) != len(set(names)):
        raise ValueError("expected schema contains duplicate fields")
    if any(not isinstance(row, dict) or set(row) != set(names) for row in rows):
        raise ValueError("expected rows must match the declared schema exactly")
    columns: list[pa.Array] = []
    for field in fields:
        values = [row[field.name] for row in rows]
        if pa.types.is_timestamp(field.type):
            scale = {"s": 0, "ms": 3, "us": 6, "ns": 9}[field.type.unit]
            converted: list[int | None] = []
            for value in values:
                if value is None:
                    converted.append(None)
                    continue
                text = str(value).replace("Z", "+00:00")
                whole_text, _, fraction_text = text.partition(".")
                fraction_text = fraction_text.split("+", 1)[0].ljust(9, "0")
                whole = datetime.fromisoformat(whole_text + "+00:00").astimezone(UTC)
                converted.append(
                    int(whole.timestamp()) * (10**scale)
                    + int(fraction_text[:9]) // (10 ** (9 - scale))
                )
            values = converted
        columns.append(pa.array(values, type=field.type))
    return pa.Table.from_arrays(columns, schema=pa.schema(fields))


def load_temporal_cases(root: Path) -> tuple[TemporalSemanticCase, ...]:
    """Load vendored temporal cases without executing an implementation oracle."""

    root = root.resolve()
    manifest = json.loads((root / "cases.json").read_text(encoding="utf-8"))
    if set(manifest) != {"schema_version", "source", "cases"}:
        raise ValueError("temporal case manifest has unknown or missing fields")
    if manifest["schema_version"] != "otc.temporal-conformance-cases/v1":
        raise ValueError("unsupported temporal case manifest schema_version")
    source = manifest["source"]
    if not isinstance(source, str) or not (root / source).is_file():
        raise ValueError("temporal case source is missing")
    raw_cases = manifest["cases"]
    if not isinstance(raw_cases, list):
        raise ValueError("temporal case manifest cases must be an array")
    cases: list[TemporalSemanticCase] = []
    seen: set[str] = set()
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict) or set(raw_case) != {"id", "plan", "expected"}:
            raise ValueError("temporal case entries must contain id, plan, expected")
        case_id, plan_name, expected_name = (
            raw_case["id"],
            raw_case["plan"],
            raw_case["expected"],
        )
        if not all(isinstance(value, str) and value for value in (case_id, plan_name, expected_name)):
            raise ValueError("temporal case identifiers and paths must be non-empty strings")
        if case_id in seen:
            raise ValueError(f"duplicate temporal case id: {case_id}")
        seen.add(case_id)
        plan_document = json.loads((root / plan_name).read_text(encoding="utf-8"))
        plan_wire = plan_document.get("plan", plan_document)
        expected_document = json.loads((root / expected_name).read_text(encoding="utf-8"))
        from open_table_connector.timeseries import plan_from_wire

        plan = plan_from_wire(plan_wire)
        request = TemporalExecutionRequest(
            TableURI("json:///conformance/ticks.json"),
            plan,
            None,
            f"semantic-{case_id}",
            None,
        )
        cases.append(TemporalSemanticCase(case_id, request, _expected_table(expected_document)))
    return tuple(cases)


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
    "load_temporal_cases",
    "assert_managed_lifecycle",
    "assert_temporal_semantics",
]
