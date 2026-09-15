"""Provider seam used by the SDK without importing provider implementations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Protocol, runtime_checkable

from ._operations import Change
from .model import SpreadsheetTarget


@runtime_checkable
class SpreadsheetProvider(Protocol):
    def bind(self, target: SpreadsheetTarget) -> Mapping[str, Any]: ...

    def preflight(self, binding: Mapping[str, Any], changes: Iterable[Change]) -> Mapping[str, Any]: ...

    def commit(
        self,
        binding: Mapping[str, Any],
        changes: Iterable[Change],
        *,
        allow_partial: bool,
        expected_revision: str | None,
        idempotency_key: str | None,
    ) -> Mapping[str, Any]: ...

    def observe(self, binding: Mapping[str, Any], selector: Mapping[str, Any]) -> Mapping[str, Any]: ...


__all__ = ["SpreadsheetProvider"]
