"""Credential-free universal table URI value."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlsplit


_SECRET_QUERY_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "credential",
    "password",
    "secret",
    "token",
}


@dataclass(frozen=True)
class TableURI:
    """A safe address; vendor-specific fields remain opaque to the contract."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise ValueError("TableURI value must be a non-empty absolute URI")
        value = self.value.strip()
        parsed = urlsplit(value)
        if not parsed.scheme:
            raise ValueError("TableURI value must be an absolute URI")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("TableURI cannot contain credentials")
        if any(key.casefold() in _SECRET_QUERY_KEYS for key, _ in parse_qsl(parsed.query)):
            raise ValueError("TableURI cannot contain credential query parameters")
        if parsed.scheme.casefold() == "file" and not parsed.path.startswith("/"):
            raise ValueError("file TableURI must use an absolute path")
        object.__setattr__(self, "value", value)

    @property
    def scheme(self) -> str:
        return urlsplit(self.value).scheme.casefold()

    def to_wire(self) -> dict[str, str]:
        return {"value": self.value}

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> "TableURI":
        if set(payload) != {"value"}:
            raise ValueError("TableURI wire object must contain only value")
        return cls(payload["value"])
