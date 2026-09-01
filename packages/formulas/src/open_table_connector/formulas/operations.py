"""Provider-facing formula request, binding, and idempotency records."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar

from .capabilities import ALL_CAPABILITIES
from .errors import (
    FormulaCommitState,
    FormulaError,
    FormulaErrorCode,
    FormulaExtensionErrorInfo,
    FormulaExtensionResult,
    FormulaOutcome,
    FormulaVerificationState,
)
from .model import (
    BoundFieldFormulaTarget,
    BoundGridFormulaTarget,
    FieldFormulaTarget,
    FieldRecalculationScope,
    FormulaExpression,
    FormulaResourceLimits,
    GridFormulaTarget,
    GridRecalculationScope,
)
from .observations import FormulaCapabilitySet
from .ranges import A1Rectangle

_TTable = TypeVar("_TTable")
_CAPABILITY_REFERENCES = {capability.to_reference() for capability in ALL_CAPABILITIES}


def _hash_text(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
        raise ValueError(f"{field_name} must be a lowercase sha256 identity when provided")
    return value


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_text(value: object, field_name: str) -> str | None:
    return None if value is None else _text(value, field_name)


def _capability(value: object) -> str:
    text = _text(value, "capability")
    if text not in _CAPABILITY_REFERENCES:
        raise ValueError("capability must belong to the closed Formula capability set")
    return text


def _grid_range(value: object, field_name: str = "cell_range") -> str:
    selector = A1Rectangle.parse(_text(value, field_name))
    if selector.worksheet_name is not None:
        raise ValueError(f"{field_name} must be unbound after target binding")
    if selector.start_address == selector.end_address:
        return selector.start_address
    return f"{selector.start_address}:{selector.end_address}"


@dataclass(frozen=True, slots=True)
class GridFormulaBinding:
    target: BoundGridFormulaTarget
    capabilities: FormulaCapabilitySet
    observed_revision: str | None

    def __post_init__(self) -> None:
        _hash_text(self.observed_revision, "observed_revision")


@dataclass(frozen=True, slots=True)
class FieldFormulaBinding(Generic[_TTable]):
    target: BoundFieldFormulaTarget[_TTable]
    capabilities: FormulaCapabilitySet
    observed_revision: str | None

    def __post_init__(self) -> None:
        _hash_text(self.observed_revision, "observed_revision")


@dataclass(frozen=True, slots=True)
class GridFormulaBindRequest:
    target: GridFormulaTarget


@dataclass(frozen=True, slots=True)
class FieldFormulaBindRequest(Generic[_TTable]):
    target: FieldFormulaTarget[_TTable]


@dataclass(frozen=True, slots=True)
class GridFormulaReadRequest:
    target: BoundGridFormulaTarget
    cell_range: str
    limits: FormulaResourceLimits | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cell_range", _grid_range(self.cell_range))


@dataclass(frozen=True, slots=True)
class FieldFormulaReadRequest(Generic[_TTable]):
    target: BoundFieldFormulaTarget[_TTable]


@dataclass(frozen=True, slots=True)
class GridFormulaSetRequest:
    target: BoundGridFormulaTarget
    cell_range: str
    expression: FormulaExpression
    expected_revision: str | None = None
    idempotency_key: str | None = None
    limits: FormulaResourceLimits | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cell_range", _grid_range(self.cell_range))
        _hash_text(self.expected_revision, "expected_revision")
        object.__setattr__(self, "idempotency_key", _optional_text(self.idempotency_key, "idempotency_key"))


@dataclass(frozen=True, slots=True)
class FieldFormulaSetRequest(Generic[_TTable]):
    target: BoundFieldFormulaTarget[_TTable]
    expression: FormulaExpression
    expected_revision: str | None = None
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        _hash_text(self.expected_revision, "expected_revision")
        object.__setattr__(self, "idempotency_key", _optional_text(self.idempotency_key, "idempotency_key"))


@dataclass(frozen=True, slots=True)
class GridFormulaValueReadRequest:
    target: BoundGridFormulaTarget
    cell_range: str
    limits: FormulaResourceLimits | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cell_range", _grid_range(self.cell_range))


@dataclass(frozen=True, slots=True)
class FieldFormulaValueReadRequest(Generic[_TTable]):
    target: BoundFieldFormulaTarget[_TTable]
    limits: FormulaResourceLimits | None = None


@dataclass(frozen=True, slots=True)
class GridFormulaRecalculateRequest:
    target: BoundGridFormulaTarget
    scope: GridRecalculationScope
    cell_range: str | None = None
    expected_revision: str | None = None
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        if self.cell_range is not None:
            object.__setattr__(self, "cell_range", _grid_range(self.cell_range))
        if self.scope is GridRecalculationScope.RANGE and self.cell_range is None:
            raise ValueError("cell_range is required for range recalculation")
        if self.scope is not GridRecalculationScope.RANGE and self.cell_range is not None:
            raise ValueError("cell_range is only allowed for range recalculation")
        _hash_text(self.expected_revision, "expected_revision")
        object.__setattr__(self, "idempotency_key", _optional_text(self.idempotency_key, "idempotency_key"))


@dataclass(frozen=True, slots=True)
class FieldFormulaRecalculateRequest(Generic[_TTable]):
    target: BoundFieldFormulaTarget[_TTable]
    scope: FieldRecalculationScope
    expected_revision: str | None = None
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        _hash_text(self.expected_revision, "expected_revision")
        object.__setattr__(self, "idempotency_key", _optional_text(self.idempotency_key, "idempotency_key"))


class FormulaIdempotencyDisposition(StrEnum):
    STARTED = "started"
    REPLAY = "replay"
    CONFLICT = "conflict"
    UNKNOWN = "unknown"
    IN_FLIGHT = "in_flight"


@dataclass(frozen=True, slots=True)
class FormulaIdempotencyDecision:
    disposition: FormulaIdempotencyDisposition
    operation_hash: str | None = None


@dataclass(slots=True)
class _LedgerEntry:
    capability: str
    payload_hash: str
    state: str
    operation_hash: str | None = None


class FormulaIdempotencyLedger:
    def __init__(self, *, limit: int) -> None:
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError("limit must be a positive integer")
        self._limit = limit
        self._entries: OrderedDict[tuple[str, str, str, str], _LedgerEntry] = OrderedDict()

    def begin(
        self,
        *,
        connector_id: str,
        capability: str,
        target_hash: str,
        selector_hash: str,
        idempotency_key: str,
        payload_hash: str,
    ) -> FormulaIdempotencyDecision:
        key = self._key(connector_id, target_hash, selector_hash, idempotency_key)
        capability_text = _capability(capability)
        payload_hash_text = _text(payload_hash, "payload_hash")
        entry = self._entries.get(key)
        if entry is None:
            self._make_room()
            self._entries[key] = _LedgerEntry(
                capability=capability_text,
                payload_hash=payload_hash_text,
                state="in_flight",
            )
            self._evict_completed()
            return FormulaIdempotencyDecision(FormulaIdempotencyDisposition.STARTED)
        if entry.payload_hash != payload_hash_text or entry.capability != capability_text:
            return FormulaIdempotencyDecision(FormulaIdempotencyDisposition.CONFLICT, entry.operation_hash)
        if entry.state == "succeeded":
            return FormulaIdempotencyDecision(FormulaIdempotencyDisposition.REPLAY, entry.operation_hash)
        if entry.state == "unknown":
            return FormulaIdempotencyDecision(FormulaIdempotencyDisposition.UNKNOWN, entry.operation_hash)
        return FormulaIdempotencyDecision(FormulaIdempotencyDisposition.IN_FLIGHT, entry.operation_hash)

    def succeed(
        self,
        *,
        connector_id: str,
        target_hash: str,
        selector_hash: str,
        idempotency_key: str,
        payload_hash: str,
        operation_hash: str,
    ) -> None:
        entry = self._require(connector_id, target_hash, selector_hash, idempotency_key, payload_hash)
        entry.state = "succeeded"
        entry.operation_hash = _text(operation_hash, "operation_hash")
        self._evict_completed()

    def fail_known(
        self,
        *,
        connector_id: str,
        target_hash: str,
        selector_hash: str,
        idempotency_key: str,
        payload_hash: str,
        operation_hash: str | None = None,
    ) -> None:
        entry = self._require(connector_id, target_hash, selector_hash, idempotency_key, payload_hash)
        entry.state = "failed"
        entry.operation_hash = _optional_text(operation_hash, "operation_hash")
        self._evict_completed()

    def mark_unknown(
        self,
        *,
        connector_id: str,
        target_hash: str,
        selector_hash: str,
        idempotency_key: str,
        payload_hash: str,
    ) -> None:
        entry = self._require(connector_id, target_hash, selector_hash, idempotency_key, payload_hash)
        entry.state = "unknown"

    def _require(
        self,
        connector_id: str,
        target_hash: str,
        selector_hash: str,
        idempotency_key: str,
        payload_hash: str,
    ) -> _LedgerEntry:
        key = self._key(connector_id, target_hash, selector_hash, idempotency_key)
        entry = self._entries[key]
        if entry.payload_hash != _text(payload_hash, "payload_hash"):
            raise ValueError("payload_hash does not match the existing idempotency binding")
        return entry

    def _key(
        self,
        connector_id: str,
        target_hash: str,
        selector_hash: str,
        idempotency_key: str,
    ) -> tuple[str, str, str, str]:
        return (
            _text(connector_id, "connector_id"),
            _text(target_hash, "target_hash"),
            _text(selector_hash, "selector_hash"),
            _text(idempotency_key, "idempotency_key"),
        )

    def _evict_completed(self) -> None:
        while len(self._entries) > self._limit:
            removable = next(
                (key for key, entry in self._entries.items() if entry.state in {"succeeded", "failed"}),
                None,
            )
            if removable is None:
                break
            self._entries.pop(removable)

    def _make_room(self) -> None:
        while len(self._entries) >= self._limit:
            removable = next(
                (key for key, entry in self._entries.items() if entry.state in {"succeeded", "failed"}),
                None,
            )
            if removable is None:
                raise FormulaError("formula idempotency ledger resource limit reached")
            self._entries.pop(removable)


def unsupported_result(*, target_kind: str, capability: str) -> FormulaExtensionResult[None]:
    return FormulaExtensionResult(
        value=None,
        outcome=FormulaOutcome.REJECTED,
        commit=FormulaCommitState.NOT_STARTED,
        verification=FormulaVerificationState.SKIPPED,
        receipts=(),
        error=FormulaExtensionErrorInfo(
            code=FormulaErrorCode.UNSUPPORTED_CAPABILITY,
            message="formula capability is not available for this target kind",
            safe_details={"target_kind": target_kind, "capability": capability},
        ),
    )


__all__ = [
    "FieldFormulaBinding",
    "FieldFormulaBindRequest",
    "FieldFormulaReadRequest",
    "FieldFormulaRecalculateRequest",
    "FieldFormulaSetRequest",
    "FieldFormulaValueReadRequest",
    "FormulaIdempotencyDecision",
    "FormulaIdempotencyDisposition",
    "FormulaIdempotencyLedger",
    "GridFormulaBinding",
    "GridFormulaBindRequest",
    "GridFormulaReadRequest",
    "GridFormulaRecalculateRequest",
    "GridFormulaSetRequest",
    "GridFormulaValueReadRequest",
    "unsupported_result",
]
