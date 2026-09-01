"""Formula extension error and result types."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Generic, TypeVar

from open_table_connector.contract.errors import _safe_value

_SAFE_DETAIL_KEYS = {
    "affected_count",
    "capability",
    "dialect",
    "field_id",
    "limit",
    "operation_hash",
    "payload_hash",
    "provider_status_code",
    "range",
    "revision_hash",
    "safe_uri",
    "status",
    "target",
    "target_kind",
    "worksheet_id",
}


def _is_unsafe_detail_value(value: object) -> bool:
    return isinstance(value, str) and (
        value.lstrip().startswith("=")
        or "http://" in value.casefold()
        or "https://" in value.casefold()
    )


def _formula_safe_details(value: Mapping[str, Any] | None) -> dict[str, Any]:
    details = _safe_value({} if value is None else value)
    return {
        key: item
        for key, item in details.items()
        if key.casefold() in _SAFE_DETAIL_KEYS and not _is_unsafe_detail_value(item)
    }


class FormulaError(ValueError):
    """Base exception for formula domain validation errors."""


class FormulaErrorCode(StrEnum):
    INVALID_TARGET = "invalid_target"
    UNSUPPORTED_MODE = "unsupported_mode"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    TARGET_NOT_FOUND = "target_not_found"
    STALE_REVISION = "stale_revision"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    RESOURCE_LIMIT = "resource_limit"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    SNAPSHOT_UNAVAILABLE = "snapshot_unavailable"
    EXECUTION_FAILED = "execution_failed"
    PARTIAL_EFFECT = "partial_effect"
    UNCERTAIN_MUTATION = "uncertain_mutation"
    READBACK_MISMATCH = "readback_mismatch"
    PROTOCOL_FAILURE = "protocol_failure"
    CLIENT_CLOSED = "client_closed"
    CLIENT_AFFINITY_MISMATCH = "client_affinity_mismatch"
    INVALID_FORMULA = "invalid_formula"


class FormulaOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    PLANNED = "planned"
    REJECTED = "rejected"
    FAILED = "failed"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class FormulaCommitState(StrEnum):
    NOT_STARTED = "not_started"
    NOT_APPLICABLE = "not_applicable"
    COMMITTED = "committed"
    NOT_COMMITTED = "not_committed"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class FormulaVerificationState(StrEnum):
    SKIPPED = "skipped"
    PASSED = "passed"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class FormulaExtensionErrorInfo:
    code: FormulaErrorCode
    message: str
    safe_details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        code = self.code if isinstance(self.code, FormulaErrorCode) else FormulaErrorCode(self.code)
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("message must be a non-empty string")
        safe_details = _formula_safe_details(self.safe_details)
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "message", self.message.strip())
        object.__setattr__(self, "safe_details", safe_details)

    def to_wire(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "safe_details": dict(self.safe_details),
        }


_T = TypeVar("_T")


@dataclass(frozen=True, slots=True)
class FormulaExtensionResult(Generic[_T]):
    value: _T | None
    outcome: FormulaOutcome
    commit: FormulaCommitState
    verification: FormulaVerificationState
    receipts: tuple[object, ...]
    error: FormulaExtensionErrorInfo | None = None

    def __post_init__(self) -> None:
        outcome = self.outcome if isinstance(self.outcome, FormulaOutcome) else FormulaOutcome(self.outcome)
        commit = self.commit if isinstance(self.commit, FormulaCommitState) else FormulaCommitState(self.commit)
        verification = (
            self.verification
            if isinstance(self.verification, FormulaVerificationState)
            else FormulaVerificationState(self.verification)
        )
        receipts = tuple(self.receipts)
        if any(receipt is None for receipt in receipts):
            raise TypeError("receipts must not contain None")
        if self.error is not None and not isinstance(self.error, FormulaExtensionErrorInfo):
            raise TypeError("error must be FormulaExtensionErrorInfo or None")
        has_value = self.value is not None

        if outcome is FormulaOutcome.SUCCEEDED:
            if self.error is not None:
                raise ValueError("succeeded result must not carry an error")
            if not has_value:
                raise ValueError("succeeded result requires a value")
            if commit not in {FormulaCommitState.NOT_APPLICABLE, FormulaCommitState.COMMITTED}:
                raise ValueError("illegal succeeded state requires committed or not_applicable")
            if verification is not FormulaVerificationState.PASSED:
                raise ValueError("illegal succeeded state requires passed verification")
        elif outcome is FormulaOutcome.REJECTED:
            if has_value:
                raise ValueError("rejected result must not carry a value")
            if self.error is None:
                raise ValueError("rejected result requires an error")
            if commit is not FormulaCommitState.NOT_STARTED or verification is not FormulaVerificationState.SKIPPED:
                raise ValueError("illegal rejected state")
        elif outcome is FormulaOutcome.FAILED:
            if has_value:
                raise ValueError("failed result must not carry a value")
            if self.error is None:
                raise ValueError("failed result requires an error")
            if (commit, verification) not in {
                (FormulaCommitState.NOT_COMMITTED, FormulaVerificationState.SKIPPED),
                (FormulaCommitState.COMMITTED, FormulaVerificationState.FAILED),
            }:
                raise ValueError("illegal failed state")
        elif outcome is FormulaOutcome.PARTIAL:
            if not has_value:
                raise ValueError("partial result requires a value")
            if self.error is None:
                raise ValueError("partial result requires an error")
            if commit is not FormulaCommitState.PARTIAL or verification is not FormulaVerificationState.FAILED:
                raise ValueError("illegal partial state")
        elif outcome is FormulaOutcome.UNKNOWN:
            if has_value:
                raise ValueError("unknown result must not carry a value")
            if self.error is None:
                raise ValueError("unknown result requires an error")
            if commit is not FormulaCommitState.UNKNOWN or verification is not FormulaVerificationState.UNAVAILABLE:
                raise ValueError("illegal unknown state")
        else:
            if has_value:
                raise ValueError("planned result must not carry a value")
            if self.error is not None:
                raise ValueError("planned result must not carry an error")
            if commit is not FormulaCommitState.NOT_STARTED or verification is not FormulaVerificationState.SKIPPED:
                raise ValueError("illegal planned state")

        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "commit", commit)
        object.__setattr__(self, "verification", verification)
        object.__setattr__(self, "receipts", receipts)


__all__ = [
    "FormulaCommitState",
    "FormulaError",
    "FormulaErrorCode",
    "FormulaExtensionErrorInfo",
    "FormulaExtensionResult",
    "FormulaOutcome",
    "FormulaVerificationState",
]
