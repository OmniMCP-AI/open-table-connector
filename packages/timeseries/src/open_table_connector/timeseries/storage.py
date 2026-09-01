"""Temporal execution and managed-storage request/result protocols."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Mapping, Protocol, runtime_checkable

import pyarrow as pa

from open_table_connector.contract import ConnectorErrorCode, TableURI

from .plan import PortableTemporalPlan, ResourceBounds
from .receipts import (
    ManagedAbortReceipt,
    ManagedCommitReceipt,
    ManagedReadbackReceipt,
    ManagedStageReceipt,
    TemporalReceipt,
)


_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_STAGE_RE = re.compile(r"^stage:[0-9a-f]{64}$")


TemporalErrorCode = ConnectorErrorCode


class TemporalExtensionError(RuntimeError):
    """Stable extension-local error without widening contract v1."""

    def __init__(
        self,
        code: TemporalErrorCode,
        message: str,
        safe_details: Mapping[str, object] | None = None,
    ) -> None:
        if not isinstance(code, TemporalErrorCode):
            raise TypeError("code must be a TemporalErrorCode")
        self.code = code
        self.message = _text(message, "message")
        self.safe_details = dict(safe_details or {})
        super().__init__(self.message)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _hash(value: object, field: str) -> str:
    text = _text(value, field)
    if _HASH_RE.fullmatch(text) is None:
        raise ValueError(f"{field} must be a lowercase sha256 identity")
    return text


def _stage(value: object) -> str:
    text = _text(value, "stage_id")
    if _STAGE_RE.fullmatch(text) is None:
        raise ValueError("stage_id must be a lowercase stage identity")
    return text


@dataclass(frozen=True, slots=True)
class ArrowArtifactReference:
    relative_path: str
    sha256: str
    size_bytes: int
    media_type: str = "application/vnd.apache.arrow.stream"

    def __post_init__(self) -> None:
        path_text = _text(self.relative_path, "relative_path")
        path = PurePosixPath(path_text)
        if path.is_absolute():
            raise ValueError("artifact path must be relative")
        if ".." in path.parts:
            raise ValueError("artifact path cannot contain traversal")
        if any(part in {"", "."} for part in path.parts):
            raise ValueError("artifact path must be normalized")
        object.__setattr__(self, "relative_path", path.as_posix())
        object.__setattr__(self, "sha256", _hash(self.sha256, "sha256"))
        if isinstance(self.size_bytes, bool) or not isinstance(self.size_bytes, int) or self.size_bytes <= 0:
            raise ValueError("size_bytes must be a positive integer")
        if self.media_type != "application/vnd.apache.arrow.stream":
            raise ValueError("artifact media_type must be Arrow IPC stream")

    def to_wire(self) -> dict[str, object]:
        return {
            "relative_path": self.relative_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "media_type": self.media_type,
        }


@dataclass(frozen=True, slots=True)
class TemporalExecutionRequest:
    target: TableURI
    plan: PortableTemporalPlan
    credential_reference: str | None
    operation_id: str
    snapshot_reference: str | None
    credential_values: Mapping[str, str] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.target, TableURI):
            raise TypeError("target must be a TableURI")
        if not isinstance(self.plan, PortableTemporalPlan):
            raise TypeError("plan must be a PortableTemporalPlan")
        object.__setattr__(self, "operation_id", _text(self.operation_id, "operation_id"))
        for field in ("credential_reference", "snapshot_reference"):
            value = getattr(self, field)
            if value is not None:
                object.__setattr__(self, field, _text(value, field))
        if not isinstance(self.credential_values, Mapping):
            raise TypeError("credential_values must be a mapping")
        object.__setattr__(
            self,
            "credential_values",
            MappingProxyType({str(key): str(value) for key, value in self.credential_values.items()}),
        )


@dataclass(frozen=True, slots=True)
class TemporalExecutionResult:
    table: pa.Table | None
    artifact: ArrowArtifactReference | None
    receipt: TemporalReceipt | None

    def __post_init__(self) -> None:
        if (self.table is None) == (self.artifact is None):
            raise ValueError("temporal result requires exactly one Arrow carrier")
        if self.table is not None and not isinstance(self.table, pa.Table):
            raise TypeError("table must be a pyarrow.Table")
        if self.artifact is not None and not isinstance(self.artifact, ArrowArtifactReference):
            raise TypeError("artifact must be an ArrowArtifactReference")
        if self.receipt is None:
            raise ValueError("temporal result requires a receipt")
        if not isinstance(self.receipt, TemporalReceipt):
            raise TypeError("receipt must be a TemporalReceipt")


@dataclass(frozen=True, slots=True)
class ManagedStageRequest:
    operation_id: str
    artifact: ArrowArtifactReference
    descriptor_hash: str
    logical_target: TableURI
    physical_target: TableURI
    idempotency_key: str
    resource_bounds: ResourceBounds
    credential_values: Mapping[str, str] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "operation_id", _text(self.operation_id, "operation_id"))
        if not isinstance(self.artifact, ArrowArtifactReference):
            raise TypeError("artifact must be an ArrowArtifactReference")
        object.__setattr__(self, "descriptor_hash", _hash(self.descriptor_hash, "descriptor_hash"))
        for field in ("logical_target", "physical_target"):
            if not isinstance(getattr(self, field), TableURI):
                raise TypeError(f"{field} must be a TableURI")
        object.__setattr__(self, "idempotency_key", _text(self.idempotency_key, "idempotency_key"))
        if not isinstance(self.resource_bounds, ResourceBounds):
            raise TypeError("resource_bounds must be ResourceBounds")
        _bind_credentials(self)


@dataclass(frozen=True, slots=True)
class ManagedCommitRequest:
    operation_id: str
    logical_target: TableURI
    stage_id: str
    idempotency_key: str
    resource_bounds: ResourceBounds
    credential_values: Mapping[str, str] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "operation_id", _text(self.operation_id, "operation_id"))
        if not isinstance(self.logical_target, TableURI):
            raise TypeError("logical_target must be a TableURI")
        object.__setattr__(self, "stage_id", _stage(self.stage_id))
        object.__setattr__(self, "idempotency_key", _text(self.idempotency_key, "idempotency_key"))
        if not isinstance(self.resource_bounds, ResourceBounds):
            raise TypeError("resource_bounds must be ResourceBounds")
        _bind_credentials(self)


@dataclass(frozen=True, slots=True)
class ManagedReadbackRequest:
    operation_id: str
    logical_target: TableURI
    snapshot_id: str
    snapshot_reference: str
    resource_bounds: ResourceBounds
    credential_values: Mapping[str, str] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "operation_id", _text(self.operation_id, "operation_id"))
        if not isinstance(self.logical_target, TableURI):
            raise TypeError("logical_target must be a TableURI")
        object.__setattr__(self, "snapshot_id", _hash(self.snapshot_id, "snapshot_id"))
        object.__setattr__(
            self,
            "snapshot_reference",
            _text(self.snapshot_reference, "snapshot_reference"),
        )
        if not isinstance(self.resource_bounds, ResourceBounds):
            raise TypeError("resource_bounds must be ResourceBounds")
        _bind_credentials(self)


@dataclass(frozen=True, slots=True)
class ManagedReadbackResult:
    table: pa.Table | None
    artifact: ArrowArtifactReference | None
    receipt: ManagedReadbackReceipt

    def __post_init__(self) -> None:
        if (self.table is None) == (self.artifact is None):
            raise ValueError("managed readback requires exactly one Arrow carrier")
        if self.table is not None and not isinstance(self.table, pa.Table):
            raise TypeError("table must be a pyarrow.Table")
        if self.artifact is not None and not isinstance(self.artifact, ArrowArtifactReference):
            raise TypeError("artifact must be an ArrowArtifactReference")
        if not isinstance(self.receipt, ManagedReadbackReceipt):
            raise TypeError("receipt must be a ManagedReadbackReceipt")


@dataclass(frozen=True, slots=True)
class ManagedCurrentRequest:
    logical_target: TableURI
    descriptor_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.logical_target, TableURI):
            raise TypeError("logical_target must be a TableURI")
        object.__setattr__(self, "descriptor_hash", _hash(self.descriptor_hash, "descriptor_hash"))


@dataclass(frozen=True, slots=True)
class ManagedCurrentResult:
    snapshot_id: str
    snapshot_reference: str
    committed_at: str
    descriptor_hash: str
    schema: pa.Schema

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", _hash(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "snapshot_reference", _text(self.snapshot_reference, "snapshot_reference"))
        object.__setattr__(self, "committed_at", _text(self.committed_at, "committed_at"))
        object.__setattr__(self, "descriptor_hash", _hash(self.descriptor_hash, "descriptor_hash"))
        if not isinstance(self.schema, pa.Schema):
            raise TypeError("schema must be a pyarrow.Schema")


@dataclass(frozen=True, slots=True)
class ManagedAbortRequest:
    operation_id: str
    logical_target: TableURI
    stage_id: str
    credential_values: Mapping[str, str] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "operation_id", _text(self.operation_id, "operation_id"))
        if not isinstance(self.logical_target, TableURI):
            raise TypeError("logical_target must be a TableURI")
        object.__setattr__(self, "stage_id", _stage(self.stage_id))
        _bind_credentials(self)


def _bind_credentials(request: object) -> None:
    values = getattr(request, "credential_values")
    if not isinstance(values, Mapping):
        raise TypeError("credential_values must be a mapping")
    object.__setattr__(
        request,
        "credential_values",
        MappingProxyType({str(key): str(value) for key, value in values.items()}),
    )


def validate_stage_retry(
    existing: ManagedStageReceipt,
    request: ManagedStageRequest,
) -> ManagedStageReceipt:
    """Return an identical prior stage or reject conflicting idempotency reuse."""

    if not isinstance(existing, ManagedStageReceipt):
        raise TypeError("existing must be a ManagedStageReceipt")
    if not isinstance(request, ManagedStageRequest):
        raise TypeError("request must be a ManagedStageRequest")
    if (
        existing.logical_target != request.logical_target
        or existing.idempotency_key != request.idempotency_key
    ):
        raise ValueError("existing stage does not match retry target and idempotency key")
    if (
        existing.physical_target != request.physical_target
        or existing.artifact_hash != request.artifact.sha256
        or existing.descriptor_hash != request.descriptor_hash
    ):
        raise TemporalExtensionError(
            TemporalErrorCode.IDEMPOTENCY_CONFLICT,
            "idempotency key was already used with different staged content",
            {
                "logical_target": request.logical_target.value,
                "idempotency_key": request.idempotency_key,
                "existing_stage_id": existing.stage_id,
            },
        )
    return existing


@runtime_checkable
class PortableTemporalExecutor(Protocol):
    def execute(self, request: TemporalExecutionRequest) -> TemporalExecutionResult: ...


@runtime_checkable
class ManagedTemporalStore(Protocol):
    def stage(self, request: ManagedStageRequest) -> ManagedStageReceipt: ...

    def commit(self, request: ManagedCommitRequest) -> ManagedCommitReceipt: ...

    def readback(self, request: ManagedReadbackRequest) -> ManagedReadbackResult: ...

    def abort(self, request: ManagedAbortRequest) -> ManagedAbortReceipt: ...


__all__ = [
    "ArrowArtifactReference",
    "ManagedAbortRequest",
    "ManagedCommitRequest",
    "ManagedCurrentRequest",
    "ManagedCurrentResult",
    "ManagedReadbackRequest",
    "ManagedReadbackResult",
    "ManagedStageRequest",
    "ManagedTemporalStore",
    "PortableTemporalExecutor",
    "TemporalErrorCode",
    "TemporalExtensionError",
    "TemporalExecutionRequest",
    "TemporalExecutionResult",
    "validate_stage_retry",
]
