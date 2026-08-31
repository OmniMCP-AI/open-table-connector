"""Compatibility facade; concrete adapters live in provider packages."""

from collections.abc import Mapping
from typing import Any

from .plugins import _descriptor_entries


def build_adapters(
    env: Mapping[str, str] | None = None,
    transports: Mapping[str, Any] | None = None,
) -> tuple[Any, ...]:
    """Preserve the old import without reintroducing CLI adapter ownership."""

    del env, transports
    if not _descriptor_entries():
        return ()
    from .registry import build_default_registry

    return tuple(build_default_registry().list())


__all__ = ["build_adapters"]
