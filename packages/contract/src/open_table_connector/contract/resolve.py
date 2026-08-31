"""URI resolver role and its small context models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .capabilities import TableMode
from .uri import TableURI


@dataclass(frozen=True)
class ResourceLimits:
    max_rows: int | None = None
    max_bytes: int | None = None
    timeout_seconds: int | None = None

    def __post_init__(self) -> None:
        for name in ("max_rows", "max_bytes", "timeout_seconds"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 1
            ):
                raise ValueError(f"{name} must be a positive integer when supplied")


@dataclass(frozen=True)
class ResolveContext:
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    credentials: Any = field(default=None, repr=False)


@dataclass(frozen=True)
class ResolvedTable:
    uri: TableURI
    mode: TableMode
    resource: Any


@runtime_checkable
class URIResolver(Protocol):
    def resolve(self, uri: TableURI, context: ResolveContext) -> ResolvedTable: ...
