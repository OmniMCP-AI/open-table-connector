"""Stable, credential-safe Connector errors."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ConnectorErrorCode(StrEnum):
    INVALID_URI = "invalid_uri"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    AUTHENTICATION = "authentication"
    CONFLICT = "conflict"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    EXECUTION_FAILED = "execution_failed"
    READBACK_MISMATCH = "readback_mismatch"
    PROTOCOL_INVALID = "protocol_invalid"
    PROTOCOL_VERSION_UNSUPPORTED = "protocol_version_unsupported"
    RESOURCE_LIMIT_EXCEEDED = "resource_limit_exceeded"
    SNAPSHOT_UNAVAILABLE = "snapshot_unavailable"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    VISIBILITY_INCOMPLETE = "visibility_incomplete"
    CONFIGURATION = "configuration"


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
_REDACTED = object()


def _safe_value(value: Any, *, key: str | None = None) -> Any:
    if key is not None and key.casefold() in _SECRET_KEYS:
        return _REDACTED
    if isinstance(value, BaseException):
        raise ValueError("safe details cannot contain exception objects")
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for raw_key, item in value.items():
            text_key = str(raw_key)
            if text_key.casefold() in _SECRET_KEYS:
                continue
            safe_item = _safe_value(item, key=text_key)
            if safe_item is not _REDACTED:
                result[text_key] = safe_item
        return result
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError("safe details must contain JSON scalar, sequence, or mapping values")


@dataclass
class ConnectorError(RuntimeError):
    code: ConnectorErrorCode
    message: str
    safe_details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.code, ConnectorErrorCode):
            raise TypeError("code must be a ConnectorErrorCode")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("message must be a non-empty string")
        details = _safe_value({} if self.safe_details is None else self.safe_details)
        object.__setattr__(self, "message", self.message.strip())
        object.__setattr__(self, "safe_details", details)
        RuntimeError.__init__(self, self.message)

    @classmethod
    def authentication(
        cls, message: str, *, safe_details: Mapping[str, Any] | None = None
    ) -> ConnectorError:
        return cls(ConnectorErrorCode.AUTHENTICATION, message, safe_details)

    @classmethod
    def configuration(
        cls, message: str, *, safe_details: Mapping[str, Any] | None = None
    ) -> ConnectorError:
        return cls(ConnectorErrorCode.CONFIGURATION, message, safe_details)

    def to_wire(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "safe_details": dict(self.safe_details),
        }
