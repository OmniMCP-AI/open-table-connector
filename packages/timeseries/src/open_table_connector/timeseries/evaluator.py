"""Bounded portable scan, latest, and as-of evaluation."""

from __future__ import annotations

import hashlib
import time
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

import polars as pl
import pyarrow as pa

from open_table_connector.contract import (
    BaseConvention,
    CapabilityIdentity,
    ConnectorIdentity,
    NeutralReceipt,
    TableMode,
    TableURI,
)

from .descriptor import DuplicatePolicy, TemporalTableDescriptor, TimestampPrecision
from .plan import (
    AsOf,
    Latest,
    PortableTemporalPlan,
    ResourceBounds,
    ScanRange,
    TagOperator,
    TagPredicate,
    _utc_parts,
    portable_plan_hash,
    validate_plan_for_descriptor,
)
from .receipts import ExecutionLocation, TemporalReceipt, TimeRange
from .storage import (
    TemporalErrorCode,
    TemporalExecutionRequest,
    TemporalExecutionResult,
    TemporalExtensionError,
)


@runtime_checkable
class TemporalSource(Protocol):
    """A source that accepts a bounded, projection-aware physical read."""

    descriptor: TemporalTableDescriptor

    def read_bounded(
        self,
        target: TableURI,
        projection: tuple[str, ...],
        predicates: tuple[TagPredicate, ...],
        bounds: ResourceBounds,
    ) -> pa.Table: ...


class PolarsTemporalExecutor:
    """Evaluate the portable lookup subset through one bounded Polars pipeline."""

    def __init__(self, source: TemporalSource) -> None:
        if not isinstance(source, TemporalSource):
            raise TypeError("source must implement TemporalSource")
        self._source = source

    def execute(self, request: TemporalExecutionRequest) -> TemporalExecutionResult:
        if not isinstance(request, TemporalExecutionRequest):
            raise TypeError("request must be a TemporalExecutionRequest")
        operation = request.plan.operation
        if not isinstance(operation, (ScanRange, Latest, AsOf)):
            raise TemporalExtensionError(
                TemporalErrorCode.PROTOCOL_INVALID,
                "portable operation is not implemented by the lookup evaluator",
                {"operation": type(operation).__name__},
            )
        descriptor = self._source.descriptor
        if not isinstance(descriptor, TemporalTableDescriptor):
            raise TypeError("source descriptor must be a TemporalTableDescriptor")
        validate_plan_for_descriptor(request.plan, descriptor)

        started = time.monotonic_ns()
        required = _required_fields(request.plan, descriptor)
        table = self._source.read_bounded(
            request.target,
            required,
            operation.tag_predicates,
            request.plan.resource_bounds,
        )
        _check_deadline(started, request.plan.resource_bounds)
        if not isinstance(table, pa.Table):
            raise TypeError("temporal source must return a pyarrow.Table")
        _validate_arrow_schema(table.schema, descriptor, required)
        table = table.select(required)
        if table[descriptor.time_field].null_count:
            raise ValueError("event-time field cannot contain null values")
        if (
            descriptor.duplicate_policy is DuplicatePolicy.REPLACE_LATEST
            and descriptor.ingestion_time_field is not None
            and table[descriptor.ingestion_time_field].null_count
        ):
            raise ValueError("replace-latest ingestion-time field cannot contain null values")
        examined_rows = table.num_rows
        examined_bytes = len(_arrow_ipc_bytes(table))
        _check_size_bounds(
            examined_rows,
            examined_bytes,
            request.plan.resource_bounds,
            "source read",
        )

        frame = pl.from_arrow(table)
        if not isinstance(frame, pl.DataFrame):
            frame = pl.DataFrame(frame)
        lazy = frame.lazy()
        lazy = _apply_predicates(lazy, operation.tag_predicates)
        time_field = descriptor.time_field
        time_ns = pl.col(time_field).dt.timestamp("ns")
        if isinstance(operation, ScanRange):
            start = _timestamp_ns(operation.start)
            end = _timestamp_ns(operation.end)
            lazy = lazy.filter((time_ns >= start) & (time_ns < end))
        elif isinstance(operation, Latest) and operation.at_or_before is not None:
            lazy = lazy.filter(time_ns <= _timestamp_ns(operation.at_or_before))
        elif isinstance(operation, AsOf):
            lazy = lazy.filter(time_ns <= _timestamp_ns(operation.at))

        filtered = lazy.collect()
        _check_deadline(started, request.plan.resource_bounds)
        if isinstance(operation, (Latest, AsOf)):
            filtered = _latest_rows(filtered, descriptor)
        filtered = _resolve_duplicates(filtered, descriptor)
        filtered = _sort_result(filtered, request.plan, descriptor)
        if request.plan.result_row_limit is not None:
            filtered = filtered.head(request.plan.result_row_limit)
        observed_range = _observed_range(filtered, descriptor.time_field)
        result = filtered.select(operation.projection).to_arrow()
        if not isinstance(result, pa.Table):
            result = pa.Table.from_batches(result)
        returned_rows = result.num_rows
        returned_bytes = len(_arrow_ipc_bytes(result))
        _check_size_bounds(
            returned_rows,
            returned_bytes,
            request.plan.resource_bounds,
            "temporal result",
        )
        _check_deadline(started, request.plan.resource_bounds)
        elapsed_ms = (time.monotonic_ns() - started) // 1_000_000
        examined_bytes = max(examined_bytes, returned_bytes)
        receipt = _receipt(
            request,
            descriptor,
            table,
            result,
            examined_rows,
            examined_bytes,
            returned_rows,
            returned_bytes,
            elapsed_ms,
            observed_range,
        )
        return TemporalExecutionResult(table=result, artifact=None, receipt=receipt)


