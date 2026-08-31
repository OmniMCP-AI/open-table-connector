"""Closed temporal execution and managed-lifecycle receipts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from open_table_connector.contract import NeutralReceipt, TableURI

from .plan import OrderKey, ResourceBounds, _bounds_from_wire, _order_from_wire, _utc_parts


_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_STAGE_RE = re.compile(r"^stage:[0-9a-f]{64}$")


class ExecutionLocation(StrEnum):
    PROVIDER = "provider"
    CONNECTOR = "connector"


class VisibilityGuarantee(StrEnum):
    ATOMIC = "atomic"
    NON_ATOMIC = "non_atomic"


class AbortDisposition(StrEnum):
    REMOVED = "removed"
    ALREADY_ABSENT = "already_absent"
    ALREADY_COMMITTED = "already_committed"


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _hash(value: object, field: str) -> str:
    text = _text(value, field)
    if _HASH_RE.fullmatch(text) is None:
        raise ValueError(f"{field} must be a lowercase sha256 identity")
    return text


def _nonnegative(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


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
class TimeRange:
    start: str
    end: str

    def __post_init__(self) -> None:
        start = _text(self.start, "start")
        end = _text(self.end, "end")
        if _utc_parts(start, "start") > _utc_parts(end, "end"):
            raise ValueError("time range start cannot be after end")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)

    def to_wire(self) -> dict[str, str]:
        return {"start": self.start, "end": self.end}

    @classmethod
    def from_wire(cls, document: Mapping[str, object]) -> "TimeRange":
        item = _closed(document, ("start", "end"), "time range")
        return cls(item["start"], item["end"])


@dataclass(frozen=True, slots=True)
class TemporalReceipt:
    schema_version: str
    neutral_receipt: NeutralReceipt
    descriptor_hash: str
    requested_range: TimeRange | None
    observed_range: TimeRange | None
    output_order: tuple[OrderKey, ...]
    execution_location: ExecutionLocation
    resource_bounds: ResourceBounds
    examined_rows: int
    examined_bytes: int
    returned_rows: int
    returned_bytes: int
    elapsed_ms: int
    snapshot_reference: str | None
    plan_schema_version: str
    portable_plan_hash: str

    def __post_init__(self) -> None:
        if self.schema_version != "otc.temporal-receipt/v1":
            raise ValueError("unsupported temporal receipt schema_version")
        if not isinstance(self.neutral_receipt, NeutralReceipt):
            object.__setattr__(
                self,
                "neutral_receipt",
                NeutralReceipt.from_wire(self.neutral_receipt),
            )
        object.__setattr__(self, "descriptor_hash", _hash(self.descriptor_hash, "descriptor_hash"))
        for field in ("requested_range", "observed_range"):
            value = getattr(self, field)
            if value is not None and not isinstance(value, TimeRange):
                object.__setattr__(self, field, TimeRange.from_wire(value))
        if not isinstance(self.output_order, (tuple, list)):
            raise ValueError("output_order must be an array")
        object.__setattr__(
            self,
            "output_order",
            tuple(
                item if isinstance(item, OrderKey) else _order_from_wire(item)
                for item in self.output_order
            ),
        )
        object.__setattr__(self, "execution_location", ExecutionLocation(self.execution_location))
        if not isinstance(self.resource_bounds, ResourceBounds):
            object.__setattr__(self, "resource_bounds", _bounds_from_wire(self.resource_bounds))
        for field in (
            "examined_rows",
            "examined_bytes",
            "returned_rows",
            "returned_bytes",
            "elapsed_ms",
        ):
            object.__setattr__(self, field, _nonnegative(getattr(self, field), field))
        if self.examined_rows > self.resource_bounds.max_rows or self.returned_rows > self.resource_bounds.max_rows:
            raise ValueError("receipt row counts cannot exceed max_rows")
        if self.examined_bytes > self.resource_bounds.max_bytes or self.returned_bytes > self.resource_bounds.max_bytes:
            raise ValueError("receipt byte counts cannot exceed max_bytes")
        if self.elapsed_ms > self.resource_bounds.max_duration_ms:
            raise ValueError("elapsed_ms cannot exceed max_duration_ms")
        if (
            self.neutral_receipt.row_count is not None
            and self.neutral_receipt.row_count != self.returned_rows
        ):
            raise ValueError("neutral receipt row_count must equal returned_rows")
        if self.snapshot_reference is not None:
            object.__setattr__(
                self,
                "snapshot_reference",
                _text(self.snapshot_reference, "snapshot_reference"),
            )
        if self.plan_schema_version != "otc.portable-temporal-plan/v1":
            raise ValueError("unsupported plan_schema_version")
        object.__setattr__(
            self,
            "portable_plan_hash",
            _hash(self.portable_plan_hash, "portable_plan_hash"),
        )

    def to_wire(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "neutral_receipt": self.neutral_receipt.to_wire(),
            "descriptor_hash": self.descriptor_hash,
            "requested_range": None if self.requested_range is None else self.requested_range.to_wire(),
            "observed_range": None if self.observed_range is None else self.observed_range.to_wire(),
            "output_order": [item.to_wire() for item in self.output_order],
            "execution_location": self.execution_location.value,
            "resource_bounds": self.resource_bounds.to_wire(),
            "examined_rows": self.examined_rows,
            "examined_bytes": self.examined_bytes,
            "returned_rows": self.returned_rows,
            "returned_bytes": self.returned_bytes,
            "elapsed_ms": self.elapsed_ms,
            "snapshot_reference": self.snapshot_reference,
            "plan_schema_version": self.plan_schema_version,
            "portable_plan_hash": self.portable_plan_hash,
        }

    @classmethod
    def from_wire(cls, document: Mapping[str, object]) -> "TemporalReceipt":
        fields = (
            "schema_version",
            "neutral_receipt",
            "descriptor_hash",
            "requested_range",
            "observed_range",
            "output_order",
            "execution_location",
            "resource_bounds",
            "examined_rows",
            "examined_bytes",
            "returned_rows",
            "returned_bytes",
            "elapsed_ms",
            "snapshot_reference",
            "plan_schema_version",
            "portable_plan_hash",
        )
        item = _closed(document, fields, "temporal receipt")
        return cls(**{field: item[field] for field in fields})


@dataclass(frozen=True, slots=True)
class ManagedStageReceipt:
    schema_version: str
    operation_id: str
    logical_target: TableURI
    physical_target: TableURI
    stage_id: str
    idempotency_key: str
    artifact_hash: str
    descriptor_hash: str
    staged_at: str
    visible: bool

    def __post_init__(self) -> None:
        if self.schema_version != "otc.managed-stage-receipt/v1":
            raise ValueError("unsupported managed stage receipt schema_version")
        object.__setattr__(self, "operation_id", _text(self.operation_id, "operation_id"))
        for field in ("logical_target", "physical_target"):
            value = getattr(self, field)
            if not isinstance(value, TableURI):
                object.__setattr__(self, field, TableURI.from_wire(value))
        stage_id = _text(self.stage_id, "stage_id")
        if _STAGE_RE.fullmatch(stage_id) is None:
            raise ValueError("stage_id must be a lowercase stage identity")
        object.__setattr__(self, "stage_id", stage_id)
        object.__setattr__(self, "idempotency_key", _text(self.idempotency_key, "idempotency_key"))
        object.__setattr__(self, "artifact_hash", _hash(self.artifact_hash, "artifact_hash"))
        object.__setattr__(self, "descriptor_hash", _hash(self.descriptor_hash, "descriptor_hash"))
        _utc_parts(self.staged_at, "staged_at")
        if self.visible is not False:
            raise ValueError("a managed stage receipt must remain invisible")

    def to_wire(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "operation_id": self.operation_id,
            "logical_target": self.logical_target.to_wire(),
            "physical_target": self.physical_target.to_wire(),
            "stage_id": self.stage_id,
            "idempotency_key": self.idempotency_key,
            "artifact_hash": self.artifact_hash,
            "descriptor_hash": self.descriptor_hash,
            "staged_at": self.staged_at,
            "visible": self.visible,
        }

    @classmethod
    def from_wire(cls, document: Mapping[str, object]) -> "ManagedStageReceipt":
        fields = (
            "schema_version",
            "operation_id",
            "logical_target",
            "physical_target",
            "stage_id",
            "idempotency_key",
            "artifact_hash",
            "descriptor_hash",
            "staged_at",
            "visible",
        )
        item = _closed(document, fields, "managed stage receipt")
        return cls(**{field: item[field] for field in fields})


@dataclass(frozen=True, slots=True)
class ManagedCommitReceipt:
    schema_version: str
    operation_id: str
    logical_target: TableURI
    stage_id: str
    idempotency_key: str
    snapshot_id: str
    snapshot_reference: str
    committed_at: str
    visibility: VisibilityGuarantee

    def __post_init__(self) -> None:
        if self.schema_version != "otc.managed-commit-receipt/v1":
            raise ValueError("unsupported managed commit receipt schema_version")
        object.__setattr__(self, "operation_id", _text(self.operation_id, "operation_id"))
        if not isinstance(self.logical_target, TableURI):
            object.__setattr__(self, "logical_target", TableURI.from_wire(self.logical_target))
        stage_id = _text(self.stage_id, "stage_id")
        if _STAGE_RE.fullmatch(stage_id) is None:
            raise ValueError("stage_id must be a lowercase stage identity")
        object.__setattr__(self, "stage_id", stage_id)
        object.__setattr__(self, "idempotency_key", _text(self.idempotency_key, "idempotency_key"))
        object.__setattr__(self, "snapshot_id", _hash(self.snapshot_id, "snapshot_id"))
        object.__setattr__(
            self,
            "snapshot_reference",
            _text(self.snapshot_reference, "snapshot_reference"),
        )
        _utc_parts(self.committed_at, "committed_at")
        object.__setattr__(self, "visibility", VisibilityGuarantee(self.visibility))

    def to_wire(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "operation_id": self.operation_id,
            "logical_target": self.logical_target.to_wire(),
            "stage_id": self.stage_id,
            "idempotency_key": self.idempotency_key,
            "snapshot_id": self.snapshot_id,
            "snapshot_reference": self.snapshot_reference,
            "committed_at": self.committed_at,
            "visibility": self.visibility.value,
        }

    @classmethod
    def from_wire(cls, document: Mapping[str, object]) -> "ManagedCommitReceipt":
        fields = (
            "schema_version",
            "operation_id",
            "logical_target",
            "stage_id",
            "idempotency_key",
            "snapshot_id",
            "snapshot_reference",
            "committed_at",
            "visibility",
        )
        item = _closed(document, fields, "managed commit receipt")
        return cls(**{field: item[field] for field in fields})


@dataclass(frozen=True, slots=True)
class ManagedReadbackReceipt:
    schema_version: str
    operation_id: str
    snapshot_id: str
    observed_at: str
    observed_schema_hash: str
    observed_content_hash: str
    observed_rows: int
    observed_bytes: int
    observed_range: TimeRange | None

    def __post_init__(self) -> None:
        if self.schema_version != "otc.managed-readback-receipt/v1":
            raise ValueError("unsupported managed readback receipt schema_version")
        object.__setattr__(self, "operation_id", _text(self.operation_id, "operation_id"))
        object.__setattr__(self, "snapshot_id", _hash(self.snapshot_id, "snapshot_id"))
        observed_at = _text(self.observed_at, "observed_at")
        _utc_parts(observed_at, "observed_at")
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(
            self,
            "observed_schema_hash",
            _hash(self.observed_schema_hash, "observed_schema_hash"),
        )
        object.__setattr__(
            self,
            "observed_content_hash",
            _hash(self.observed_content_hash, "observed_content_hash"),
        )
        object.__setattr__(self, "observed_rows", _nonnegative(self.observed_rows, "observed_rows"))
        object.__setattr__(self, "observed_bytes", _nonnegative(self.observed_bytes, "observed_bytes"))
        if self.observed_range is not None and not isinstance(self.observed_range, TimeRange):
            object.__setattr__(
                self,
                "observed_range",
                TimeRange.from_wire(self.observed_range),
            )

    def to_wire(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "operation_id": self.operation_id,
            "snapshot_id": self.snapshot_id,
            "observed_at": self.observed_at,
            "observed_schema_hash": self.observed_schema_hash,
            "observed_content_hash": self.observed_content_hash,
            "observed_rows": self.observed_rows,
            "observed_bytes": self.observed_bytes,
            "observed_range": None if self.observed_range is None else self.observed_range.to_wire(),
        }

    @classmethod
    def from_wire(cls, document: Mapping[str, object]) -> "ManagedReadbackReceipt":
        fields = (
            "schema_version",
            "operation_id",
            "snapshot_id",
            "observed_at",
            "observed_schema_hash",
            "observed_content_hash",
            "observed_rows",
            "observed_bytes",
            "observed_range",
        )
        item = _closed(document, fields, "managed readback receipt")
        return cls(**{field: item[field] for field in fields})


@dataclass(frozen=True, slots=True)
class ManagedAbortReceipt:
    schema_version: str
    operation_id: str
    logical_target: TableURI
    stage_id: str
    disposition: AbortDisposition
    aborted_at: str

    def __post_init__(self) -> None:
        if self.schema_version != "otc.managed-abort-receipt/v1":
            raise ValueError("unsupported managed abort receipt schema_version")
        object.__setattr__(self, "operation_id", _text(self.operation_id, "operation_id"))
        if not isinstance(self.logical_target, TableURI):
            object.__setattr__(self, "logical_target", TableURI.from_wire(self.logical_target))
        stage_id = _text(self.stage_id, "stage_id")
        if _STAGE_RE.fullmatch(stage_id) is None:
            raise ValueError("stage_id must be a lowercase stage identity")
        object.__setattr__(self, "stage_id", stage_id)
        object.__setattr__(self, "disposition", AbortDisposition(self.disposition))
        _utc_parts(self.aborted_at, "aborted_at")

    def to_wire(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "operation_id": self.operation_id,
            "logical_target": self.logical_target.to_wire(),
            "stage_id": self.stage_id,
            "disposition": self.disposition.value,
            "aborted_at": self.aborted_at,
        }

    @classmethod
    def from_wire(cls, document: Mapping[str, object]) -> "ManagedAbortReceipt":
        fields = (
            "schema_version",
            "operation_id",
            "logical_target",
            "stage_id",
            "disposition",
            "aborted_at",
        )
        item = _closed(document, fields, "managed abort receipt")
        return cls(**{field: item[field] for field in fields})


__all__ = [
    "AbortDisposition",
    "ExecutionLocation",
    "ManagedAbortReceipt",
    "ManagedCommitReceipt",
    "ManagedReadbackReceipt",
    "ManagedStageReceipt",
    "TemporalReceipt",
    "TimeRange",
    "VisibilityGuarantee",
]
