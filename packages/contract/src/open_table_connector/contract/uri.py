"""Credential-free universal table URI value."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from .names import SCHEME_FILE

_SECRET_QUERY_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "credential",
    "password",
    "secret",
    "token",
}


def _secret_parameter_keys(text: str) -> set[str]:
    return {
        key.casefold()
        for key, _value in parse_qsl(text, keep_blank_values=True)
        if key.casefold() in _SECRET_QUERY_KEYS
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
        if _secret_parameter_keys(parsed.query) or _secret_parameter_keys(parsed.fragment):
            raise ValueError("TableURI cannot contain credential query parameters")
        if parsed.scheme.casefold() == SCHEME_FILE and not parsed.path.startswith("/"):
            raise ValueError("file TableURI must use an absolute path")
        object.__setattr__(self, "value", value)

    @property
    def scheme(self) -> str:
        return urlsplit(self.value).scheme.casefold()

    def to_wire(self) -> dict[str, str]:
        return {"value": self.value}

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> TableURI:
        if set(payload) != {"value"}:
            raise ValueError("TableURI wire object must contain only value")
        return cls(payload["value"])