def _required_fields(
    plan: PortableTemporalPlan,
    descriptor: TemporalTableDescriptor,
) -> tuple[str, ...]:
    operation = plan.operation
    fields = list(operation.projection)
    fields.extend(predicate.field for predicate in operation.tag_predicates)
    fields.extend(key.field for key in plan.output_order)
    fields.extend(descriptor.series_key_fields)
    fields.append(descriptor.time_field)
    if descriptor.ingestion_time_field is not None:
        fields.append(descriptor.ingestion_time_field)
    return tuple(dict.fromkeys(fields))


def _validate_arrow_schema(
    schema: pa.Schema,
    descriptor: TemporalTableDescriptor,
    required: tuple[str, ...],
) -> None:
    missing = sorted(set(required).difference(schema.names))
    if missing:
        raise ValueError(f"temporal source schema is missing fields: {', '.join(missing)}")
    expected_unit = {
        TimestampPrecision.SECOND: "s",
        TimestampPrecision.MILLISECOND: "ms",
        TimestampPrecision.MICROSECOND: "us",
        TimestampPrecision.NANOSECOND: "ns",
    }[descriptor.precision]
    for field_name in (
        descriptor.time_field,
        *(() if descriptor.ingestion_time_field is None else (descriptor.ingestion_time_field,)),
    ):
        field = schema.field(field_name)
        if not pa.types.is_timestamp(field.type):
            raise ValueError(f"{field_name} must be an Arrow timestamp")
        if field.type.unit != expected_unit or field.type.tz != descriptor.timezone:
            raise ValueError(f"{field_name} timestamp type disagrees with the descriptor")


def _apply_predicates(
    lazy: pl.LazyFrame,
    predicates: tuple[TagPredicate, ...],
) -> pl.LazyFrame:
    for predicate in predicates:
        if predicate.operator is TagOperator.EQ:
            lazy = lazy.filter(pl.col(predicate.field) == predicate.values[0])
        else:
            lazy = lazy.filter(pl.col(predicate.field).is_in(list(predicate.values)))
    return lazy


def _latest_rows(frame: pl.DataFrame, descriptor: TemporalTableDescriptor) -> pl.DataFrame:
    if frame.is_empty():
        return frame
    time_field = descriptor.time_field
    if descriptor.series_key_fields:
        maximum = pl.col(time_field).max().over(list(descriptor.series_key_fields))
    else:
        maximum = pl.col(time_field).max()
    return frame.filter(pl.col(time_field) == maximum)


def _resolve_duplicates(
    frame: pl.DataFrame,
    descriptor: TemporalTableDescriptor,
) -> pl.DataFrame:
    if frame.is_empty() or descriptor.duplicate_policy is DuplicatePolicy.PRESERVE:
        return frame
    keys = [*descriptor.series_key_fields, descriptor.time_field]
    duplicate = frame.select(pl.struct(keys).is_duplicated().alias("duplicate"))["duplicate"].any()
    if duplicate and descriptor.duplicate_policy is DuplicatePolicy.REJECT:
        raise ValueError("duplicate event timestamp violates reject policy")
    if descriptor.duplicate_policy is DuplicatePolicy.REPLACE_LATEST:
        ingestion = descriptor.ingestion_time_field
        if ingestion is None:
            raise ValueError("replace-latest requires an ingestion timestamp")
        return (
            frame.sort([*keys, ingestion])
            .unique(subset=keys, keep="last", maintain_order=True)
        )
    return frame


