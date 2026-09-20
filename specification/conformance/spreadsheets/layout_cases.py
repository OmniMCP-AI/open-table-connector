"""Shared harness for Excel and recorded MaybeSheet layout conformance."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class LayoutCase:
    provider_name: str
    table_address: str
    client_factory: Callable[[], Any]
    column_sizes: dict[str, dict[str, Any]] = field(default_factory=dict)
    _client: Any = field(default=None, init=False, repr=False)
    _table: Any = field(default=None, init=False, repr=False)
    _layout: Any = field(default=None, init=False, repr=False)

    def open_layout(self):
        if self._layout is not None:
            return self._layout
        self._client = self.client_factory()
        self._table = self._client.open(self.table_address, metadata_only=True).require_value()
        self._layout = self._table.layout()
        return self._layout

    def reopen_layout(self):
        self.close()
        return self.open_layout()

    def corrupt(self, field: str, value: Any):
        corruptor = getattr(self._client, "corrupt_layout", None)
        if not callable(corruptor):
            raise RuntimeError(f"{self.provider_name} does not expose an independent corruptor")
        corruptor(field, value)

    def close(self):
        if self._layout is not None:
            self._layout.close()
        if self._client is not None:
            self._client.close()
        self._layout = self._table = self._client = None


__all__ = ["LayoutCase"]
