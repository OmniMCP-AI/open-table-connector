"""Closed PortableTemporalPlan v1 models, validation, and wire identity."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TypeAlias
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .descriptor import TemporalTableDescriptor, TimestampPrecision

_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_CAPABILITY_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*/[1-9][0-9]*\.[0-9]+$")
_UTC_RE = re.compile(
    r"^(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})T"
    r"(?P<time>[0-9]{2}:[0-9]{2}:[0-9]{2})"
    r"(?:\.(?P<fraction>[0-9]{1,9}))?Z$"
)


class TagOperator(StrEnum):
    EQ = "eq"
    IN = "in"


class OrderDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


class AggregateFunction(StrEnum):
    COUNT = "count"
    MIN = "min"
    MAX = "max"
    SUM = "sum"
    AVG = "avg"
    FIRST = "first"
    LAST = "last"


class FillMode(StrEnum):
    NULL = "null"
    CONSTANT = "constant"
    LOCF = "locf"
    LINEAR = "linear"


class CalendarUnit(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


JsonScalar: TypeAlias = str | int | float | bool | None


def _name(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _names(values: object, field: str) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{field} must be an array of strings")
    result = tuple(_name(value, field) for value in values)
    if len(result) != len(set(result)):
        label = "projection" if field == "projection" else field.replace("_", " ")
        raise ValueError(f"duplicate {label} field")
    return result


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _utc_parts(value: object, field: str) -> tuple[int, int]:
    text = _name(value, field)
    match = _UTC_RE.fullmatch(text)
    if match is None:
        raise ValueError(f"{field} must be an RFC 3339 UTC timestamp")
    try:
        whole = datetime.strptime(
            f"{match.group('date')}T{match.group('time')}",
            "%Y-%m-%dT%H:%M:%S",
        ).replace(tzinfo=UTC)
    except ValueError as exc:
        raise ValueError(f"{field} must be an RFC 3339 UTC timestamp") from exc
    fraction = (match.group("fraction") or "").ljust(9, "0")
    return int(whole.timestamp()), int(fraction or "0")


def _range(start: object, end: object) -> tuple[str, str]:
    start_text = _name(start, "start")
    end_text = _name(end, "end")
    if _utc_parts(start_text, "start") >= _utc_parts(end_text, "end"):
        raise ValueError("temporal range must be non-empty and increasing")
    return start_text, end_text


def _scalar(value: object, field: str, *, allow_none: bool = False) -> JsonScalar:
    if value is None:
        if allow_none:
            return None
        raise ValueError(f"{field} cannot be null")
    if isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ValueError(f"{field} must be a finite JSON scalar")


def _closed(document: object, expected: tuple[str, ...], label: str) -> Mapping[str, object]:
    if not isinstance(document, Mapping):
        raise ValueError(f"{label} must be an object")
    keys = set(document)
    expected_set = set(expected)
    unknown = sorted(keys - expected_set)
    missing = sorted(expected_set - keys)
    if unknown:
        raise ValueError(f"unknown {label} fields: {', '.join(unknown)}")
    if missing:
        raise ValueError(f"missing {label} fields: {', '.join(missing)}")
    return document


@dataclass(frozen=True, slots=True)
class ResourceBounds:
    max_rows: int
    max_bytes: int
    max_duration_ms: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_rows", _positive_int(self.max_rows, "max_rows"))
        object.__setattr__(self, "max_bytes", _positive_int(self.max_bytes, "max_bytes"))
        object.__setattr__(
            self,
            "max_duration_ms",
            _positive_int(self.max_duration_ms, "max_duration_ms"),
        )

    def to_wire(self) -> dict[str, int]:
        return {
            "max_rows": self.max_rows,
            "max_bytes": self.max_bytes,
            "max_duration_ms": self.max_duration_ms,
        }


@dataclass(frozen=True, slots=True)
class TagPredicate:
    field: str
    operator: TagOperator
    values: tuple[JsonScalar, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "field", _name(self.field, "predicate field"))
        object.__setattr__(self, "operator", TagOperator(self.operator))
        if not isinstance(self.values, (tuple, list)):
            raise ValueError("predicate values must be an array")
        object.__setattr__(
            self,
            "values",
            tuple(_scalar(value, "predicate value") for value in self.values),
        )
        if self.operator is TagOperator.EQ and len(self.values) != 1:
            raise ValueError("eq predicate requires exactly one value")
        if self.operator is TagOperator.IN and not self.values:
            raise ValueError("in predicate requires at least one value")

    def to_wire(self) -> dict[str, object]:
        return {"field": self.field, "operator": self.operator.value, "values": list(self.values)}


@dataclass(frozen=True, slots=True)
class OrderKey:
    field: str
    direction: OrderDirection

    def __post_init__(self) -> None:
        object.__setattr__(self, "field", _name(self.field, "order field"))
        object.__setattr__(self, "direction", OrderDirection(self.direction))

    def to_wire(self) -> dict[str, str]:
        return {"field": self.field, "direction": self.direction.value}


@dataclass(frozen=True, slots=True)
class FixedBucket:
    width_ns: int
    origin: str
    offset_ns: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "width_ns", _positive_int(self.width_ns, "width_ns"))
        _utc_parts(self.origin, "origin")
        if isinstance(self.offset_ns, bool) or not isinstance(self.offset_ns, int):
            raise ValueError("offset_ns must be an integer")

    def to_wire(self) -> dict[str, object]:
        return {
            "kind": "fixed",
            "width_ns": self.width_ns,
            "origin": self.origin,
            "offset_ns": self.offset_ns,
        }


@dataclass(frozen=True, slots=True)
class CalendarBucket:
    count: int
    unit: CalendarUnit
    timezone: str
    week_start: int
    origin: str
    offset_ns: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "count", _positive_int(self.count, "count"))
        object.__setattr__(self, "unit", CalendarUnit(self.unit))
        object.__setattr__(self, "timezone", _name(self.timezone, "timezone"))
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("timezone must be an IANA timezone name") from exc
        if isinstance(self.week_start, bool) or not isinstance(self.week_start, int) or not 1 <= self.week_start <= 7:
            raise ValueError("week_start must be an ISO weekday from 1 through 7")
        _utc_parts(self.origin, "origin")
        if isinstance(self.offset_ns, bool) or not isinstance(self.offset_ns, int):
            raise ValueError("offset_ns must be an integer")

    def to_wire(self) -> dict[str, object]:
        return {
            "kind": "calendar",
            "count": self.count,
            "unit": self.unit.value,
            "timezone": self.timezone,
            "week_start": self.week_start,
            "origin": self.origin,
            "offset_ns": self.offset_ns,
        }


Bucket: TypeAlias = FixedBucket | CalendarBucket


@dataclass(frozen=True, slots=True)
class AggregateMeasure:
    output_field: str
    function: AggregateFunction
    value_field: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "output_field", _name(self.output_field, "output_field"))
        object.__setattr__(self, "function", AggregateFunction(self.function))
        if self.value_field is not None:
            object.__setattr__(self, "value_field", _name(self.value_field, "value_field"))
        if self.function is AggregateFunction.COUNT:
            if self.value_field is not None:
                raise ValueError("count requires value_field to be null")
        elif self.value_field is None:
            raise ValueError(f"{self.function.value} requires value_field")

    def to_wire(self) -> dict[str, object]:
        return {
            "output_field": self.output_field,
            "function": self.function.value,
            "value_field": self.value_field,
        }


@dataclass(frozen=True, slots=True)
class FillRule:
    field: str
    mode: FillMode
    value: JsonScalar

    def __post_init__(self) -> None:
        object.__setattr__(self, "field", _name(self.field, "fill field"))
        object.__setattr__(self, "mode", FillMode(self.mode))
        if self.mode is FillMode.CONSTANT:
            object.__setattr__(self, "value", _scalar(self.value, "fill value"))
        elif self.value is not None:
            raise ValueError(f"{self.mode.value} fill cannot contain a value")

    def to_wire(self) -> dict[str, object]:
        return {"field": self.field, "mode": self.mode.value, "value": self.value}


def _predicates(value: object) -> tuple[TagPredicate, ...]:
    if not isinstance(value, (tuple, list)):
        raise ValueError("tag_predicates must be an array")
    result = tuple(
        item if isinstance(item, TagPredicate) else _predicate_from_wire(item) for item in value
    )
    fields = tuple(item.field for item in result)
    if len(fields) != len(set(fields)):
        raise ValueError("duplicate predicate field")
    return result


def _measures(value: object) -> tuple[AggregateMeasure, ...]:
    if not isinstance(value, (tuple, list)):
        raise ValueError("measures must be an array")
    result = tuple(
        item if isinstance(item, AggregateMeasure) else _measure_from_wire(item) for item in value
    )
    if not result:
        raise ValueError("measures must contain at least one aggregate")
    outputs = tuple(item.output_field for item in result)
    if len(outputs) != len(set(outputs)):
        raise ValueError("duplicate aggregate output field")
    return result


@dataclass(frozen=True, slots=True)
class ScanRange:
    start: str
    end: str
    projection: tuple[str, ...]
    tag_predicates: tuple[TagPredicate, ...]

    def __post_init__(self) -> None:
        start, end = _range(self.start, self.end)
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        object.__setattr__(self, "projection", _names(self.projection, "projection"))
        if not self.projection:
            raise ValueError("projection must contain at least one field")
        object.__setattr__(self, "tag_predicates", _predicates(self.tag_predicates))

    def to_wire(self) -> dict[str, object]:
        return {
            "kind": "scan_range",
            "start": self.start,
            "end": self.end,
            "projection": list(self.projection),
            "tag_predicates": [item.to_wire() for item in self.tag_predicates],
        }


@dataclass(frozen=True, slots=True)
class Latest:
    at_or_before: str | None
    projection: tuple[str, ...]
    tag_predicates: tuple[TagPredicate, ...]

    def __post_init__(self) -> None:
        if self.at_or_before is not None:
            _utc_parts(self.at_or_before, "at_or_before")
        object.__setattr__(self, "projection", _names(self.projection, "projection"))
        if not self.projection:
            raise ValueError("projection must contain at least one field")
        object.__setattr__(self, "tag_predicates", _predicates(self.tag_predicates))

    def to_wire(self) -> dict[str, object]:
        return {
            "kind": "latest",
            "at_or_before": self.at_or_before,
            "projection": list(self.projection),
            "tag_predicates": [item.to_wire() for item in self.tag_predicates],
        }


@dataclass(frozen=True, slots=True)
class AsOf:
    at: str
    projection: tuple[str, ...]
    tag_predicates: tuple[TagPredicate, ...]

    def __post_init__(self) -> None:
        _utc_parts(self.at, "at")
        object.__setattr__(self, "projection", _names(self.projection, "projection"))
        if not self.projection:
            raise ValueError("projection must contain at least one field")
        object.__setattr__(self, "tag_predicates", _predicates(self.tag_predicates))

    def to_wire(self) -> dict[str, object]:
        return {
            "kind": "as_of",
            "at": self.at,
            "projection": list(self.projection),
            "tag_predicates": [item.to_wire() for item in self.tag_predicates],
        }


@dataclass(frozen=True, slots=True)
class BucketAggregate:
    start: str
    end: str
    bucket: Bucket
    group_by: tuple[str, ...]
    measures: tuple[AggregateMeasure, ...]
    tag_predicates: tuple[TagPredicate, ...]

    def __post_init__(self) -> None:
        start, end = _range(self.start, self.end)
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        if not isinstance(self.bucket, (FixedBucket, CalendarBucket)):
            object.__setattr__(self, "bucket", _bucket_from_wire(self.bucket))
        object.__setattr__(self, "group_by", _names(self.group_by, "group_by"))
        object.__setattr__(self, "measures", _measures(self.measures))
        object.__setattr__(self, "tag_predicates", _predicates(self.tag_predicates))

    def to_wire(self) -> dict[str, object]:
        return {
            "kind": "bucket_aggregate",
            "start": self.start,
            "end": self.end,
            "bucket": self.bucket.to_wire(),
            "group_by": list(self.group_by),
            "measures": [item.to_wire() for item in self.measures],
            "tag_predicates": [item.to_wire() for item in self.tag_predicates],
        }


@dataclass(frozen=True, slots=True)
class GapFill:
    start: str
    end: str
    bucket: Bucket
    group_by: tuple[str, ...]
    measures: tuple[AggregateMeasure, ...]
    tag_predicates: tuple[TagPredicate, ...]
    fills: tuple[FillRule, ...]

    def __post_init__(self) -> None:
        start, end = _range(self.start, self.end)
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        if not isinstance(self.bucket, (FixedBucket, CalendarBucket)):
            object.__setattr__(self, "bucket", _bucket_from_wire(self.bucket))
        object.__setattr__(self, "group_by", _names(self.group_by, "group_by"))
        object.__setattr__(self, "measures", _measures(self.measures))
        object.__setattr__(self, "tag_predicates", _predicates(self.tag_predicates))
        if not isinstance(self.fills, (tuple, list)):
            raise ValueError("fills must be an array")
        fills = tuple(item if isinstance(item, FillRule) else _fill_from_wire(item) for item in self.fills)
        fill_fields = tuple(item.field for item in fills)
        if len(fill_fields) != len(set(fill_fields)):
            raise ValueError("duplicate fill field")
        object.__setattr__(self, "fills", fills)

    def to_wire(self) -> dict[str, object]:
        return {
            "kind": "gap_fill",
            "start": self.start,
            "end": self.end,
            "bucket": self.bucket.to_wire(),
            "group_by": list(self.group_by),
            "measures": [item.to_wire() for item in self.measures],
            "tag_predicates": [item.to_wire() for item in self.tag_predicates],
            "fills": [item.to_wire() for item in self.fills],
        }


TemporalOperation: TypeAlias = ScanRange | Latest | AsOf | BucketAggregate | GapFill


@dataclass(frozen=True, slots=True)
class PortableTemporalPlan:
    schema_version: str
    descriptor_hash: str
    relation: str
    required_capabilities: tuple[str, ...]
    resource_bounds: ResourceBounds
    operation: TemporalOperation
    output_order: tuple[OrderKey, ...]
    result_row_limit: int | None

    def __post_init__(self) -> None:
        if self.schema_version != "otc.portable-temporal-plan/v1":
            raise ValueError("unsupported portable temporal plan schema_version")
        if not isinstance(self.descriptor_hash, str) or _HASH_RE.fullmatch(self.descriptor_hash) is None:
            raise ValueError("descriptor_hash must be a lowercase sha256 identity")
        object.__setattr__(self, "relation", _name(self.relation, "relation"))
        if not isinstance(self.required_capabilities, (tuple, list)):
            raise ValueError("required_capabilities must be an array")
        capabilities = tuple(self.required_capabilities)
        if any(not isinstance(item, str) or _CAPABILITY_RE.fullmatch(item) is None for item in capabilities):
            raise ValueError("required_capabilities contains an invalid capability identity")
        if capabilities != tuple(sorted(set(capabilities))):
            raise ValueError("required_capabilities must be unique and sorted")
        object.__setattr__(self, "required_capabilities", capabilities)
        if not isinstance(self.resource_bounds, ResourceBounds):
            object.__setattr__(self, "resource_bounds", _bounds_from_wire(self.resource_bounds))
        if not isinstance(self.operation, (ScanRange, Latest, AsOf, BucketAggregate, GapFill)):
            object.__setattr__(self, "operation", _operation_from_wire(self.operation))
        if not isinstance(self.output_order, (tuple, list)):
            raise ValueError("output_order must be an array")
        output_order = tuple(
            item if isinstance(item, OrderKey) else _order_from_wire(item)
            for item in self.output_order
        )
        order_fields = tuple(item.field for item in output_order)
        if len(order_fields) != len(set(order_fields)):
            raise ValueError("duplicate output order field")
        object.__setattr__(self, "output_order", output_order)
        if self.result_row_limit is not None:
            limit = _positive_int(self.result_row_limit, "result_row_limit")
            if limit > self.resource_bounds.max_rows:
                raise ValueError("result_row_limit cannot exceed max_rows")
            object.__setattr__(self, "result_row_limit", limit)

    def to_wire(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "descriptor_hash": self.descriptor_hash,
            "relation": self.relation,
            "required_capabilities": list(self.required_capabilities),
            "resource_bounds": self.resource_bounds.to_wire(),
            "operation": self.operation.to_wire(),
            "output_order": [item.to_wire() for item in self.output_order],
            "result_row_limit": self.result_row_limit,
        }


def _bounds_from_wire(document: object) -> ResourceBounds:
    item = _closed(document, ("max_rows", "max_bytes", "max_duration_ms"), "resource_bounds")
    return ResourceBounds(item["max_rows"], item["max_bytes"], item["max_duration_ms"])


def _predicate_from_wire(document: object) -> TagPredicate:
    item = _closed(document, ("field", "operator", "values"), "tag predicate")
    return TagPredicate(item["field"], item["operator"], item["values"])


def _order_from_wire(document: object) -> OrderKey:
    item = _closed(document, ("field", "direction"), "order key")
    return OrderKey(item["field"], item["direction"])


def _bucket_from_wire(document: object) -> Bucket:
    if not isinstance(document, Mapping):
        raise ValueError("bucket must be an object")
    kind = document.get("kind")
    if kind == "fixed":
        item = _closed(document, ("kind", "width_ns", "origin", "offset_ns"), "fixed bucket")
        return FixedBucket(item["width_ns"], item["origin"], item["offset_ns"])
    if kind == "calendar":
        item = _closed(
            document,
            ("kind", "count", "unit", "timezone", "week_start", "origin", "offset_ns"),
            "calendar bucket",
        )
        return CalendarBucket(
            item["count"],
            item["unit"],
            item["timezone"],
            item["week_start"],
            item["origin"],
            item["offset_ns"],
        )
    raise ValueError("unsupported bucket kind")


def _measure_from_wire(document: object) -> AggregateMeasure:
    item = _closed(document, ("output_field", "function", "value_field"), "aggregate measure")
    return AggregateMeasure(item["output_field"], item["function"], item["value_field"])


def _fill_from_wire(document: object) -> FillRule:
    item = _closed(document, ("field", "mode", "value"), "fill rule")
    return FillRule(item["field"], item["mode"], item["value"])


def _operation_from_wire(document: object) -> TemporalOperation:
    if not isinstance(document, Mapping):
        raise ValueError("operation must be an object")
    kind = document.get("kind")
    if kind == "scan_range":
        item = _closed(
            document,
            ("kind", "start", "end", "projection", "tag_predicates"),
            "scan_range",
        )
        return ScanRange(item["start"], item["end"], item["projection"], item["tag_predicates"])
    if kind == "latest":
        item = _closed(
            document,
            ("kind", "at_or_before", "projection", "tag_predicates"),
            "latest",
        )
        return Latest(item["at_or_before"], item["projection"], item["tag_predicates"])
    if kind == "as_of":
        item = _closed(document, ("kind", "at", "projection", "tag_predicates"), "as_of")
        return AsOf(item["at"], item["projection"], item["tag_predicates"])
    if kind in {"bucket_aggregate", "gap_fill"}:
        expected = (
            "kind",
            "start",
            "end",
            "bucket",
            "group_by",
            "measures",
            "tag_predicates",
        )
        if kind == "gap_fill":
            expected = (*expected, "fills")
        item = _closed(document, expected, str(kind))
        common = {
            "start": item["start"],
            "end": item["end"],
            "bucket": item["bucket"],
            "group_by": item["group_by"],
            "measures": item["measures"],
            "tag_predicates": item["tag_predicates"],
        }
        return GapFill(**common, fills=item["fills"]) if kind == "gap_fill" else BucketAggregate(**common)
    raise ValueError("unsupported temporal operation kind")


def plan_from_wire(document: Mapping[str, object]) -> PortableTemporalPlan:
    item = _closed(
        document,
        (
            "schema_version",
            "descriptor_hash",
            "relation",
            "required_capabilities",
            "resource_bounds",
            "operation",
            "output_order",
            "result_row_limit",
        ),
        "portable plan",
    )
    return PortableTemporalPlan(**{key: item[key] for key in item})


def portable_plan_hash(plan: PortableTemporalPlan) -> str:
    if not isinstance(plan, PortableTemporalPlan):
        raise TypeError("plan must be a PortableTemporalPlan")
    encoded = json.dumps(
        plan.to_wire(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _validate_precision(value: str, precision: TimestampPrecision, field: str) -> None:
    match = _UTC_RE.fullmatch(value)
    if match is None:
        raise ValueError(f"{field} must be an RFC 3339 UTC timestamp")
    expected = {
        TimestampPrecision.SECOND: 0,
        TimestampPrecision.MILLISECOND: 3,
        TimestampPrecision.MICROSECOND: 6,
        TimestampPrecision.NANOSECOND: 9,
    }[precision]
    actual = len(match.group("fraction") or "")
    if actual != expected:
        raise ValueError(f"{field} does not match descriptor precision {precision.value}")


def validate_plan_for_descriptor(
    plan: PortableTemporalPlan,
    descriptor: TemporalTableDescriptor,
) -> None:
    declared = set(descriptor.declared_fields)
    operation = plan.operation
    projections = operation.projection if isinstance(operation, (ScanRange, Latest, AsOf)) else ()
    unknown_projection = sorted(set(projections) - declared)
    if unknown_projection:
        raise ValueError(f"projection contains undeclared fields: {', '.join(unknown_projection)}")

    allowed_predicates = set(descriptor.series_key_fields) | set(descriptor.tag_fields)
    unknown_predicates = sorted(
        predicate.field
        for predicate in operation.tag_predicates
        if predicate.field not in allowed_predicates
    )
    if unknown_predicates:
        raise ValueError(f"predicate field is not a series key or tag: {', '.join(unknown_predicates)}")

    timestamps: list[tuple[str, str]] = []
    if isinstance(operation, (ScanRange, BucketAggregate, GapFill)):
        timestamps.extend((("start", operation.start), ("end", operation.end)))
    elif isinstance(operation, Latest) and operation.at_or_before is not None:
        timestamps.append(("at_or_before", operation.at_or_before))
    elif isinstance(operation, AsOf):
        timestamps.append(("at", operation.at))
    if isinstance(operation, (BucketAggregate, GapFill)):
        timestamps.append(("origin", operation.bucket.origin))
        allowed_groups = allowed_predicates
        unknown_groups = sorted(set(operation.group_by) - allowed_groups)
        if unknown_groups:
            raise ValueError(f"group_by contains undeclared dimensions: {', '.join(unknown_groups)}")
        for measure in operation.measures:
            if measure.value_field is not None and measure.value_field not in descriptor.value_fields:
                raise ValueError(
                    f"aggregate value field is not declared: {measure.value_field}"
                )
            if (
                measure.function in {AggregateFunction.FIRST, AggregateFunction.LAST}
                and descriptor.duplicate_policy.value == "preserve"
            ):
                raise ValueError("first/last aggregates require duplicate resolution")
        outputs = [*operation.group_by, "bucket", *(measure.output_field for measure in operation.measures)]
        if len(outputs) != len(set(outputs)):
            raise ValueError("aggregate output fields must be unique")
        if isinstance(operation, GapFill):
            outputs = {measure.output_field for measure in operation.measures}
            unknown_fills = sorted(fill.field for fill in operation.fills if fill.field not in outputs)
            if unknown_fills:
                raise ValueError(f"fill field is not an aggregate output: {', '.join(unknown_fills)}")
    for field, value in timestamps:
        _validate_precision(value, descriptor.precision, field)
    allowed_order = set(
        projections
        if projections
        else (
            [*operation.group_by, "bucket", *(measure.output_field for measure in operation.measures)]
            if isinstance(operation, (BucketAggregate, GapFill))
            else descriptor.declared_fields
        )
    )
    order_fields = [key.field for key in plan.output_order]
    unknown_order = sorted(set(order_fields) - allowed_order)
    if unknown_order:
        raise ValueError(f"output_order contains fields absent from the result: {', '.join(unknown_order)}")
    if len(order_fields) != len(set(order_fields)):
        raise ValueError("output_order fields must be unique")


__all__ = [
    "AggregateFunction",
    "AggregateMeasure",
    "AsOf",
    "BucketAggregate",
    "CalendarBucket",
    "CalendarUnit",
    "FillMode",
    "FillRule",
    "FixedBucket",
    "GapFill",
    "Latest",
    "OrderDirection",
    "OrderKey",
    "PortableTemporalPlan",
    "ResourceBounds",
    "ScanRange",
    "TagOperator",
    "TagPredicate",
    "plan_from_wire",
    "portable_plan_hash",
    "validate_plan_for_descriptor",
]
