"""Time-series facade over the existing temporal contracts."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import polars as pl
import pyarrow as pa
import sqlglot
from open_table_connector.contract import PROVIDER_POSTGRES, ConnectorErrorCode, TableURI
from open_table_connector.contract import TableMode as LegacyTableMode
from open_table_connector.timeseries import (
    AggregateFunction,
    AggregateMeasure,
    AsOf,
    BucketAggregate,
    CalendarBucket,
    FillMode,
    FillRule,
    FixedBucket,
    GapFill,
    Latest,
    ManagedAbortReceipt,
    ManagedCommitReceipt,
    ManagedCurrentResult,
    ManagedReadbackResult,
    ManagedStageReceipt,
    OrderDirection,
    OrderKey,
    PortableTemporalPlan,
    ResourceBounds,
    ScanRange,
    TagOperator,
    TagPredicate,
    TemporalExecutionRequest,
    TemporalExecutionResult,
    TemporalExtensionError,
    TemporalReceipt,
    TemporalTableDescriptor,
    TimestampPrecision,
    portable_plan_hash,
    temporal_descriptor_hash,
)
from sqlglot import exp

from .query import Query, QueryLane
from .result import (
    CommitState,
    ErrorCode,
    ErrorInfo,
    OperationResult,
    OTCError,
    Outcome,
    Receipt,
    ReconciliationReference,
    VerificationState,
)

if TYPE_CHECKING:
    from .client import Client
    from .table import Table, TableBinding


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _utc_text_now() -> str:
    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond:06d}" + "000Z"


def _is_expired(deadline: str | None, now_text: str) -> bool:
    return deadline is not None and deadline < now_text


_FIXED_INTERVAL_NS = {
    "nanosecond": 1,
    "nanoseconds": 1,
    "microsecond": 1_000,
    "microseconds": 1_000,
    "millisecond": 1_000_000,
    "milliseconds": 1_000_000,
    "second": 1_000_000_000,
    "seconds": 1_000_000_000,
    "minute": 60_000_000_000,
    "minutes": 60_000_000_000,
    "hour": 3_600_000_000_000,
    "hours": 3_600_000_000_000,
}

_PRECISION_DIGITS = {
    TimestampPrecision.SECOND: 0,
    TimestampPrecision.MILLISECOND: 3,
    TimestampPrecision.MICROSECOND: 6,
    TimestampPrecision.NANOSECOND: 9,
}
_INTERVAL = re.compile(r"^([1-9][0-9]*)\s+([A-Za-z]+)$")


class AbortDisposition(StrEnum):
    ABORTED = "aborted"
    ALREADY_ABORTED = "already_aborted"
    ALREADY_COMMITTED = "already_committed"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class TemporalResourceLimits:
    max_rows: int = 100_000
    max_bytes: int = 128 * 1024 * 1024
    max_duration_ms: int = 30_000

    def __post_init__(self) -> None:
        if self.max_rows <= 0:
            raise ValueError("max_rows must be positive")
        if self.max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        if self.max_duration_ms <= 0:
            raise ValueError("max_duration_ms must be positive")

    def to_bounds(self) -> ResourceBounds:
        return ResourceBounds(
            max_rows=self.max_rows,
            max_bytes=self.max_bytes,
            max_duration_ms=self.max_duration_ms,
        )


@dataclass(frozen=True, slots=True)
class ManagedStage:
    logical_target: TableURI
    physical_target: TableURI
    stage_id: str
    idempotency_key: str
    descriptor_hash: str
    artifact_hash: str
    staged_at: str
    _binding: TableBinding = field(repr=False, compare=False, hash=False)
    _owner_client_id: str = field(repr=False, compare=False, hash=False)
    lease_expires_at: str | None = None


@dataclass(frozen=True, slots=True)
class ManagedSnapshot:
    logical_target: TableURI
    stage_id: str
    snapshot_id: str
    snapshot_reference: str
    descriptor_hash: str
    committed_at: str
    _binding: TableBinding = field(repr=False, compare=False, hash=False)
    _owner_client_id: str = field(repr=False, compare=False, hash=False)
    retention_expires_at: str | None = None


@dataclass(frozen=True, slots=True)
class ManagedSnapshotState:
    snapshot: ManagedSnapshot
    schema: pa.Schema

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, ManagedSnapshot):
            raise TypeError("snapshot must be a ManagedSnapshot")
        if not isinstance(self.schema, pa.Schema):
            raise TypeError("schema must be a pyarrow.Schema")


@dataclass(frozen=True, slots=True)
class _TemporalQueryDefinition:
    binding: TableBinding
    descriptor: TemporalTableDescriptor
    plan: PortableTemporalPlan
    snapshot_reference: str | None = None

    def canonical_plan(self) -> dict[str, object]:
        return self.plan.to_wire()

    def canonical_plan_hash(self) -> str:
        return portable_plan_hash(self.plan)


@runtime_checkable
class TemporalConnectorExtension(Protocol):
    def descriptor_hash_for(
        self,
        binding: TableBinding,
        descriptor: TemporalTableDescriptor,
    ) -> str: ...

    def executor_for(
        self,
        binding: TableBinding,
        descriptor: TemporalTableDescriptor,
    ) -> object: ...

    def append_rows(
        self,
        binding: TableBinding,
        descriptor: TemporalTableDescriptor,
        frame: pl.DataFrame,
        *,
        idempotency_key: str,
    ) -> OperationResult[int]: ...

    def upsert_rows(
        self,
        binding: TableBinding,
        descriptor: TemporalTableDescriptor,
        frame: pl.DataFrame,
        *,
        idempotency_key: str,
    ) -> OperationResult[int]: ...

    def stage_rows(
        self,
        binding: TableBinding,
        descriptor: TemporalTableDescriptor,
        frame: pl.DataFrame,
        *,
        idempotency_key: str,
    ) -> ManagedStageReceipt: ...

    def commit_stage(
        self,
        binding: TableBinding,
        descriptor: TemporalTableDescriptor,
        stage: ManagedStage,
    ) -> ManagedCommitReceipt: ...

    def readback_snapshot(
        self,
        binding: TableBinding,
        descriptor: TemporalTableDescriptor,
        snapshot: ManagedSnapshot,
    ) -> ManagedReadbackResult: ...

    def current_snapshot(
        self,
        binding: TableBinding,
        descriptor: TemporalTableDescriptor,
    ) -> ManagedCurrentResult | None: ...

    def abort_stage(
        self,
        binding: TableBinding,
        descriptor: TemporalTableDescriptor,
        stage: ManagedStage,
    ) -> ManagedAbortReceipt: ...


def _error(
    message: str,
    code: ErrorCode,
    *,
    reconciliation: ReconciliationReference | None = None,
    **details: object,
) -> OTCError:
    return OTCError(
        message,
        OperationResult[None](
            value=None,
            outcome=Outcome.REJECTED,
            commit=CommitState.NOT_STARTED,
            verification=VerificationState.SKIPPED,
            receipts=(),
            error=ErrorInfo(
                code=code,
                message=message,
                safe_details=details,
                reconciliation=reconciliation,
            ),
        ),
    )


def _map_temporal_error(code: ConnectorErrorCode) -> ErrorCode:
    mapping = {
        ConnectorErrorCode.UNSUPPORTED_CAPABILITY: ErrorCode.UNSUPPORTED_CAPABILITY,
        ConnectorErrorCode.TIMEOUT: ErrorCode.TIMEOUT,
        ConnectorErrorCode.CANCELLED: ErrorCode.CANCELLED,
        ConnectorErrorCode.EXECUTION_FAILED: ErrorCode.EXECUTION_FAILED,
        ConnectorErrorCode.READBACK_MISMATCH: ErrorCode.READBACK_MISMATCH,
        ConnectorErrorCode.PROTOCOL_INVALID: ErrorCode.PROTOCOL_FAILURE,
        ConnectorErrorCode.PROTOCOL_VERSION_UNSUPPORTED: ErrorCode.PROTOCOL_FAILURE,
        ConnectorErrorCode.RESOURCE_LIMIT_EXCEEDED: ErrorCode.RESOURCE_LIMIT,
        ConnectorErrorCode.SNAPSHOT_UNAVAILABLE: ErrorCode.SNAPSHOT_UNAVAILABLE,
        ConnectorErrorCode.IDEMPOTENCY_CONFLICT: ErrorCode.IDEMPOTENCY_CONFLICT,
        ConnectorErrorCode.VISIBILITY_INCOMPLETE: ErrorCode.UNCERTAIN_MUTATION,
        ConnectorErrorCode.AUTHENTICATION: ErrorCode.AUTHENTICATION,
        ConnectorErrorCode.CONFIGURATION: ErrorCode.INVALID_CONFIGURATION,
        ConnectorErrorCode.CONFLICT: ErrorCode.KEY_CONFLICT,
    }
    return mapping.get(code, ErrorCode.EXECUTION_FAILED)


def _receipt_from_temporal(receipt: TemporalReceipt, query: Query) -> Receipt:
    return Receipt(
        kind="temporal-execution",
        operation=receipt.neutral_receipt.capability.capability_id,
        connector_id=receipt.neutral_receipt.connector.connector_id,
        capability=receipt.neutral_receipt.capability.to_reference(),
        safe_target=receipt.neutral_receipt.safe_uri,
        mode=LegacyTableMode.BASE.value,
        details={
            "descriptor_hash": receipt.descriptor_hash,
            "execution_location": receipt.execution_location.value,
            "plan_hash": receipt.portable_plan_hash,
            "definition_hash": query.definition_hash,
            "plan_schema_version": receipt.plan_schema_version,
            "resource_bounds": receipt.resource_bounds.to_wire(),
            "examined_rows": receipt.examined_rows,
            "examined_bytes": receipt.examined_bytes,
            "returned_rows": receipt.returned_rows,
            "returned_bytes": receipt.returned_bytes,
            "elapsed_ms": receipt.elapsed_ms,
            "requested_range": None
            if receipt.requested_range is None
            else receipt.requested_range.to_wire(),
            "observed_range": None
            if receipt.observed_range is None
            else receipt.observed_range.to_wire(),
            "output_order": [item.to_wire() for item in receipt.output_order],
            "snapshot_reference": receipt.snapshot_reference,
            "source_operation_id": receipt.neutral_receipt.operation_id,
            "source_revision": receipt.neutral_receipt.source_revision,
            "schema_fingerprint": receipt.neutral_receipt.schema_fingerprint,
            "content_fingerprint": receipt.neutral_receipt.content_fingerprint,
        },
    )


def _receipt_from_stage(receipt: ManagedStageReceipt) -> Receipt:
    return Receipt(
        kind="managed-stage",
        operation="timeseries.stage",
        safe_target=receipt.logical_target,
        mode=LegacyTableMode.BASE.value,
        details={
            "operation_id": receipt.operation_id,
            "stage_id": receipt.stage_id,
            "idempotency_key": receipt.idempotency_key,
            "descriptor_hash": receipt.descriptor_hash,
            "artifact_hash": receipt.artifact_hash,
            "staged_at": receipt.staged_at,
        },
    )


def _receipt_from_commit(receipt: ManagedCommitReceipt) -> Receipt:
    return Receipt(
        kind="managed-commit",
        operation="timeseries.commit",
        safe_target=receipt.logical_target,
        mode=LegacyTableMode.BASE.value,
        details={
            "operation_id": receipt.operation_id,
            "stage_id": receipt.stage_id,
            "idempotency_key": receipt.idempotency_key,
            "snapshot_id": receipt.snapshot_id,
            "snapshot_reference": receipt.snapshot_reference,
            "committed_at": receipt.committed_at,
            "visibility": receipt.visibility.value,
        },
    )


def _receipt_from_readback(result: ManagedReadbackResult) -> Receipt:
    receipt = result.receipt
    return Receipt(
        kind="managed-readback",
        operation="timeseries.readback",
        details={
            "operation_id": receipt.operation_id,
            "snapshot_id": receipt.snapshot_id,
            "observed_at": receipt.observed_at,
            "observed_schema_hash": receipt.observed_schema_hash,
            "observed_content_hash": receipt.observed_content_hash,
            "observed_rows": receipt.observed_rows,
            "observed_bytes": receipt.observed_bytes,
        },
    )


def _receipt_from_abort(receipt: ManagedAbortReceipt) -> Receipt:
    return Receipt(
        kind="managed-abort",
        operation="timeseries.abort",
        safe_target=receipt.logical_target,
        mode=LegacyTableMode.BASE.value,
        details={
            "operation_id": receipt.operation_id,
            "stage_id": receipt.stage_id,
            "disposition": receipt.disposition.value,
            "aborted_at": receipt.aborted_at,
        },
    )


def _abort_disposition(receipt: ManagedAbortReceipt) -> AbortDisposition:
    if receipt.disposition.value == "removed":
        return AbortDisposition.ABORTED
    if receipt.disposition.value == "already_absent":
        return AbortDisposition.ALREADY_ABORTED
    return AbortDisposition.ALREADY_COMMITTED


def _expired_abort_receipt(stage: ManagedStage, observed_at: str) -> Receipt:
    return Receipt(
        kind="managed-abort",
        operation="timeseries.abort",
        safe_target=stage.logical_target,
        mode=LegacyTableMode.BASE.value,
        details={
            "stage_id": stage.stage_id,
            "idempotency_key": stage.idempotency_key,
            "disposition": AbortDisposition.EXPIRED.value,
            "lease_expires_at": stage.lease_expires_at,
            "observed_at": observed_at,
            "provider_mutation": False,
            "evidence_source": "authenticated-stage-lease",
        },
    )


def _extension_for(table: Table, descriptor: TemporalTableDescriptor) -> TemporalConnectorExtension:
    connector = table._client._connector_for_binding(table._binding)
    factory = getattr(connector, "temporal_extension_for", None)
    if not callable(factory):
        raise _error(
            "connector does not expose the temporal extension",
            ErrorCode.UNSUPPORTED_CAPABILITY,
            connector_id=table.connector_id,
        )
    extension = factory(table._binding, descriptor)
    if not isinstance(extension, TemporalConnectorExtension):
        raise _error(
            "connector temporal extension is invalid",
            ErrorCode.PROTOCOL_FAILURE,
            connector_id=table.connector_id,
        )
    return extension


def _descriptor_hash(table: Table, descriptor: TemporalTableDescriptor) -> str:
    extension = _extension_for(table, descriptor)
    descriptor_hash_for = getattr(extension, "descriptor_hash_for", None)
    if callable(descriptor_hash_for):
        return descriptor_hash_for(table._binding, descriptor)
    schema = pl.DataFrame(schema=table.schema).to_arrow().schema
    return temporal_descriptor_hash(descriptor, schema)


def _temporal_parameter(node: exp.Expression, parameters: Mapping[str, Any]) -> Any:
    if isinstance(node, exp.Parameter):
        name = _required_text(node.name, "parameter")
        if not name.isdecimal() or name == "0" or name.startswith("0"):
            raise ValueError("temporal SQL parameters must use canonical positive indexes")
        if name not in parameters:
            raise ValueError(f"missing temporal SQL parameter ${name}")
        value = parameters[name]
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
                raise ValueError("temporal timestamps must be UTC")
            return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f000Z")
        if isinstance(value, Decimal):
            if not value.is_finite() or len(value.as_tuple().digits) > 38:
                raise ValueError("temporal Decimal parameters must be finite Decimal128 values")
            return format(value, "f")
        if isinstance(value, float):
            raise ValueError("temporal SQL parameters do not accept float values")
        if not isinstance(value, (str, int, bool)):
            raise ValueError("temporal SQL parameter type is unsupported")
        return value
    if isinstance(node, exp.Literal):
        return node.to_py()
    raise ValueError("temporal SQL values must be numbered parameters or literals")


def _flatten_and(node: exp.Expression) -> tuple[exp.Expression, ...]:
    if isinstance(node, exp.And):
        return (*_flatten_and(node.this), *_flatten_and(node.expression))
    return (node,)


def _column_name(node: exp.Expression) -> str:
    if not isinstance(node, exp.Column) or node.table or node.db or node.catalog:
        raise ValueError("temporal SQL fields must be unqualified descriptor columns")
    return _required_text(node.name, "column")


def _temporal_predicates(
    where: exp.Where | None,
    descriptor: TemporalTableDescriptor,
    parameters: Mapping[str, Any],
) -> tuple[str | None, str | None, str | None, tuple[TagPredicate, ...]]:
    start = None
    end = None
    cutoff = None
    tags: list[TagPredicate] = []
    if where is None:
        return start, end, cutoff, ()
    filterable = set(descriptor.series_key_fields) | set(descriptor.tag_fields)
    for predicate in _flatten_and(where.this):
        if isinstance(predicate, (exp.GTE, exp.LT, exp.LTE)):
            field = _column_name(predicate.this)
            if field != descriptor.time_field:
                raise ValueError("temporal range comparisons may target only the event-time field")
            if not isinstance(predicate.expression, exp.Parameter):
                raise ValueError("temporal bounds must use typed numbered parameters")
            value = _temporal_parameter(predicate.expression, parameters)
            if not isinstance(value, str):
                raise ValueError("temporal bounds must be UTC timestamp strings")
            if isinstance(predicate, exp.GTE):
                if start is not None:
                    raise ValueError("temporal SQL contains duplicate lower bounds")
                start = value
            elif isinstance(predicate, exp.LT):
                if end is not None:
                    raise ValueError("temporal SQL contains duplicate upper bounds")
                end = value
            else:
                if cutoff is not None:
                    raise ValueError("temporal SQL contains duplicate latest cutoffs")
                cutoff = value
            continue
        if isinstance(predicate, exp.EQ):
            field = _column_name(predicate.this)
            if field not in filterable:
                raise ValueError("temporal equality filters require a series-key or tag field")
            if not isinstance(predicate.expression, exp.Parameter):
                raise ValueError("temporal tag values must use typed numbered parameters")
            tags.append(
                TagPredicate(
                    field,
                    TagOperator.EQ,
                    (_temporal_parameter(predicate.expression, parameters),),
                )
            )
            continue
        if isinstance(predicate, exp.In):
            field = _column_name(predicate.this)
            if field not in filterable or predicate.args.get("query") is not None:
                raise ValueError("temporal IN filters require literal series-key or tag values")
            if any(not isinstance(item, exp.Parameter) for item in predicate.expressions):
                raise ValueError("temporal tag values must use typed numbered parameters")
            tags.append(
                TagPredicate(
                    field,
                    TagOperator.IN,
                    tuple(_temporal_parameter(item, parameters) for item in predicate.expressions),
                )
            )
            continue
        raise ValueError("temporal SQL WHERE is outside the supported profile")
    if len({item.field for item in tags}) != len(tags):
        raise ValueError("temporal SQL contains duplicate tag predicates")
    return start, end, cutoff, tuple(tags)


def _temporal_limit(expression: exp.Select, limits: TemporalResourceLimits) -> int:
    limit = expression.args.get("limit")
    if not isinstance(limit, exp.Limit) or not isinstance(limit.expression, exp.Literal):
        raise ValueError("temporal SQL requires a positive literal LIMIT")
    literal = str(limit.expression.this)
    if (
        limit.expression.is_string
        or not limit.expression.is_int
        or not re.fullmatch(r"[1-9][0-9]*", literal)
    ):
        raise ValueError("temporal SQL LIMIT must be a positive integer")
    value = int(literal)
    if value <= 0 or value > limits.max_rows:
        raise ValueError("temporal SQL LIMIT must fit within max_rows")
    return value


def _temporal_order(expression: exp.Select) -> tuple[str, ...]:
    order = expression.args.get("order")
    if not isinstance(order, exp.Order) or not order.expressions:
        raise ValueError("temporal SQL requires deterministic ORDER BY")
    fields: list[str] = []
    for item in order.expressions:
        if bool(item.args.get("desc")):
            raise ValueError("temporal SQL v1 requires ascending output order")
        fields.append(_column_name(item.this))
    return tuple(fields)


def _fixed_bucket(
    node: exp.Expression, descriptor: TemporalTableDescriptor
) -> tuple[str, FixedBucket]:
    if not isinstance(node, exp.Alias) or not isinstance(node.this, exp.Anonymous):
        raise ValueError("temporal bucket projection must be aliased")
    function = node.this.name.casefold()
    if function not in {"time_bucket", "time_bucket_gapfill"}:
        raise ValueError("temporal SQL supports only time_bucket or time_bucket_gapfill")
    arguments = tuple(node.this.expressions)
    if len(arguments) != 2 or not isinstance(arguments[0], exp.Literal):
        raise ValueError("temporal bucket requires one literal fixed interval and event time")
    if _column_name(arguments[1]) != descriptor.time_field:
        raise ValueError("temporal bucket must use the descriptor event-time field")
    match = _INTERVAL.fullmatch(str(arguments[0].to_py()))
    if match is None or match.group(2).casefold() not in _FIXED_INTERVAL_NS:
        raise ValueError("temporal SQL v1 supports fixed sub-day bucket intervals")
    count = int(match.group(1))
    width_ns = count * _FIXED_INTERVAL_NS[match.group(2).casefold()]
    digits = _PRECISION_DIGITS[descriptor.precision]
    origin = "1970-01-01T00:00:00Z" if digits == 0 else f"1970-01-01T00:00:00.{0:0{digits}d}Z"
    return function, FixedBucket(
        width_ns=width_ns,
        origin=origin,
    )


def _aggregate_measure(
    node: exp.Expression,
    descriptor: TemporalTableDescriptor,
    *,
    gap_fill: bool,
) -> tuple[AggregateMeasure, FillRule | None]:
    if not isinstance(node, exp.Alias):
        raise ValueError("temporal aggregates require explicit unique aliases")
    output = _required_text(node.alias, "aggregate alias")
    aggregate = node.this
    fill = None
    if isinstance(aggregate, exp.Anonymous):
        wrapper = aggregate.name.casefold()
        if not gap_fill or wrapper not in {"locf", "interpolate"}:
            raise ValueError("unsupported temporal SQL aggregate wrapper")
        if len(aggregate.expressions) != 1:
            raise ValueError("gap-fill wrappers require exactly one aggregate")
        aggregate = aggregate.expressions[0]
        fill = FillRule(
            output,
            FillMode.LOCF if wrapper == "locf" else FillMode.LINEAR,
            None,
        )
    function_types = {
        exp.Count: AggregateFunction.COUNT,
        exp.Min: AggregateFunction.MIN,
        exp.Max: AggregateFunction.MAX,
        exp.Sum: AggregateFunction.SUM,
        exp.Avg: AggregateFunction.AVG,
        exp.First: AggregateFunction.FIRST,
        exp.Last: AggregateFunction.LAST,
    }
    function = next(
        (kind for node_type, kind in function_types.items() if isinstance(aggregate, node_type)),
        None,
    )
    if function is None:
        raise ValueError("temporal SQL aggregate is outside the supported profile")
    if function is AggregateFunction.COUNT:
        if not isinstance(aggregate.this, exp.Star):
            raise ValueError("temporal SQL v1 supports COUNT(*) only")
        value_field = None
    else:
        value_field = _column_name(aggregate.this)
        if value_field not in descriptor.value_fields:
            raise ValueError("temporal aggregates must target descriptor value fields")
    if (
        function in {AggregateFunction.FIRST, AggregateFunction.LAST}
        and _column_name(aggregate.expression) != descriptor.time_field
    ):
        raise ValueError("first/last aggregates must order by the event-time field")
    if (
        function in {AggregateFunction.FIRST, AggregateFunction.LAST}
        and descriptor.duplicate_policy.value == "preserve"
    ):
        raise ValueError("first/last aggregates require duplicate resolution")
    return AggregateMeasure(output, function, value_field), fill


def _lower_temporal_sql(
    view: TimeSeriesView,
    statement: str,
    *,
    parameters: Mapping[str, Any],
    snapshot_reference: str | None,
    limits: TemporalResourceLimits,
) -> Query:
    if "--" in statement or "/*" in statement:
        raise ValueError("temporal SQL comments are not supported")
    parsed = sqlglot.parse(statement, read=PROVIDER_POSTGRES)
    if len(parsed) != 1 or not isinstance(parsed[0], exp.Select):
        raise ValueError("temporal SQL accepts exactly one SELECT")
    expression = parsed[0]
    used_parameters = {node.name for node in expression.find_all(exp.Parameter)}
    if set(parameters) != used_parameters:
        raise ValueError("temporal SQL parameters must match the statement exactly")
    for key in ("joins", "with", "with_", "having", "distinct", "offset"):
        if expression.args.get(key):
            raise ValueError(f"temporal SQL does not support {key.upper()}")
    from_clause = expression.args.get("from_")
    if (
        not isinstance(from_clause, exp.From)
        or not isinstance(from_clause.this, exp.Table)
        or from_clause.this.name != "series"
        or from_clause.this.db
        or from_clause.this.catalog
        or from_clause.expressions
    ):
        raise ValueError("temporal SQL must read exactly the descriptor-bound source 'series'")
    result_limit = _temporal_limit(expression, limits)
    order = _temporal_order(expression)
    start, end, cutoff, tag_predicates = _temporal_predicates(
        expression.args.get("where"), view._descriptor, parameters
    )

    projections = tuple(expression.expressions)
    bucket_projection = projections[0] if projections else None
    is_bucket = (
        isinstance(bucket_projection, exp.Alias)
        and isinstance(bucket_projection.this, exp.Anonymous)
        and bucket_projection.this.name.casefold() in {"time_bucket", "time_bucket_gapfill"}
    )
    latest_projections = tuple(
        item
        for item in projections
        if isinstance(item, exp.Alias) and isinstance(item.this, exp.Last)
    )

    if is_bucket:
        if start is None or end is None or cutoff is not None:
            raise ValueError("temporal bucket SQL requires exact >= start and < end bounds")
        bucket_function, bucket = _fixed_bucket(bucket_projection, view._descriptor)
        group = expression.args.get("group")
        if not isinstance(group, exp.Group):
            raise ValueError("temporal bucket SQL requires GROUP BY")
        group_fields = tuple(_column_name(item) for item in group.expressions)
        if not group_fields or group_fields[0] != bucket_projection.alias:
            raise ValueError("temporal bucket GROUP BY must begin with the bucket alias")
        group_by = group_fields[1:]
        if any(
            field not in view._descriptor.series_key_fields + view._descriptor.tag_fields
            for field in group_by
        ):
            raise ValueError("temporal bucket group fields must be series keys or tags")
        if order != (*group_by, bucket_projection.alias):
            raise ValueError("temporal bucket ORDER BY must be group fields followed by bucket")
        gap_fill = bucket_function == "time_bucket_gapfill"
        measures: list[AggregateMeasure] = []
        fills: list[FillRule] = []
        for item in projections[1:]:
            if isinstance(item, exp.Column):
                if _column_name(item) not in group_by:
                    raise ValueError("non-aggregate bucket projections must be group fields")
                continue
            measure, fill = _aggregate_measure(item, view._descriptor, gap_fill=gap_fill)
            measures.append(measure)
            if fill is not None:
                fills.append(fill)
        if not measures:
            raise ValueError("temporal bucket SQL requires at least one aggregate")
        operation = (
            GapFill(start, end, bucket, group_by, tuple(measures), tag_predicates, tuple(fills))
            if gap_fill
            else BucketAggregate(start, end, bucket, group_by, tuple(measures), tag_predicates)
        )
    elif latest_projections:
        if cutoff is None or start is not None or end is not None:
            raise ValueError("temporal latest SQL requires one event-time <= cutoff")
        group = expression.args.get("group")
        group_by = () if group is None else tuple(_column_name(item) for item in group.expressions)
        if group_by != view._descriptor.series_key_fields or order != group_by:
            raise ValueError("temporal latest SQL must group and order by the complete series key")
        projection = list(group_by)
        for item in latest_projections:
            value_field = _column_name(item.this.this)
            if _column_name(item.this.expression) != view._descriptor.time_field:
                raise ValueError("last(value, event_time) must use the descriptor time field")
            if value_field not in view._descriptor.value_fields or item.alias != value_field:
                raise ValueError("latest value aliases must preserve descriptor field names")
            projection.append(value_field)
        if len(latest_projections) != len(projections) - len(group_by):
            raise ValueError("latest SQL projections may contain only series keys and last values")
        operation = Latest(cutoff, tuple(projection), tag_predicates)
    else:
        if start is None or end is None or cutoff is not None:
            raise ValueError("temporal scan SQL requires exact >= start and < end bounds")
        if expression.args.get("group") is not None:
            raise ValueError("temporal scan SQL does not support GROUP BY")
        projection = tuple(_column_name(item) for item in projections)
        if not projection or any(
            field not in view._descriptor.declared_fields for field in projection
        ):
            raise ValueError("temporal scan projection must contain descriptor fields")
        expected_order = (*view._descriptor.series_key_fields, view._descriptor.time_field)
        if order != expected_order:
            raise ValueError("temporal scan ORDER BY must use the complete observation order")
        operation = ScanRange(start, end, projection, tag_predicates)

    return view._query(
        operation,
        snapshot_reference=snapshot_reference,
        limits=limits,
        statement=statement,
        parameters=parameters,
        result_row_limit=result_limit,
    )


class TemporalStorage:
    def __init__(self, table: Table, descriptor: TemporalTableDescriptor) -> None:
        self._table = table
        self._descriptor = descriptor

    def _now_text(self) -> str:
        extension = _extension_for(self._table, self._descriptor)
        return getattr(extension, "current_time_text", _utc_text_now())

    def stage(
        self,
        frame: pl.DataFrame,
        *,
        idempotency_key: str,
        lease_expires_at: str | None = None,
    ) -> OperationResult[ManagedStage]:
        receipt = _extension_for(self._table, self._descriptor).stage_rows(
            self._table._binding,
            self._descriptor,
            frame,
            idempotency_key=_required_text(idempotency_key, "idempotency_key"),
        )
        stage = ManagedStage(
            logical_target=receipt.logical_target,
            physical_target=receipt.physical_target,
            stage_id=receipt.stage_id,
            idempotency_key=receipt.idempotency_key,
            descriptor_hash=receipt.descriptor_hash,
            artifact_hash=receipt.artifact_hash,
            staged_at=receipt.staged_at,
            lease_expires_at=lease_expires_at,
            _binding=self._table._binding,
            _owner_client_id=self._table._client._client_id,
        )
        return OperationResult(
            value=stage,
            outcome=Outcome.SUCCEEDED,
            commit=CommitState.NOT_APPLICABLE,
            verification=VerificationState.PASSED,
            receipts=(_receipt_from_stage(receipt),),
        )

    def commit(
        self,
        stage: ManagedStage,
        *,
        retention_expires_at: str | None = None,
    ) -> OperationResult[ManagedSnapshot]:
        self._assert_stage(stage)
        if _is_expired(stage.lease_expires_at, self._now_text()):
            raise _error("managed stage lease has expired", ErrorCode.INVALID_TARGET)
        try:
            receipt = _extension_for(self._table, self._descriptor).commit_stage(
                self._table._binding,
                self._descriptor,
                stage,
            )
        except TemporalExtensionError as exc:
            raise _error(
                exc.message,
                _map_temporal_error(exc.code),
                reconciliation=ReconciliationReference(
                    operation_id=stage.stage_id,
                    connector_id=self._table.connector_id,
                    idempotency_key=stage.idempotency_key,
                ),
                **dict(exc.safe_details),
            ) from exc
        snapshot = ManagedSnapshot(
            logical_target=receipt.logical_target,
            stage_id=receipt.stage_id,
            snapshot_id=receipt.snapshot_id,
            snapshot_reference=receipt.snapshot_reference,
            descriptor_hash=stage.descriptor_hash,
            committed_at=receipt.committed_at,
            retention_expires_at=retention_expires_at,
            _binding=self._table._binding,
            _owner_client_id=self._table._client._client_id,
        )
        return OperationResult(
            value=snapshot,
            outcome=Outcome.SUCCEEDED,
            commit=CommitState.COMMITTED,
            verification=VerificationState.PASSED,
            receipts=(_receipt_from_commit(receipt),),
        )

    def readback(self, snapshot: ManagedSnapshot) -> OperationResult[pl.DataFrame]:
        self._assert_snapshot(snapshot)
        if _is_expired(snapshot.retention_expires_at, self._now_text()):
            raise _error("managed snapshot retention has expired", ErrorCode.SNAPSHOT_UNAVAILABLE)
        result = _extension_for(self._table, self._descriptor).readback_snapshot(
            self._table._binding,
            self._descriptor,
            snapshot,
        )
        if result.table is None:
            raise _error(
                "managed readback did not return an Arrow table", ErrorCode.PROTOCOL_FAILURE
            )
        return OperationResult(
            value=pl.from_arrow(result.table),
            outcome=Outcome.SUCCEEDED,
            commit=CommitState.NOT_APPLICABLE,
            verification=VerificationState.PASSED,
            receipts=(_receipt_from_readback(result),),
        )

    def current(self) -> OperationResult[ManagedSnapshotState | None]:
        try:
            result = _extension_for(self._table, self._descriptor).current_snapshot(
                self._table._binding,
                self._descriptor,
            )
        except TemporalExtensionError as exc:
            raise _error(
                exc.message,
                _map_temporal_error(exc.code),
                connector_id=self._table.connector_id,
                **dict(exc.safe_details),
            ) from exc
        if result is None:
            return OperationResult(
                value=None,
                outcome=Outcome.SUCCEEDED,
                commit=CommitState.NOT_APPLICABLE,
                verification=VerificationState.PASSED,
                receipts=(),
            )
        if not isinstance(result, ManagedCurrentResult):
            raise _error("managed current result is invalid", ErrorCode.PROTOCOL_FAILURE)
        expected_hash = _descriptor_hash(self._table, self._descriptor)
        expected_schema = (
            pl.DataFrame(schema=self._table.schema)
            .select(list(self._descriptor.declared_fields))
            .to_arrow()
            .schema
        )
        if result.descriptor_hash != expected_hash or result.schema != expected_schema:
            raise _error(
                "managed current snapshot does not match this time-series view",
                ErrorCode.PROTOCOL_FAILURE,
            )
        snapshot = ManagedSnapshot(
            logical_target=self._table.uri,
            stage_id=f"current:{result.snapshot_id}",
            snapshot_id=result.snapshot_id,
            snapshot_reference=result.snapshot_reference,
            descriptor_hash=result.descriptor_hash,
            committed_at=result.committed_at,
            _binding=self._table._binding,
            _owner_client_id=self._table._client._client_id,
        )
        return OperationResult(
            value=ManagedSnapshotState(snapshot=snapshot, schema=result.schema),
            outcome=Outcome.SUCCEEDED,
            commit=CommitState.NOT_APPLICABLE,
            verification=VerificationState.PASSED,
            receipts=(),
        )

    def abort(self, stage: ManagedStage) -> OperationResult[AbortDisposition]:
        self._assert_stage(stage)
        observed_at = self._now_text()
        if _is_expired(stage.lease_expires_at, observed_at):
            return OperationResult(
                value=AbortDisposition.EXPIRED,
                outcome=Outcome.SUCCEEDED,
                commit=CommitState.NOT_APPLICABLE,
                verification=VerificationState.NOT_APPLICABLE,
                receipts=(_expired_abort_receipt(stage, observed_at),),
            )
        try:
            receipt = _extension_for(self._table, self._descriptor).abort_stage(
                self._table._binding,
                self._descriptor,
                stage,
            )
        except TemporalExtensionError as exc:
            raise _error(
                exc.message,
                _map_temporal_error(exc.code),
                reconciliation=ReconciliationReference(
                    operation_id=stage.stage_id,
                    connector_id=self._table.connector_id,
                    idempotency_key=stage.idempotency_key,
                ),
                **dict(exc.safe_details),
            ) from exc
        return OperationResult(
            value=_abort_disposition(receipt),
            outcome=Outcome.SUCCEEDED,
            commit=CommitState.NOT_APPLICABLE,
            verification=VerificationState.NOT_APPLICABLE,
            receipts=(_receipt_from_abort(receipt),),
        )

    def _assert_stage(self, stage: ManagedStage) -> None:
        if stage._owner_client_id != self._table._client._client_id:
            raise _error("managed stage belongs to a different client", ErrorCode.INVALID_TARGET)
        if stage._binding.uri != self._table.uri or stage.descriptor_hash != _descriptor_hash(
            self._table, self._descriptor
        ):
            raise _error(
                "managed stage does not match this time-series view", ErrorCode.INVALID_TARGET
            )

    def _assert_snapshot(self, snapshot: ManagedSnapshot) -> None:
        if snapshot._owner_client_id != self._table._client._client_id:
            raise _error("managed snapshot belongs to a different client", ErrorCode.INVALID_TARGET)
        if snapshot._binding.uri != self._table.uri or snapshot.descriptor_hash != _descriptor_hash(
            self._table, self._descriptor
        ):
            raise _error(
                "managed snapshot does not match this time-series view",
                ErrorCode.INVALID_TARGET,
            )


class TimeSeriesView:
    def __init__(self, table: Table, descriptor: TemporalTableDescriptor) -> None:
        self._table = table
        self._descriptor = descriptor
        self.storage = TemporalStorage(table, descriptor)

    def _projection(self, columns: tuple[str, ...] | None) -> tuple[str, ...]:
        if columns is not None:
            return columns
        return (
            self._descriptor.time_field,
            *self._descriptor.series_key_fields,
            *self._descriptor.tag_fields,
            *self._descriptor.value_fields,
        )

    def _query(
        self,
        operation: object,
        *,
        snapshot_reference: str | None = None,
        limits: TemporalResourceLimits | None = None,
        statement: str | None = None,
        parameters: Mapping[str, Any] | None = None,
        result_row_limit: int | None = None,
    ) -> Query:
        bounds = (limits or TemporalResourceLimits()).to_bounds()
        if isinstance(operation, ScanRange):
            required_capabilities = ("timeseries.scan.range/1.0",)
            output_order = (
                *[
                    OrderKey(field, OrderDirection.ASC)
                    for field in self._descriptor.series_key_fields
                ],
                OrderKey(self._descriptor.time_field, OrderDirection.ASC),
            )
        elif isinstance(operation, Latest):
            required_capabilities = ("timeseries.lookup.latest/1.0",)
            output_order = tuple(
                OrderKey(field, OrderDirection.ASC) for field in self._descriptor.series_key_fields
            )
        elif isinstance(operation, AsOf):
            required_capabilities = ("timeseries.lookup.asof/1.0",)
            output_order = (
                *[
                    OrderKey(field, OrderDirection.ASC)
                    for field in self._descriptor.series_key_fields
                ],
                OrderKey(self._descriptor.time_field, OrderDirection.ASC),
            )
        elif isinstance(operation, BucketAggregate):
            required_capabilities = ("timeseries.aggregate.window/1.0",)
            output_order = (
                *[OrderKey(field, OrderDirection.ASC) for field in operation.group_by],
                OrderKey("bucket", OrderDirection.ASC),
            )
        elif isinstance(operation, GapFill):
            required_capabilities = ("timeseries.fill/1.0",)
            output_order = (
                *[OrderKey(field, OrderDirection.ASC) for field in operation.group_by],
                OrderKey("bucket", OrderDirection.ASC),
            )
        else:
            raise TypeError("unsupported temporal operation")
        plan = PortableTemporalPlan(
            schema_version="otc.portable-temporal-plan/v1",
            descriptor_hash=_descriptor_hash(self._table, self._descriptor),
            relation="series",
            required_capabilities=required_capabilities,
            resource_bounds=bounds,
            operation=operation,
            output_order=output_order,
            result_row_limit=bounds.max_rows if result_row_limit is None else result_row_limit,
        )
        return Query(
            lane=QueryLane.TEMPORAL,
            statement=type(operation).__name__ if statement is None else statement,
            sources={"series": self._table},
            parameters={} if parameters is None else parameters,
            limits=limits or TemporalResourceLimits(),
            _definition=_TemporalQueryDefinition(
                binding=self._table._binding,
                descriptor=self._descriptor,
                plan=plan,
                snapshot_reference=snapshot_reference,
            ),
        )

    def scan_range(
        self,
        start: str,
        end: str,
        *,
        columns: tuple[str, ...] | None = None,
        tag_predicates: tuple[TagPredicate, ...] = (),
        snapshot_reference: str | None = None,
        limits: TemporalResourceLimits | None = None,
    ) -> Query:
        return self._query(
            ScanRange(start, end, self._projection(columns), tag_predicates),
            snapshot_reference=snapshot_reference,
            limits=limits,
        )

    def latest(
        self,
        *,
        at_or_before: str | None = None,
        columns: tuple[str, ...] | None = None,
        tag_predicates: tuple[TagPredicate, ...] = (),
        snapshot_reference: str | None = None,
        limits: TemporalResourceLimits | None = None,
    ) -> Query:
        return self._query(
            Latest(at_or_before, self._projection(columns), tag_predicates),
            snapshot_reference=snapshot_reference,
            limits=limits,
        )

    def as_of(
        self,
        at: str,
        *,
        columns: tuple[str, ...] | None = None,
        tag_predicates: tuple[TagPredicate, ...] = (),
        snapshot_reference: str | None = None,
        limits: TemporalResourceLimits | None = None,
    ) -> Query:
        return self._query(
            AsOf(at, self._projection(columns), tag_predicates),
            snapshot_reference=snapshot_reference,
            limits=limits,
        )

    def aggregate(
        self,
        start: str,
        end: str,
        *,
        bucket: FixedBucket | CalendarBucket,
        group_by: tuple[str, ...] = (),
        measures: tuple[AggregateMeasure, ...],
        tag_predicates: tuple[TagPredicate, ...] = (),
        snapshot_reference: str | None = None,
        limits: TemporalResourceLimits | None = None,
    ) -> Query:
        return self._query(
            BucketAggregate(start, end, bucket, group_by, measures, tag_predicates),
            snapshot_reference=snapshot_reference,
            limits=limits,
        )

    def gap_fill(
        self,
        start: str,
        end: str,
        *,
        bucket: FixedBucket | CalendarBucket,
        group_by: tuple[str, ...] = (),
        measures: tuple[AggregateMeasure, ...],
        fills: tuple[FillRule, ...],
        tag_predicates: tuple[TagPredicate, ...] = (),
        snapshot_reference: str | None = None,
        limits: TemporalResourceLimits | None = None,
    ) -> Query:
        return self._query(
            GapFill(start, end, bucket, group_by, measures, tag_predicates, fills),
            snapshot_reference=snapshot_reference,
            limits=limits,
        )

    def sql(
        self,
        statement: str,
        *,
        parameters: Mapping[str | int, Any],
        snapshot_reference: str | None = None,
        limits: TemporalResourceLimits | None = None,
    ) -> Query:
        normalized_parameters = {str(name): value for name, value in parameters.items()}
        effective_limits = limits or TemporalResourceLimits()
        try:
            return _lower_temporal_sql(
                self,
                statement,
                parameters=normalized_parameters,
                snapshot_reference=snapshot_reference,
                limits=effective_limits,
            )
        except OTCError:
            raise
        except (ValueError, TypeError, sqlglot.errors.ParseError) as exc:
            raise _error(str(exc), ErrorCode.INVALID_SQL) from exc

    def append(self, frame: pl.DataFrame, *, idempotency_key: str) -> OperationResult[int]:
        return _extension_for(self._table, self._descriptor).append_rows(
            self._table._binding,
            self._descriptor,
            frame,
            idempotency_key=_required_text(idempotency_key, "idempotency_key"),
        )

    def upsert(self, frame: pl.DataFrame, *, idempotency_key: str) -> OperationResult[int]:
        return _extension_for(self._table, self._descriptor).upsert_rows(
            self._table._binding,
            self._descriptor,
            frame,
            idempotency_key=_required_text(idempotency_key, "idempotency_key"),
        )


def execute_temporal_query(client: Client, query: Query) -> OperationResult[pl.DataFrame]:
    definition = query._definition
    if not isinstance(definition, _TemporalQueryDefinition):
        raise _error("temporal query definition is invalid", ErrorCode.PROTOCOL_FAILURE)
    source = query.sources.get("series")
    from .table import Table

    if not isinstance(source, Table):
        raise _error("temporal query source must be a physical Table", ErrorCode.INVALID_TARGET)
    client._assert_owned(source)
    executor = _extension_for(source, definition.descriptor).executor_for(
        source._binding, definition.descriptor
    )
    if not hasattr(executor, "execute"):
        raise _error("temporal executor is invalid", ErrorCode.PROTOCOL_FAILURE)
    request = TemporalExecutionRequest(
        target=source.uri,
        plan=definition.plan,
        credential_reference=None,
        operation_id=f"temporal-{source.uri.value}",
        snapshot_reference=definition.snapshot_reference,
    )
    try:
        result: TemporalExecutionResult = executor.execute(request)
    except TemporalExtensionError as exc:
        raise _error(exc.message, _map_temporal_error(exc.code), **dict(exc.safe_details)) from exc
    if result.table is None:
        raise _error("temporal executor did not return an Arrow table", ErrorCode.PROTOCOL_FAILURE)
    return OperationResult(
        value=pl.from_arrow(result.table),
        outcome=Outcome.SUCCEEDED,
        commit=CommitState.NOT_APPLICABLE,
        verification=VerificationState.PASSED,
        receipts=(_receipt_from_temporal(result.receipt, query),),
    )


__all__ = [
    "AbortDisposition",
    "AggregateFunction",
    "AggregateMeasure",
    "CalendarBucket",
    "FillMode",
    "FillRule",
    "FixedBucket",
    "ManagedSnapshot",
    "ManagedSnapshotState",
    "ManagedStage",
    "TemporalConnectorExtension",
    "TemporalResourceLimits",
    "TemporalTableDescriptor",
    "TimeSeriesView",
    "execute_temporal_query",
]
