"""Lazy CLI provider descriptor discovery."""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import Any

from open_table_connector.contract import CLI_PLUGIN_GROUP


def _descriptor_entries() -> tuple[Any, ...]:
    discovered = entry_points()
    if hasattr(discovered, "select"):
        selected = discovered.select(group=CLI_PLUGIN_GROUP)
    else:  # pragma: no cover
        selected = discovered.get(CLI_PLUGIN_GROUP, ())
    return tuple(sorted(selected, key=lambda item: (item.name, item.value)))


__all__ = ["CLI_PLUGIN_GROUP", "_descriptor_entries"]
