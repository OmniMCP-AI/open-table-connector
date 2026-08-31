"""Scheme and capability dispatch for the OTC CLI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
from urllib.parse import urlsplit

from open_table_connector.contract import ConnectorError, ConnectorErrorCode

from .adapters import ConnectorAdapter, build_adapters
from .model import Endpoint


@dataclass(frozen=True)
class Route:
    scheme: str
    host: str | None
    adapter_id: str


@dataclass
class ConnectorRegistry:
    _adapters: list[ConnectorAdapter] = field(default_factory=list)
    _routes: dict[tuple[str, str | None], ConnectorAdapter] = field(default_factory=dict)

    def __post_init__(self) -> None:
        initial = tuple(self._adapters)
        self._adapters = []
        self._routes = {}
        for adapter in initial:
            self.register(adapter)

    def register(self, adapter: ConnectorAdapter) -> None:
        hosts = tuple(getattr(adapter, "hosts", ()))
        for scheme in adapter.schemes:
            route_hosts = hosts if scheme == "https" and hosts else (None,)
            for host in route_hosts:
                key = (scheme.casefold(), host.casefold() if host else None)
                if key in self._routes:
                    raise ConnectorError(
                        ConnectorErrorCode.CONFLICT,
                        "connector route is already registered",
                        {"scheme": key[0], **({"host": key[1]} if key[1] else {})},
                    )
        for scheme in adapter.schemes:
            route_hosts = hosts if scheme == "https" and hosts else (None,)
            for host in route_hosts:
                key = (scheme.casefold(), host.casefold() if host else None)
                self._routes[key] = adapter
        self._adapters.append(adapter)

    def list(self) -> tuple[ConnectorAdapter, ...]:
        return tuple(self._adapters)

    def connector_for(self, endpoint: Endpoint) -> ConnectorAdapter:
        if endpoint.is_stdio or endpoint.path is not None:
            for adapter in self._adapters:
                if "file" in adapter.schemes:
                    return adapter
            raise self._invalid(endpoint, None)
        assert endpoint.uri is not None
        scheme = endpoint.uri.scheme.casefold()
        parsed = urlsplit(endpoint.uri.value)
        host = (parsed.hostname or "").casefold() if scheme == "https" else None
        adapter = self._routes.get((scheme, host)) or self._routes.get((scheme, None))
        if adapter is not None:
            return adapter
        if not any(scheme in {item.casefold() for item in candidate.schemes} for candidate in self._adapters):
            raise self._unsupported_scheme(endpoint)
        raise self._invalid(endpoint, host)

    def require_capability(self, endpoint: Endpoint, capability_id: str) -> ConnectorAdapter:
        adapter = self.connector_for(endpoint)
        if capability_id not in {capability.capability_id for capability in adapter.capabilities}:
            raise ConnectorError(ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                                 "connector does not support the requested capability",
                                 {"scheme": endpoint.uri.scheme if endpoint.uri else "file", "capability": capability_id})
        return adapter

    @staticmethod
    def _invalid(endpoint: Endpoint, host: str | None) -> ConnectorError:
        details = {"scheme": endpoint.uri.scheme if endpoint.uri else "file"}
        if host:
            details["host"] = host
        return ConnectorError(ConnectorErrorCode.INVALID_URI, "no connector supports this endpoint", details)

    @staticmethod
    def _unsupported_scheme(endpoint: Endpoint) -> ConnectorError:
        scheme = endpoint.uri.scheme if endpoint.uri else "file"
        return ConnectorError(
            ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
            "no connector advertises this endpoint scheme",
            {"scheme": scheme},
        )


def build_default_registry(env: Mapping[str, str] | None = None, transports: Mapping[str, Any] | None = None) -> ConnectorRegistry:
    registry = ConnectorRegistry()
    for adapter in build_adapters(dict(env or {}), transports):
        registry.register(adapter)
    return registry


__all__ = ["ConnectorRegistry", "Route", "build_default_registry"]
