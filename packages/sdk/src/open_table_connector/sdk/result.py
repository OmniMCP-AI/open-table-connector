"""SDK result types."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Generic, TypeVar

from open_table_connector.contract import TableURI

from .model import TableMode

T = TypeVar("T")

_SECRET_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
}


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _safe_json(value: Any, *, key: str | None = None) -> Any:
    if key is not None and key.casefold() in _SECRET_KEYS:
        return _Redacted
    if isinstance(value, BaseException):
        raise ValueError("safe details cannot contain exception objects")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        safe: dict[str, Any] = {}
        for raw_key, item in value.items():
            text_key = str(raw_key)
            redacted = _safe_json(item, key=text_key)
            if redacted is not _Redacted:
                safe[text_key] = redacted
        return safe
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_safe_json(item) for item in value]
    raise ValueError("safe details must contain JSON-compatible values")


class _RedactedType:
    pass


_Redacted = _RedactedType()


class Outcome(StrEnum):
    SUCCEEDED = "succeeded"
    PLANNED = "planned"
    REJECTED = "rejected"
    FAILED = "failed"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class CommitState(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    NOT_STARTED = "not_started"
    NOT_COMMITTED = "not_committed"
    COMMITTED = "committed"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class VerificationState(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    UNAVAILABLE = "unavailable"


class ErrorCode(StrEnum):
    INVALID_TARGET = "invalid_target"
    INVALID_FORMULA = "invalid_formula"
    INVALID_SCHEMA = "invalid_schema"
    INVALID_PREDICATE = "invalid_predicate"
    INVALID_SQL = "invalid_sql"
    INVALID_DESCRIPTOR = "invalid_descriptor"
    INVALID_CONFIGURATION = "invalid_configuration"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    UNSUPPORTED_MODE = "unsupported_mode"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DESTINATION_EXISTS = "destination_exists"
    TARGET_NOT_FOUND = "target_not_found"
    STALE_REVISION = "stale_revision"
    KEY_CONFLICT = "key_conflict"
    DUPLICATE_UPDATE_KEY = "duplicate_update_key"
    MISSING_UPDATE_KEY = "missing_update_key"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    RESOURCE_LIMIT = "resource_limit"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    SNAPSHOT_UNAVAILABLE = "snapshot_unavailable"
    EXECUTION_FAILED = "execution_failed"
    PARTIAL_EFFECT = "partial_effect"
    UNCERTAIN_MUTATION = "uncertain_mutation"
    RECONCILIATION_UNAVAILABLE = "reconciliation_unavailable"
    READBACK_MISMATCH = "readback_mismatch"
    PROTOCOL_FAILURE = "protocol_failure"
    ARTIFACT_INTEGRITY = "artifact_integrity"
    CLIENT_CLOSED = "client_closed"
    CLIENT_AFFINITY_MISMATCH = "client_affinity_mismatch"


@dataclass(frozen=True, slots=True)
class ReconciliationReference:
    operation_id: str
    connector_id: str | None = None
    idempotency_key: str | None = None
    expires_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "operation_id",
            _required_text(self.operation_id, "operation_id"),
        )
        for field_name in ("connector_id", "idempotency_key", "expires_at"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _required_text(value, field_name))

    def to_wire(self) -> dict[str, str | None]:
        return {
            "operation_id": self.operation_id,
            "connector_id": self.connector_id,
            "idempotency_key": self.idempotency_key,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> ReconciliationReference:
        if set(payload) != {"operation_id", "connector_id", "idempotency_key", "expires_at"}:
            raise ValueError("ReconciliationReference wire keys mismatch")
        return cls(
            operation_id=payload["operation_id"],
            connector_id=payload["connector_id"],
            idempotency_key=payload["idempotency_key"],
            expires_at=payload["expires_at"],
        )


@dataclass(frozen=True, slots=True)
class OperationWarning:
    code: str
    message: str
    safe_details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _required_text(self.code, "code"))
        object.__setattr__(self, "message", _required_text(self.message, "message"))
        object.__setattr__(
            self,
            "safe_details",
            _safe_json(dict(self.safe_details or {})),
        )

    def to_wire(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "safe_details": dict(self.safe_details),
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> OperationWarning:
        if set(payload) != {"code", "message", "safe_details"}:
            raise ValueError("OperationWarning wire keys mismatch")
        return cls(
            code=payload["code"],
            message=payload["message"],
            safe_details=payload["safe_details"],
        )


@dataclass(frozen=True, slots=True)
class Receipt:
    kind: str
    operation: str
    connector_id: str | None = None
    capability: str | None = None
    safe_target: TableURI | None = None
    mode: TableMode | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _required_text(self.kind, "kind"))
        object.__setattr__(self, "operation", _required_text(self.operation, "operation"))
        if self.connector_id is not None:
            object.__setattr__(
                self,
                "connector_id",
                _required_text(self.connector_id, "connector_id"),
            )
        if self.capability is not None:
            object.__setattr__(
                self,
                "capability",
                _required_text(self.capability, "capability"),
            )
        if self.safe_target is not None and not isinstance(self.safe_target, TableURI):
            object.__setattr__(self, "safe_target", TableURI(self.safe_target))
        if self.mode is not None:
            object.__setattr__(self, "mode", TableMode.from_wire(str(self.mode)))
        object.__setattr__(self, "details", _safe_json(dict(self.details or {})))

    def to_wire(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "operation": self.operation,
            "connector_id": self.connector_id,
            "capability": self.capability,
            "safe_target": None if self.safe_target is None else self.safe_target.to_wire(),
            "mode": None if self.mode is None else self.mode.to_wire(),
            "details": dict(self.details),
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> Receipt:
        if set(payload) != {
            "kind",
            "operation",
            "connector_id",
            "capability",
            "safe_target",
            "mode",
            "details",
        }:
            raise ValueError("Receipt wire keys mismatch")
        return cls(
            kind=payload["kind"],
            operation=payload["operation"],
            connector_id=payload["connector_id"],
            capability=payload["capability"],
            safe_target=None
            if payload["safe_target"] is None
            else TableURI.from_wire(payload["safe_target"]),
            mode=None if payload["mode"] is None else TableMode.from_wire(payload["mode"]),
            details=payload["details"],
        )


@dataclass(frozen=True, slots=True)
class ErrorInfo:
    code: ErrorCode
    message: str
    safe_details: Mapping[str, Any] = field(default_factory=dict)
    reconciliation: ReconciliationReference | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", ErrorCode(self.code))
        object.__setattr__(self, "message", _required_text(self.message, "message"))
        object.__setattr__(
            self,
            "safe_details",
            _safe_json(dict(self.safe_details or {})),
        )
        if self.reconciliation is not None and not isinstance(
            self.reconciliation, ReconciliationReference
        ):
            raise TypeError("reconciliation must be a ReconciliationReference")

    def to_wire(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "safe_details": dict(self.safe_details),
            "reconciliation": None
            if self.reconciliation is None
            else self.reconciliation.to_wire(),
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> ErrorInfo:
        if set(payload) != {"code", "message", "safe_details", "reconciliation"}:
            raise ValueError("ErrorInfo wire keys mismatch")
        return cls(
            code=ErrorCode(payload["code"]),
            message=payload["message"],
            safe_details=payload["safe_details"],
            reconciliation=None
            if payload["reconciliation"] is None
            else ReconciliationReference.from_wire(payload["reconciliation"]),
        )


@dataclass(frozen=True, slots=True)
class OperationResult(Generic[T]):
    value: T | None
    outcome: Outcome
    commit: CommitState
    verification: VerificationState
    receipts: tuple[Receipt, ...]
    continuation: str | None = None
    warnings: tuple[OperationWarning, ...] = ()
    error: ErrorInfo | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "outcome", Outcome(self.outcome))
        object.__setattr__(self, "commit", CommitState(self.commit))
        object.__setattr__(self, "verification", VerificationState(self.verification))
        object.__setattr__(self, "receipts", tuple(self.receipts))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        if self.continuation is not None:
            object.__setattr__(
                self,
                "continuation",
                _required_text(self.continuation, "continuation"),
            )
        if self.outcome in {Outcome.SUCCEEDED, Outcome.PLANNED} and self.error is not None:
            raise ValueError("successful or planned results cannot carry an error")
        if (
            self.outcome in {Outcome.REJECTED, Outcome.FAILED, Outcome.PARTIAL, Outcome.UNKNOWN}
            and self.error is None
        ):
            raise ValueError(f"{self.outcome.value} outcome requires an error")
        if self.outcome is Outcome.SUCCEEDED and self.commit not in {
            CommitState.NOT_APPLICABLE,
            CommitState.COMMITTED,
        }:
            raise ValueError("succeeded outcome requires committed or not_applicable commit state")
        if self.outcome is Outcome.PLANNED:
            if self.commit not in {CommitState.NOT_APPLICABLE, CommitState.NOT_STARTED}:
                raise ValueError(
                    "planned outcome requires not_applicable or not_started commit state"
                )
            if self.verification not in {
                VerificationState.NOT_APPLICABLE,
                VerificationState.SKIPPED,
            }:
                raise ValueError("planned outcome requires not_applicable or skipped verification")
        if self.outcome is Outcome.REJECTED:
            if self.commit not in {CommitState.NOT_APPLICABLE, CommitState.NOT_STARTED}:
                raise ValueError(
                    "rejected outcome requires not_applicable or not_started commit state"
                )
            if self.verification is not VerificationState.SKIPPED:
                raise ValueError("rejected outcome requires skipped verification")
        if self.outcome is Outcome.PARTIAL and self.commit is not CommitState.PARTIAL:
            raise ValueError("partial outcome requires partial commit state")
        if self.outcome is Outcome.UNKNOWN:
            if self.commit is not CommitState.UNKNOWN:
                raise ValueError("unknown outcome requires unknown commit state")
            if self.verification is not VerificationState.UNAVAILABLE:
                raise ValueError("unknown outcome requires unavailable verification")
        if self.continuation is not None and self.outcome is not Outcome.SUCCEEDED:
            raise ValueError("continuation is only valid for succeeded results")

    def require_value(self) -> T:
        if self.outcome is not Outcome.SUCCEEDED or self.value is None:
            if self.error is not None:
                raise OTCError(self.error.message, self)
            raise OTCError(
                "operation result did not carry a value",
                replace(
                    self,
                    outcome=Outcome.FAILED,
                    commit=self.commit,
                    verification=self.verification,
                    error=ErrorInfo(
                        code=ErrorCode.PROTOCOL_FAILURE,
                        message="operation result did not carry a value",
                    ),
                ),
            )
        return self.value

    def to_wire(self, value_encoder: Callable[[T], Any] | None = None) -> dict[str, Any]:
        if self.value is None:
            encoded_value = None
        elif value_encoder is not None:
            encoded_value = value_encoder(self.value)
        else:
            encoded_value = _safe_json(self.value)
        return {
            "value": encoded_value,
            "outcome": self.outcome.value,
            "commit": self.commit.value,
            "verification": self.verification.value,
            "receipts": [receipt.to_wire() for receipt in self.receipts],
            "continuation": self.continuation,
            "warnings": [warning.to_wire() for warning in self.warnings],
            "error": None if self.error is None else self.error.to_wire(),
        }

    @classmethod
    def from_wire(
        cls,
        payload: Mapping[str, Any],
        *,
        value_decoder: Callable[[Any], T] | None = None,
    ) -> OperationResult[T]:
        if set(payload) != {
            "value",
            "outcome",
            "commit",
            "verification",
            "receipts",
            "continuation",
            "warnings",
            "error",
        }:
            raise ValueError("OperationResult wire keys mismatch")
        value = payload["value"]
        if value_decoder is not None and value is not None:
            value = value_decoder(value)
        return cls(
            value=value,
            outcome=Outcome(payload["outcome"]),
            commit=CommitState(payload["commit"]),
            verification=VerificationState(payload["verification"]),
            receipts=tuple(Receipt.from_wire(item) for item in payload["receipts"]),
            continuation=payload["continuation"],
            warnings=tuple(OperationWarning.from_wire(item) for item in payload["warnings"]),
            error=None if payload["error"] is None else ErrorInfo.from_wire(payload["error"]),
        )


class OTCError(RuntimeError):
    def __init__(self, message: str, result: OperationResult[Any]) -> None:
        self.result = result
        super().__init__(_required_text(message, "message"))


__all__ = [
    "CommitState",
    "ErrorCode",
    "ErrorInfo",
    "OTCError",
    "OperationResult",
    "OperationWarning",
    "Outcome",
    "Receipt",
    "ReconciliationReference",
    "VerificationState",
]
