"""Descriptor routing and lazy activation for configured CLI providers."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from importlib.metadata import EntryPoint
from typing import Any
from urllib.parse import urlsplit

from open_table_connector.contract import (
    SCHEME_FILE,
    SCHEME_HTTPS,
    AdapterEndpoint,
    ConnectorAdapter,
    ConnectorError,
    ConnectorErrorCode,
    PluginDescriptor,
    ProviderConfig,
    ProviderFactoryContext,
    TableURI,
)

from .configuration import CliConfig
from .credentials import CredentialResolver
from .plugins import _descriptor_entries


@dataclass(frozen=True)
class ConfiguredPlugin:
    descriptor: PluginDescriptor
    config: ProviderConfig


class _LazyAdapter:
    """Descriptor-backed adapter that activates a provider for each operation."""

    def __init__(self, registry: ConfiguredConnectorRegistry, plugin: ConfiguredPlugin) -> None:
        self._registry = registry
        self._plugin = plugin
        descriptor = plugin.descriptor
        self.identity = descriptor.identity
        self.schemes = descriptor.schemes
        self.hosts = descriptor.hosts
        self.capabilities = descriptor.capabilities
        self.modes = descriptor.modes
        self.local = descriptor.local
        self.handles_paths = descriptor.handles_paths

    def read(self, endpoint: AdapterEndpoint, options):
        with self._registry.open_adapter(endpoint) as adapter:
            return adapter.read(endpoint, options)

    def inspect(self, endpoint: AdapterEndpoint, options):
        with self._registry.open_adapter(endpoint) as adapter:
            return adapter.inspect(endpoint, options)

    def write(self, endpoint: AdapterEndpoint, table, options):
        with self._registry.open_adapter(endpoint) as adapter:
            return adapter.write(endpoint, table, options)

    def preflight_write(self, endpoint: AdapterEndpoint, options) -> None:
        with self._registry.open_adapter(endpoint) as adapter:
            preflight = getattr(adapter, "preflight_write", None)
            if callable(preflight):
                preflight(endpoint, options)


def discover_configured_plugins(
    config: CliConfig,
    *,
    entries: Iterable[EntryPoint] | None = None,
) -> tuple[ConfiguredPlugin, ...]:
    selected_entries = _descriptor_entries() if entries is None else tuple(entries)
    discovered: list[ConfiguredPlugin] = []
    seen_ids: set[str] = set()
    for entry in sorted(selected_entries, key=lambda item: (item.name, item.value)):
        try:
            loaded = entry.load()
            descriptor = loaded() if callable(loaded) else loaded
            if not isinstance(descriptor, PluginDescriptor):
                raise TypeError("CLI plugin entry point must return PluginDescriptor")
        except ConnectorError:
            raise
        except Exception as exc:
            raise ConnectorError.configuration(
                "CLI provider descriptor could not be loaded",
                safe_details={"entry_point": entry.name},
            ) from exc
        provider_id = descriptor.identity.connector_id
        if provider_id in seen_ids:
            raise ConnectorError.configuration(
                "duplicate CLI provider descriptor",
                safe_details={"provider_id": provider_id},
            )
        seen_ids.add(provider_id)
        provider_config = config.providers.get(provider_id, ProviderConfig(provider_id))
        if provider_config.enabled:
            discovered.append(ConfiguredPlugin(descriptor, provider_config))
    return tuple(sorted(discovered, key=lambda item: item.descriptor.name))


@dataclass
class ConfiguredConnectorRegistry:
    _plugins: list[ConfiguredPlugin] = field(default_factory=list)
    _resolver: CredentialResolver | None = field(default=None, repr=False)
    _environ: Mapping[str, str] = field(default_factory=dict, repr=False)
    _transports: Mapping[str, Any] = field(default_factory=dict, repr=False)
    _routes: dict[tuple[str, str | None], ConfiguredPlugin] = field(
        default_factory=dict, init=False, repr=False
    )
    _path_plugin: ConfiguredPlugin | None = field(default=None, init=False, repr=False)
    _diagnostics: tuple[str, ...] = field(default=(), init=False)

    @classmethod
    def from_descriptors(
        cls,
        descriptors: Iterable[PluginDescriptor],
        config: CliConfig,
        *,
        resolver: CredentialResolver,
        environ: Mapping[str, str] | None = None,
        transports: Mapping[str, Any] | None = None,
    ) -> ConfiguredConnectorRegistry:
        registry = cls(
            _resolver=resolver,
            _environ={} if environ is None else dict(environ),
            _transports={} if transports is None else dict(transports),
        )
        descriptor_list = tuple(descriptors)
        discovered_ids = [descriptor.identity.connector_id for descriptor in descriptor_list]
        if len(set(discovered_ids)) != len(discovered_ids):
            raise ConnectorError.configuration(
                "duplicate CLI provider descriptor",
                safe_details={"provider_id": sorted(
                    provider_id
                    for provider_id in set(discovered_ids)
                    if discovered_ids.count(provider_id) > 1
                )[0]},
            )
        discovered_id_set = set(discovered_ids)
        registry._diagnostics = tuple(
            sorted(
                provider_id
                for provider_id in config.providers
                if provider_id not in discovered_id_set
            )
        )
        for descriptor in sorted(descriptor_list, key=lambda item: item.name):
            provider_id = descriptor.identity.connector_id
            provider_config = config.providers.get(provider_id, ProviderConfig(provider_id))
            if not provider_config.enabled:
                continue
            plugin = ConfiguredPlugin(descriptor, provider_config)
            for route_key in descriptor.route_keys():
                if route_key in registry._routes:
                    raise ConnectorError(
                        ConnectorErrorCode.CONFLICT,
                        "connector route is already registered",
                        {
                            "scheme": route_key[0],
                            **({"host": route_key[1]} if route_key[1] else {}),
                        },
                    )
                registry._routes[route_key] = plugin
            if descriptor.handles_paths:
                if registry._path_plugin is not None:
                    raise ConnectorError(
                        ConnectorErrorCode.CONFLICT,
                        "multiple connectors handle path endpoints",
                        {},
                    )
                registry._path_plugin = plugin
            registry._plugins.append(plugin)
        return registry

    @property
    def diagnostics(self) -> tuple[str, ...]:
        return self._diagnostics

    def list(self) -> tuple[PluginDescriptor, ...]:
        if self._plugins and not isinstance(self._plugins[0], ConfiguredPlugin):
            return tuple(self._plugins)  # type: ignore[return-value]
        return tuple(plugin.descriptor for plugin in self._plugins)

    def descriptor_for(self, endpoint: AdapterEndpoint) -> PluginDescriptor:
        if self._plugins and not isinstance(self._plugins[0], ConfiguredPlugin):
            adapter = self.connector_for(endpoint)
            return PluginDescriptor(
                adapter.identity.connector_id,
                adapter.identity,
                adapter.schemes,
                lambda context: adapter,
                getattr(adapter, "hosts", ()),
                capabilities=getattr(adapter, "capabilities", ()),
                modes=getattr(adapter, "modes", ()),
                local=getattr(adapter, "local", False),
                handles_paths=getattr(adapter, "handles_paths", False),
            )
        plugin = self._plugin_for(endpoint)
        return plugin.descriptor

    def connector_for(self, endpoint: AdapterEndpoint) -> _LazyAdapter:
        if self._plugins and not isinstance(self._plugins[0], ConfiguredPlugin):
            if endpoint.is_stdio or endpoint.path is not None:
                for adapter in self._plugins:
                    if SCHEME_FILE in adapter.schemes or getattr(adapter, "handles_paths", False):
                        return adapter
            else:
                assert endpoint.uri is not None
                scheme = endpoint.uri.scheme.casefold()
                parsed = urlsplit(endpoint.uri.value)
                host = (
                    parsed.hostname.casefold()
                    if scheme == SCHEME_HTTPS and parsed.hostname
                    else None
                )
                for adapter in self._plugins:
                    if scheme in {item.casefold() for item in adapter.schemes} and (
                        not host or not getattr(adapter, "hosts", ()) or host in adapter.hosts
                    ):
                        return adapter
            raise ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "no connector advertises this endpoint scheme",
                {},
            )
        return _LazyAdapter(self, self._plugin_for(endpoint))

    def require_capability(self, endpoint: AdapterEndpoint, capability_id: str):
        if self._plugins and not isinstance(self._plugins[0], ConfiguredPlugin):
            adapter = self.connector_for(endpoint)
            if capability_id not in {
                capability.capability_id for capability in adapter.capabilities
            }:
                raise ConnectorError(
                    ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                    "connector does not support the requested capability",
                    {"capability": capability_id},
                )
            return adapter  # type: ignore[return-value]
        plugin = self._plugin_for(endpoint)
        descriptor = plugin.descriptor
        if capability_id not in {
            capability.capability_id for capability in descriptor.capabilities
        }:
            raise ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "connector does not support the requested capability",
                {
                    "scheme": endpoint.uri.scheme if endpoint.uri else SCHEME_FILE,
                    "capability": capability_id,
                },
            )
        return _LazyAdapter(self, plugin)

    def _plugin_for(self, endpoint: AdapterEndpoint) -> ConfiguredPlugin:
        if self._plugins and not isinstance(self._plugins[0], ConfiguredPlugin):
            raise TypeError("legacy registry does not expose configured plugins")
        if endpoint.is_stdio or endpoint.path is not None:
            if self._path_plugin is None:
                raise ConnectorError(
                    ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                    "no connector handles path endpoints",
                    {},
                )
            return self._path_plugin
        if endpoint.uri is None or not isinstance(endpoint.uri, TableURI):
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "endpoint does not contain a routable URI",
                {},
            )
        scheme = endpoint.uri.scheme.casefold()
        parsed = urlsplit(endpoint.uri.value)
        host = parsed.hostname.casefold() if scheme == SCHEME_HTTPS and parsed.hostname else None
        plugin = self._routes.get((scheme, host)) or self._routes.get((scheme, None))
        if plugin is not None:
            return plugin
        if not any(key[0] == scheme for key in self._routes):
            raise ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "no connector advertises this endpoint scheme",
                {"scheme": scheme},
            )
        raise ConnectorError(
            ConnectorErrorCode.INVALID_URI,
            "no connector supports this endpoint host",
            {"scheme": scheme, **({"host": host} if host else {})},
        )

    @contextmanager
    def open_adapter(self, endpoint: AdapterEndpoint) -> Iterator[ConnectorAdapter]:
        plugin = self._plugin_for(endpoint)
        config = plugin.config
        environment: dict[str, str] = {}
        for logical_name, environment_name in config.environment.items():
            value = self._environ.get(environment_name)
            if value is None:
                raise ConnectorError.configuration(
                    "provider environment binding is missing",
                    safe_details={
                        "provider_id": config.provider_id,
                        "field": logical_name,
                        "environment": environment_name,
                    },
                )
            environment[logical_name] = value
        if self._resolver is None:
            raise ConnectorError.configuration("credential resolver is not configured")
        lease = self._resolver.resolve(config)
        with lease:
            selected_transport = self._transports.get(config.provider_id)
            transports = (
                {config.provider_id: selected_transport}
                if selected_transport is not None
                else {}
            )
            context = ProviderFactoryContext(
                config=config,
                environment=environment,
                credentials=lease.values,
                transports=transports,
            )
            try:
                adapter = plugin.descriptor.factory(context)
            except ConnectorError:
                raise
            except Exception as exc:
                raise ConnectorError(
                    ConnectorErrorCode.EXECUTION_FAILED,
                    "provider adapter construction failed",
                    {"provider_id": config.provider_id},
                ) from exc
            if not isinstance(adapter, ConnectorAdapter):
                raise ConnectorError.configuration(
                    "provider CLI factory did not return a ConnectorAdapter",
                    safe_details={"provider_id": config.provider_id},
                )
            yield adapter


__all__ = [
    "ConfiguredConnectorRegistry",
    "ConfiguredPlugin",
    "discover_configured_plugins",
]
