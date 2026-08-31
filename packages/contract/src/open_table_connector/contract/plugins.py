"""Provider-neutral plugin registration primitives."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeAlias

from .identity import ConnectorIdentity
from .names import SCHEME_HTTPS

PluginFactory: TypeAlias = Callable[..., Any]


def _normalise_tokens(values: tuple[str, ...], label: str) -> tuple[str, ...]:
    result = tuple(value.strip().casefold() for value in values)
    if any(not value for value in result):
        raise ValueError(f"{label} must contain only non-empty strings")
    if len(set(result)) != len(result):
        raise ValueError(f"{label} must not contain duplicates")
    return result


@dataclass(frozen=True)
class PluginDescriptor:
    """A zero-I/O registration record consumed by a host application."""

    name: str
    identity: ConnectorIdentity
    schemes: tuple[str, ...]
    factory: PluginFactory = field(repr=False, compare=False)
    hosts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("plugin name must be a non-empty string")
        if not isinstance(self.identity, ConnectorIdentity):
            raise TypeError("plugin identity must be a ConnectorIdentity")
        if not callable(self.factory):
            raise TypeError("plugin factory must be callable")
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "schemes", _normalise_tokens(self.schemes, "plugin schemes"))
        object.__setattr__(self, "hosts", _normalise_tokens(self.hosts, "plugin hosts"))
        if not self.schemes:
            raise ValueError("plugin schemes must not be empty")
        if self.hosts and SCHEME_HTTPS not in self.schemes:
            raise ValueError("plugin hosts are only valid for https routes")

    def route_keys(self) -> tuple[tuple[str, str | None], ...]:
        """Return canonical `(scheme, host)` keys used for collision checks."""

        keys: list[tuple[str, str | None]] = []
        for scheme in self.schemes:
            hosts = self.hosts if scheme == SCHEME_HTTPS and self.hosts else (None,)
            keys.extend((scheme, host) for host in hosts)
        return tuple(keys)


__all__ = ["PluginDescriptor", "PluginFactory"]
