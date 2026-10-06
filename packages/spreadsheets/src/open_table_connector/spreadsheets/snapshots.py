"""Immutable source snapshot metadata for presentation adapters."""

from __future__ import annotations

from dataclasses import dataclass

from open_table_connector.contract import TargetSelector


@dataclass(frozen=True, slots=True)
class WorkbookSnapshot:
    uri: str
    source: TargetSelector
    content_hash: str
    captured_at: str
    provider_revision: str | None
    consistency: str

    def __post_init__(self) -> None:
        if self.consistency not in {"revision_bound", "revision_unavailable"}:
            raise ValueError("unsupported snapshot consistency")


__all__ = ["WorkbookSnapshot"]
