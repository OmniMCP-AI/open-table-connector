"""Shared public-SDK portable materialization conformance contract."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import polars as pl


@dataclass(frozen=True)
class PortableMaterializationCase:
    """One adapter registration for the portable materialization suite."""

    name: str
    make_clients: Callable[[], tuple[object, object]]
    read_in_fresh_process: Callable[[object], pl.DataFrame]
    destination: object
    source: pl.DataFrame
    changed_source: pl.DataFrame

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("portable materialization case requires a name")
        if not callable(self.make_clients):
            raise TypeError("portable materialization case requires a client factory")
        if not callable(self.read_in_fresh_process):
            raise TypeError("portable materialization case requires a fresh-process reader")
        if not isinstance(self.source, pl.DataFrame) or not isinstance(self.changed_source, pl.DataFrame):
            raise TypeError("portable materialization cases require polars DataFrames")
