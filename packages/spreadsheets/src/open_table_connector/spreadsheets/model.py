"""Validated wire models shared by spreadsheet provider adapters."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

_A1 = re.compile(r"^([A-Z]{1,3})([1-9][0-9]*)$")
_RANGE = re.compile(r"^([A-Z]{1,3}[1-9][0-9]*)(?::([A-Z]{1,3}[1-9][0-9]*))?$")
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _closed(payload: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(payload) != expected:
        raise ValueError(f"{label} wire keys mismatch")


def _column_number(value: str) -> int:
    result = 0
    for char in value:
        result = result * 26 + ord(char) - ord("A") + 1
    return result


def _coordinate(value: str) -> tuple[int, int]:
    match = _A1.fullmatch(value)
    if match is None:
        raise ValueError("coordinate must be an uppercase A1 cell")
    column = _column_number(match.group(1))
    row = int(match.group(2))
    if column > 16_384 or row > 1_048_576:
        raise ValueError("coordinate is outside the Excel worksheet bounds")
    return row, column


@dataclass(frozen=True, slots=True)
class SpreadsheetTarget:
    """Canonical workbook URI; local Excel uses standard ``file://`` URIs."""

    uri: str

    def __post_init__(self) -> None:
        value = _text(self.uri, "uri")
        if value.startswith("file://"):
            if not value.startswith("file:///"):
                raise ValueError("file URI must use an absolute path")
        elif "://" not in value:
            raise ValueError("spreadsheet target must be a URI")
        object.__setattr__(self, "uri", value)

    def to_wire(self) -> dict[str, str]:
        return {"uri": self.uri}

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> SpreadsheetTarget:
        _closed(payload, {"uri"}, "SpreadsheetTarget")
        return cls(payload["uri"])


@dataclass(frozen=True, slots=True)
class WorksheetRef:
    name: str | None = None
    worksheet_id: str | None = None

    def __post_init__(self) -> None:
        if self.name is None and self.worksheet_id is None:
            raise ValueError("worksheet reference requires name or worksheet_id")
        for field_name in ("name", "worksheet_id"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _text(value, field_name))

    def to_wire(self) -> dict[str, str | None]:
        return {"name": self.name, "worksheet_id": self.worksheet_id}


@dataclass(frozen=True, slots=True)
class RangeRef:
    address: str

    def __post_init__(self) -> None:
        value = _text(self.address, "address").upper()
        match = _RANGE.fullmatch(value)
        if match is None:
            raise ValueError("range must be a finite A1 rectangle")
        start = match.group(1)
        end = match.group(2) or start
        start_row, start_column = _coordinate(start)
        end_row, end_column = _coordinate(end)
        if (end_row, end_column) < (start_row, start_column):
            raise ValueError("range end must not precede its start")
        object.__setattr__(self, "address", value)

    def to_wire(self) -> dict[str, str]:
        return {"address": self.address}


@dataclass(frozen=True, slots=True)
class CellFormat:
    kind: str
    pattern: str | None = None

    def __post_init__(self) -> None:
        kind = _text(self.kind, "kind").casefold()
        if kind not in {"text", "general", "number", "percent", "currency", "date_time", "native"}:
            raise ValueError("unsupported cell format kind")
        if kind == "native" and not self.pattern:
            raise ValueError("native cell format requires pattern")
        object.__setattr__(self, "kind", kind)
        if self.pattern is not None:
            object.__setattr__(self, "pattern", _text(self.pattern, "pattern"))


@dataclass(frozen=True, slots=True)
class CellStyle:
    font_size: float | None = None
    bold: bool | None = None
    italic: bool | None = None
    foreground: str | None = None
    fill: str | None = None

    def __post_init__(self) -> None:
        if self.font_size is not None and (
            isinstance(self.font_size, bool)
            or not isinstance(self.font_size, (int, float))
            or not math.isfinite(self.font_size)
            or self.font_size <= 0
        ):
            raise ValueError("font_size must be positive")
        for field_name in ("bold", "italic"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, bool):
                raise ValueError(f"{field_name} must be a boolean")
        for field_name in ("foreground", "fill"):
            value = getattr(self, field_name)
            if value is not None and not _HEX.fullmatch(value):
                raise ValueError(f"{field_name} must be #RRGGBB")


@dataclass(frozen=True, slots=True)
class ImageSpec:
    mime_type: str
    content: bytes
    anchor: str
    sha256: str = field(init=False)

    def __post_init__(self) -> None:
        mime = _text(self.mime_type, "mime_type").casefold()
        if mime not in {"image/png", "image/jpeg"}:
            raise ValueError("image MIME type must be image/png or image/jpeg")
        if not isinstance(self.content, bytes) or not self.content:
            raise ValueError("image content must be non-empty bytes")
        anchor = _text(self.anchor, "anchor").upper()
        if _A1.fullmatch(anchor) is None:
            raise ValueError("image anchor must be one A1 cell")
        object.__setattr__(self, "mime_type", mime)
        object.__setattr__(self, "anchor", anchor)
        object.__setattr__(self, "sha256", hashlib.sha256(self.content).hexdigest())

    def to_wire(self) -> dict[str, Any]:
        return {"mime_type": self.mime_type, "sha256": self.sha256, "anchor": self.anchor, "byte_count": len(self.content)}


__all__ = ["CellFormat", "CellStyle", "ImageSpec", "RangeRef", "SpreadsheetTarget", "WorksheetRef"]