def _sort_result(
    frame: pl.DataFrame,
    plan: PortableTemporalPlan,
    descriptor: TemporalTableDescriptor,
) -> pl.DataFrame:
    fields = [key.field for key in plan.output_order]
    descending = [key.direction.value == "desc" for key in plan.output_order]
    if (
        descriptor.duplicate_policy is DuplicatePolicy.PRESERVE
        and descriptor.ingestion_time_field is not None
        and descriptor.ingestion_time_field not in fields
    ):
        fields.append(descriptor.ingestion_time_field)
        descending.append(False)
    return frame.sort(fields, descending=descending, maintain_order=True)


def _timestamp_ns(value: str) -> int:
    seconds, fraction = _utc_parts(value, "timestamp")
    return seconds * 1_000_000_000 + fraction


def _observed_range(frame: pl.DataFrame, time_field: str) -> TimeRange | None:
    if frame.is_empty():
        return None
    values = frame.select(pl.col(time_field).dt.timestamp("ns"))[time_field]
    return TimeRange(_format_ns(values.min()), _format_ns(values.max()))


def _format_ns(value: int) -> str:
    seconds, nanos = divmod(value, 1_000_000_000)
    whole = datetime.fromtimestamp(seconds, tz=UTC).strftime("%Y-%m-%dT%H:%M:%S")
    return f"{whole}.{nanos:09d}Z"


def _arrow_ipc_bytes(table: pa.Table) -> bytes:
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return sink.getvalue().to_pybytes()


def _identity(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _check_size_bounds(
    rows: int,
    size_bytes: int,
    bounds: ResourceBounds,
    phase: str,
) -> None:
    if rows > bounds.max_rows or size_bytes > bounds.max_bytes:
        raise TemporalExtensionError(
            TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
            f"{phase} exceeded temporal resource bounds",
            {"rows": rows, "bytes": size_bytes},
        )


def _check_deadline(started: int, bounds: ResourceBounds) -> None:
    elapsed_ns = time.monotonic_ns() - started
    if elapsed_ns > bounds.max_duration_ms * 1_000_000:
        raise TemporalExtensionError(
            TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
            "temporal execution exceeded max_duration_ms",
            {"elapsed_ms": elapsed_ns // 1_000_000},
        )


def _receipt(
    request: TemporalExecutionRequest,
    descriptor: TemporalTableDescriptor,
    examined: pa.Table,
    result: pa.Table,
    examined_rows: int,
    examined_bytes: int,
    returned_rows: int,
    returned_bytes: int,
    elapsed_ms: int,
    observed_range: TimeRange | None,
) -> TemporalReceipt:
    operation = request.plan.operation
    capability = {
        ScanRange: "timeseries.scan.range",
        Latest: "timeseries.lookup.latest",
        AsOf: "timeseries.lookup.asof",
    }[type(operation)]
    examined_ipc = _arrow_ipc_bytes(examined)
    result_ipc = _arrow_ipc_bytes(result)
    source_revision = _identity(examined_ipc)
    convention = (
        BaseConvention(key_fields=descriptor.series_key_fields)
        if descriptor.series_key_fields
        else BaseConvention(ordinal_snapshot_id=source_revision)
    )
    neutral = NeutralReceipt(
        connector=ConnectorIdentity("portable_temporal", "0.1.0", "1.0"),
        capability=CapabilityIdentity(capability, "1.0"),
        operation_id=request.operation_id,
        safe_uri=request.target,
        mode=TableMode.BASE,
        source_revision=source_revision,
        schema_fingerprint=_identity(result.schema.serialize().to_pybytes()),
        content_fingerprint=_identity(result_ipc),
        coordinate_convention=convention,
        row_count=returned_rows,
        batch_count=len(result.to_batches()),
    )
    requested_range = None
    if isinstance(operation, ScanRange):
        requested_range = TimeRange(operation.start, operation.end)
    return TemporalReceipt(
        schema_version="otc.temporal-receipt/v1",
        neutral_receipt=neutral,
        descriptor_hash=request.plan.descriptor_hash,
        requested_range=requested_range,
        observed_range=observed_range,
        output_order=request.plan.output_order,
        execution_location=ExecutionLocation.CONNECTOR,
        resource_bounds=request.plan.resource_bounds,
        examined_rows=examined_rows,
        examined_bytes=examined_bytes,
        returned_rows=returned_rows,
        returned_bytes=returned_bytes,
        elapsed_ms=elapsed_ms,
        snapshot_reference=request.snapshot_reference,
        plan_schema_version=request.plan.schema_version,
        portable_plan_hash=portable_plan_hash(request.plan),
    )


__all__ = ["PolarsTemporalExecutor", "TemporalSource"]
