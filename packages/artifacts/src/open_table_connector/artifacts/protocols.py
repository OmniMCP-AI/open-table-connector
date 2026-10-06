from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol

from .model import ViewRequest


class ArtifactAdapter(Protocol):
    def describe(self) -> Mapping[str, object]: ...
    def create_table(self, document_path: Path, rows: Sequence[Sequence[str]], spec: Mapping[str, object]) -> Mapping[str, object]: ...
    def observe_document(self, document_path: Path, selectors: Sequence[Mapping[str, object]]) -> Mapping[str, object]: ...
    def render(self, snapshot_path: Path, request: ViewRequest) -> Mapping[str, object]: ...


__all__ = ["ArtifactAdapter"]
