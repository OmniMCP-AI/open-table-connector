"""Shared public-SDK portable materialization conformance contract."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import polars as pl


@dataclass(frozen=True)
class PortableMaterializationCase:
    """One adapter registration for the portable materialization suite."""

    name: str
    make_client: Callable[[], object]
    read_in_fresh_process: Callable[[object], pl.DataFrame]
    destination: object
    failure_destination: object
    source: pl.DataFrame
    changed_source: pl.DataFrame

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("portable materialization case requires a name")
        if not callable(self.make_client):
            raise TypeError("portable materialization case requires a client factory")
        if not callable(self.read_in_fresh_process):
            raise TypeError("portable materialization case requires a fresh-process reader")
        if not isinstance(self.source, pl.DataFrame) or not isinstance(self.changed_source, pl.DataFrame):
            raise TypeError("portable materialization cases require polars DataFrames")


PortableMaterializationCaseFactory = Callable[[Path], PortableMaterializationCase]
_CASE_FACTORIES: list[PortableMaterializationCaseFactory] = []


def register_portable_materialization_case(
    factory: PortableMaterializationCaseFactory,
) -> PortableMaterializationCaseFactory:
    """Register one adapter case factory for the public-SDK materialization suite."""

    if not callable(factory):
        raise TypeError("portable materialization case factory must be callable")
    _CASE_FACTORIES.append(factory)
    return factory


def portable_materialization_cases(root: Path) -> tuple[PortableMaterializationCase, ...]:
    """Create all registered cases against isolated persisted destinations."""

    return tuple(factory(root) for factory in _CASE_FACTORIES)
