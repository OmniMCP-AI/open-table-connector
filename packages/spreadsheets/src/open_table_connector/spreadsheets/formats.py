"""Excel number-format request normalization.

This module validates transport shape and preserves exact format codes. It does
not render values or claim that a provider's format engine supports a dialect.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

JSON = dict[str, Any]

_DEFAULT_CODES = {
    "general": "General",
    "text": "@",
    "number": "0.00",
    "percent": "0.00%",
    "date": "yyyy-mm-dd",
    "time": "hh:mm:ss",
    "date_time": "yyyy-mm-dd hh:mm:ss",
    "duration": "[h]:mm:ss",
    "fraction": "# ?/?",
    "scientific": "0.00E+00",
}
_KINDS = set(_DEFAULT_CODES) | {"currency", "accounting", "special", "custom", "native"}


def _formats_descriptor(descriptor: Mapping[str, Any]) -> Mapping[str, Any]:
    formats = descriptor.get("formats")
    if not isinstance(formats, Mapping):
        raise ValueError("descriptor requires formats")
    required = {"dialect", "version", "locales", "builtins", "custom_code", "unsupported_features"}
    if not required <= set(formats):
        raise ValueError("format descriptor is incomplete")
    if not isinstance(formats["locales"], (list, tuple)):
        raise ValueError("format descriptor locales must be an array")
    return formats


def normalize_format(arguments: Mapping[str, Any], *, descriptor: Mapping[str, Any]) -> JSON:
    if not isinstance(arguments, Mapping):
        raise ValueError("format arguments must be an object")
    formats = _formats_descriptor(descriptor)
    allowed = {"kind", "pattern", "builtin_id", "locale", "date_system", "storage_kind"}
    unknown = set(arguments) - allowed
    if unknown:
        raise ValueError(f"unsupported format arguments: {sorted(unknown)}")
    kind = arguments.get("kind")
    if kind is not None:
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError("format kind must be a non-empty string")
        kind = kind.casefold()
        if kind not in _KINDS:
            raise ValueError(f"unsupported format kind: {kind}")
    pattern = arguments.get("pattern")
    if pattern is not None and (not isinstance(pattern, str) or not pattern):
        raise ValueError("format pattern must be a non-empty string")
    builtin_id = arguments.get("builtin_id")
    if builtin_id is not None and (isinstance(builtin_id, bool) or not isinstance(builtin_id, int) or builtin_id < 0):
        raise ValueError("builtin_id must be a non-negative integer")
    if builtin_id is not None and (kind is not None or pattern is not None):
        raise ValueError("builtin_id is mutually exclusive with kind and pattern")
    if kind is None and builtin_id is None:
        raise ValueError("kind, pattern, or builtin_id is required")
    if kind in {"currency", "accounting", "special", "custom", "native"} and pattern is None:
        raise ValueError(f"{kind} requires pattern")
    locale = arguments.get("locale")
    if locale is not None and (not isinstance(locale, str) or not locale):
        raise ValueError("locale must be a non-empty string")
    if locale is not None and locale not in formats["locales"]:
        raise ValueError(f"unsupported locale: {locale}")
    if builtin_id is not None and locale is None:
        raise ValueError("locale is required for builtin_id")
    date_system = arguments.get("date_system")
    if date_system is not None and date_system not in {"1900", "1904"}:
        raise ValueError("date_system must be 1900 or 1904")
    if builtin_id is not None:
        builtins = formats["builtins"]
        metadata = builtins.get(str(builtin_id)) or builtins.get(builtin_id)
        if not isinstance(metadata, Mapping):
            raise ValueError(f"unsupported builtin format id: {builtin_id}")
        if locale not in metadata.get("locales", formats["locales"]):
            raise ValueError("builtin format is unavailable for locale")
        return {
            "kind": None,
            "code": metadata.get("code"),
            "builtin_id": builtin_id,
            "locale": locale,
            "date_system": date_system,
            "storage_kind": "builtin",
        }
    if pattern is not None and not formats["custom_code"]:
        raise ValueError("custom format codes are unsupported by this descriptor")
    return {
        "kind": kind,
        "code": pattern if pattern is not None else _DEFAULT_CODES[kind],
        "builtin_id": None,
        "locale": locale,
        "date_system": date_system,
        "storage_kind": "custom" if pattern is not None else "provider",
    }

