"""Descriptor routing and lazy connector activation for the SDK."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from importlib.metadata import EntryPoint, entry_points
from typing import Any
from urllib.parse import urlsplit

from open_table_connector.contract import (
    CLI_PLUGIN_GROUP,
    ConnectorAdapter,
    PluginDescriptor,
    ProviderConfig,
    ProviderFactoryContext,
    parse_adapter_endpoint,
)

from .config import ClientConfig
from .connector import LegacyConnectorAdapterBridge, TableConnector, _sdk_mode_to_legacy
from .credentials import CredentialLease, CredentialResolver
from .result import ErrorCode, ErrorInfo, OperationResult, OTCError


def _registry_error(code: ErrorCode, message: str, **details: object) -> OTCError:
    result = OperationResult[None](
        value=None,
        outcome="rejected",
        commit="not_started",
        verification="skipped",
        receipts=(),
        error=ErrorInfo(code=code, message=message, safe_details=details),
    )
    return OTCError(message, result)


@dataclass(frozen=True, slots=True)
class ConfiguredPlugin:
    descriptor: PluginDescriptor
    config: ProviderConfig


def discover_configured_plugins(
    config: ClientConfig,
    *,
    entries: Iterable[EntryPoint] | None = None,
) -> tuple[ConfiguredPlugin, ...]:
    discovered = entry_points() if entries is None else tuple(entries)
    if hasattr(discovered, "select"):
        selected = discovered.select(group=CLI_PLUGIN_GROUP)
    else:
        selected = discovered
    configured: list[ConfiguredPlugin] = []
    seen_ids: set[str] = set()
    for entry in sorted(selected, key=lambda item: (item.name, item.value)):
        loaded = entry.load()
        descriptor = loaded() if callable(loaded) else loaded
        if not isinstance(descriptor, PluginDescriptor):
            raise _registry_error(
                ErrorCode.INVALID_CONFIGURATION,
                "plugin entry point did not return PluginDescriptor",
            )
        provider_id = descriptor.identity.connector_id
        if provider_id in seen_ids:
            raise _registry_error(
                ErrorCode.INVALID_CONFIGURATION,
                "duplicate SDK provider descriptor",
                provider_id=provider_id,
            )
        seen_ids.add(provider_id)
        provider_config = config.providers.get(provider_id, ProviderConfig(provider_id))
        if provider_config.enabled:
            configured.append(ConfiguredPlugin(descriptor, provider_config))
    return tuple(sorted(configured, key=lambda item: item.descriptor.name))


@dataclass
class ConnectorRegistry:
    _resolver: CredentialResolver | None = field(default=None, repr=False)
    _environ: Mapping[str, str] = field(default_factory=dict, repr=False)
    _transports: Mapping[str, Any] = field(default_factory=dict, repr=False)
    _descriptors: dict[tuple[str, str | None], PluginDescriptor] = field(
        default_factory=dict, init=False, repr=False
    )
    _plugins: dict[str, ConfiguredPlugin] = field(default_factory=dict, init=False, repr=False)
    _connectors: dict[str, TableConnector] = field(default_factory=dict, init=False, repr=False)
    _path_connector_id: str | None = field(default=None, init=False, repr=False)

    def __init__(
        self,
        connectors: Iterable[TableConnector] | None = None,
        *,
        resolver: CredentialResolver | None = None,
        environ: Mapping[str, str] | None = None,
        transports: Mapping[str, Any] | None = None,
    ) -> None:
        self._resolver = resolver
        self._environ = {} if environ is None else dict(environ)
        self._transports = {} if transports is None else dict(transports)
        self._descriptors = {}
        self._plugins = {}
        self._connectors = {}
        self._path_connector_id = None
        for connector in () if connectors is None else connectors:
            self.register(connector)

    @classmethod
    def from_descriptors(
        cls,
        descriptors: Iterable[PluginDescriptor],
        config: ClientConfig,
        *,
        resolver: CredentialResolver | None = None,
        environ: Mapping[str, str] | None = None,
        transports: Mapping[str, Any] | None = None,
    ) -> ConnectorRegistry:
        registry = cls(resolver=resolver, environ=environ, transports=transports)
        for descriptor in sorted(descriptors, key=lambda item: item.name):
            provider_id = descriptor.identity.connector_id
            provider_config = config.providers.get(provider_id, ProviderConfig(provider_id))
            if not provider_config.enabled:
                continue
            registry._register_plugin(ConfiguredPlugin(descriptor, provider_config))
        return registry

    def register(self, connector: TableConnector) -> None:
        descriptor = self._descriptor_for_connector(connector)
        provider_id = descriptor.identity.connector_id
        self._plugins[provider_id] = ConfiguredPlugin(descriptor, ProviderConfig(provider_id))
        self._connectors[provider_id] = connector
        self._register_routes(descriptor)

    def _register_plugin(self, plugin: ConfiguredPlugin) -> None:
        provider_id = plugin.descriptor.identity.connector_id
        if provider_id in self._plugins:
            raise _registry_error(
                ErrorCode.INVALID_CONFIGURATION,
                "duplicate SDK provider descriptor",
                provider_id=provider_id,
            )
        self._plugins[provider_id] = plugin
        self._register_routes(plugin.descriptor)

    def _register_routes(self, descriptor: PluginDescriptor) -> None:
        for route_key in descriptor.route_keys():
            if route_key in self._descriptors:
                raise _registry_error(
                    ErrorCode.KEY_CONFLICT,
                    "connector route is already registered",
                    scheme=route_key[0],
                    host=route_key[1],
                )
            self._descriptors[route_key] = descriptor
        if descriptor.handles_paths:
            if self._path_connector_id is not None:
                raise _registry_error(
                    ErrorCode.KEY_CONFLICT, "multiple connectors handle path endpoints"
                )
            self._path_connector_id = descriptor.identity.connector_id

    def list(self) -> tuple[PluginDescriptor, ...]:
        return tuple(
            sorted(
                (plugin.descriptor for plugin in self._plugins.values()), key=lambda item: item.name
            )
        )

    def descriptor_for(self, target: str | object) -> PluginDescriptor:
        return self._plugin_for(target).descriptor

    def connector_for(self, target: str | object) -> TableConnector:
        plugin = self._plugin_for(target)
        provider_id = plugin.descriptor.identity.connector_id
        if provider_id in self._connectors:
            return self._connectors[provider_id]
        context, lease = self._provider_context(plugin.config)
        try:
            connector = plugin.descriptor.factory(context)
        finally:
            if lease is not None:
                lease.dispose()
        if isinstance(connector, ConnectorAdapter):
            wrapped = LegacyConnectorAdapterBridge(connector)
        else:
            wrapped = connector
        self._connectors[provider_id] = wrapped
        return wrapped

    def close(self) -> None:
        for connector in list(self._connectors.values()):
            close = getattr(connector, "close", None)
            if callable(close):
                close()
        self._connectors.clear()

    def _plugin_for(self, target: str | object) -> ConfiguredPlugin:
        endpoint = parse_adapter_endpoint(
            target if isinstance(target, str) else self._route_key_value(target)
        )
        if endpoint.is_stdio or endpoint.path is not None:
            if self._path_connector_id is None:
                raise _registry_error(
                    ErrorCode.UNSUPPORTED_CAPABILITY, "no connector handles path endpoints"
                )
            return self._plugins[self._path_connector_id]
        assert endpoint.uri is not None
        scheme = endpoint.uri.scheme.casefold()
        parsed = urlsplit(endpoint.uri.value)
        host = parsed.hostname.casefold() if scheme == "https" and parsed.hostname else None
        descriptor = self._descriptors.get((scheme, host)) or self._descriptors.get((scheme, None))
        if descriptor is None:
            raise _registry_error(
                ErrorCode.UNSUPPORTED_CAPABILITY,
                "no connector advertises this endpoint scheme",
                scheme=scheme,
                host=host,
            )
        return self._plugins[descriptor.identity.connector_id]

    @staticmethod
    def _descriptor_for_connector(connector: TableConnector) -> PluginDescriptor:
        return PluginDescriptor(
            name=connector.identity.connector_id,
            identity=connector.identity,
            schemes=tuple(connector.schemes),
            factory=lambda _context, instance=connector: instance,
            hosts=tuple(getattr(connector, "hosts", ())),
            capabilities=tuple(getattr(connector, "capabilities", ())),
            modes=tuple(_sdk_mode_to_legacy(mode) for mode in getattr(connector, "modes", ())),
            local=bool(getattr(connector, "local", False)),
            handles_paths=bool(getattr(connector, "handles_paths", False)),
        )

    @staticmethod
    def _route_key_value(target: object) -> str:
        for attribute in ("uri", "database", "container", "grid"):
            value = getattr(target, attribute, None)
            if value is not None:
                return value.value
        raise TypeError("target is not routable")

    def _provider_environment(self, config: ProviderConfig) -> Mapping[str, str]:
        environment: dict[str, str] = {}
        for logical_name, environment_name in config.environment.items():
            value = self._environ.get(environment_name)
            if value is None:
                raise _registry_error(
                    ErrorCode.INVALID_CONFIGURATION,
                    "provider environment binding is missing",
                    provider_id=config.provider_id,
                    field=logical_name,
                    environment=environment_name,
                )
            environment[logical_name] = value
        return environment

    def _provider_context(
        self, config: ProviderConfig
    ) -> tuple[ProviderFactoryContext, CredentialLease | None]:
        credentials: Mapping[str, str] = {}
        lease = None
        if self._resolver is not None:
            lease = self._resolver.resolve(config)
            credentials = lease.values
        return (
            ProviderFactoryContext(
                config=config,
                environment=self._provider_environment(config),
                credentials=credentials,
                transports=self._provider_transports(config),
            ),
            lease,
        )

    def _provider_transports(self, config: ProviderConfig) -> Mapping[str, Any]:
        selected = self._transports.get(config.provider_id)
        return {} if selected is None else {config.provider_id: selected}


__all__ = ["ConfiguredPlugin", "ConnectorRegistry", "discover_configured_plugins"]
