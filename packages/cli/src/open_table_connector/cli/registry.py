"""Scheme and capability dispatch for the OTC CLI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
from urllib.parse import urlsplit

from open_table_connector.contract import ConnectorError, ConnectorErrorCode

from .adapters import ConnectorAdapter, build_adapters
from .model import Endpoint


@dataclass
class ConnectorRegistry:
    _adapters: list[ConnectorAdapter] = field(default_factory=list)

    def register(self, adapter: ConnectorAdapter) -> None:
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
        scheme = endpoint.uri.scheme
        parsed = urlsplit(endpoint.uri.value)
        scheme_matched = False
        for adapter in self._adapters:
            if scheme not in adapter.schemes:
                continue
            scheme_matched = True
            if scheme == "https":
                host = (parsed.hostname or "").casefold()
                if adapter.identity.connector_id == "google_sheets" and host != "docs.google.com":
                    continue
                if adapter.identity.connector_id == "maybe_sheet" and host != "www.maybe.ai":
                    continue
            return adapter
        if not scheme_matched:
            raise self._unsupported_scheme(endpoint)
        raise self._invalid(endpoint, parsed.hostname)

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


__all__ = ["ConnectorRegistry", "build_default_registry"]
