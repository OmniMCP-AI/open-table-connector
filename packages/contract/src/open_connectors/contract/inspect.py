"""Inspection role for native schema and source facts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

from .capabilities import TableMode
from .coordinates import BaseConvention, SheetConvention
from .resolve import ResourceLimits
from .uri import TableURI


@dataclass(frozen=True)
class InspectRequest:
    uri: TableURI
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)


@dataclass(frozen=True)
class TableInspection:
    safe_uri: TableURI
    mode: TableMode
    columns: tuple[str, ...]
    schema_fingerprint: str
    row_count: int | None
    coordinate_convention: BaseConvention | SheetConvention
    facts: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.mode.value != self.coordinate_convention.mode:
            raise ValueError("inspection mode and coordinate convention disagree")
        if any(not isinstance(column, str) or not column for column in self.columns):
            raise ValueError("inspection columns must be non-empty strings")
        if not isinstance(self.schema_fingerprint, str) or not self.schema_fingerprint.strip():
            raise ValueError("schema_fingerprint must be non-empty")
        if self.row_count is not None and (
            not isinstance(self.row_count, int) or isinstance(self.row_count, bool) or self.row_count < 0
        ):
            raise ValueError("row_count must be a non-negative integer when supplied")
        object.__setattr__(self, "columns", tuple(self.columns))
        object.__setattr__(self, "facts", dict(self.facts))


@runtime_checkable
class TableInspector(Protocol):
    def inspect(self, request: InspectRequest) -> TableInspection: ...

