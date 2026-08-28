"""Stable, credential-safe Connector errors."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping


class ConnectorErrorCode(StrEnum):
    INVALID_URI = "invalid_uri"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    AUTHENTICATION = "authentication"
    CONFLICT = "conflict"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    EXECUTION_FAILED = "execution_failed"
    READBACK_MISMATCH = "readback_mismatch"


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


def _safe_value(value: Any, *, key: str | None = None) -> Any:
    if key is not None and key.casefold() in _SECRET_KEYS:
        return None
    if isinstance(value, BaseException):
        raise ValueError("safe details cannot contain exception objects")
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for raw_key, item in value.items():
            text_key = str(raw_key)
            safe_item = _safe_value(item, key=text_key)
            if safe_item is not None:
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
        details = _safe_value(self.safe_details)
        object.__setattr__(self, "message", self.message.strip())
        object.__setattr__(self, "safe_details", details)
        RuntimeError.__init__(self, self.message)

    @classmethod
    def authentication(cls, message: str, *, safe_details: Mapping[str, Any] = ()) -> "ConnectorError":
        return cls(ConnectorErrorCode.AUTHENTICATION, message, safe_details)

    def to_wire(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "safe_details": dict(self.safe_details),
        }
