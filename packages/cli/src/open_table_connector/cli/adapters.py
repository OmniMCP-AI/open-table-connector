"""Compatibility facade; concrete adapters live in provider packages."""

from collections.abc import Mapping
from typing import Any

from open_table_connector.contract import PROVIDER_EXCEL, SCHEME_FILE

from . import plugins


def build_adapters(
    env: Mapping[str, str] | None = None,
    transports: Mapping[str, Any] | None = None,
) -> tuple[Any, ...]:
    """Preserve the old import without reintroducing CLI adapter ownership."""

    del env, transports
    if not plugins._descriptor_entries():
        return ()
    from .registry import build_default_registry

    return tuple(build_default_registry().list())


__all__ = ["build_adapters"]


def __getattr__(name: str):
    """Resolve legacy adapter names from their owning provider package."""

    providers = {
        "CsvAdapter": ("open_table_connector.local_files.cli_adapter", "CsvCliAdapter"),
        "ExcelAdapter": ("open_table_connector.local_files.cli_adapter", "ExcelCliAdapter"),
        "MarkdownAdapter": (
            "open_table_connector.local_files.cli_adapter",
            "MarkdownCliAdapter",
        ),
        "LocalAdapter": (
            "open_table_connector.local_files.cli_adapter",
            "LocalFilesCliAdapter",
        ),
        "GoogleSheetsAdapter": (
            "open_table_connector.google_sheets.cli_adapter",
            "GoogleSheetsCliAdapter",
        ),
        "FeishuBitableAdapter": (
            "open_table_connector.feishu_bitable.cli_adapter",
            "FeishuBitableCliAdapter",
        ),
        "MaybeSheetAdapter": (
            "open_table_connector.maybe_sheet.cli_adapter",
            "MaybeSheetCliAdapter",
        ),
    }
    try:
        module_name, attribute = providers[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    from importlib import import_module

    value = getattr(import_module(module_name), attribute)
    if name in {"CsvAdapter", "ExcelAdapter", "MarkdownAdapter", "LocalAdapter"}:
        value = _legacy_local_adapter(value, name)
    elif name == "MaybeSheetAdapter":
        value = _legacy_maybe_sheet_adapter(value)
    elif name == "GoogleSheetsAdapter":
        value = _legacy_google_sheets_adapter(value)
    elif name == "FeishuBitableAdapter":
        value = _legacy_feishu_adapter(value)
    globals()[name] = value
    return value


def _legacy_context(provider_id: str):
    """Build the empty provider context used by pre-SDK CLI callers."""

    from open_table_connector.contract import ProviderConfig, ProviderFactoryContext

    return ProviderFactoryContext(ProviderConfig(provider_id))


def _legacy_local_adapter(adapter_type, name: str):
    """Keep the old ``Adapter(connector)`` construction seam as a shim."""

    if name == "LocalAdapter":
        from open_table_connector.local_files import LocalFilesConnector

        class LegacyLocalAdapter(adapter_type):
            def __init__(self, connector=None):
                super().__init__(
                    LocalFilesConnector() if connector is None else connector,
                    _legacy_context(adapter_type.identity.connector_id),
                )

        LegacyLocalAdapter.schemes = (SCHEME_FILE,)
        LegacyLocalAdapter.handles_paths = True
        return LegacyLocalAdapter

    class LegacyLocalAdapter(adapter_type):
        def __init__(self, connector):
            super().__init__(connector, _legacy_context(adapter_type.identity.connector_id))

    LegacyLocalAdapter.capabilities = tuple(
        capability
        for capability in adapter_type.capabilities
        if capability.capability_id != "table.write"
    )
    if name == "ExcelAdapter":
        LegacyLocalAdapter.schemes = (PROVIDER_EXCEL,)
    return LegacyLocalAdapter


def _legacy_maybe_sheet_adapter(adapter_type):
    """Keep the old ``MaybeSheetAdapter(connector)`` construction seam as a shim."""

    class LegacyMaybeSheetAdapter(adapter_type):
        def __init__(self, connector):
            super().__init__(connector, {})

    return LegacyMaybeSheetAdapter


def _legacy_google_sheets_adapter(adapter_type):
    """Keep the old transport override accepted by CLI fixture callers."""

    class LegacyGoogleSheetsAdapter(adapter_type):
        def __init__(self, connector, transport=None, environment_token=None):
            self._legacy_transport = transport
            self._legacy_environment_token = environment_token
            super().__init__(connector)

        def _connector_for_options(self, options):
            token = getattr(options, "token", None) or self._legacy_environment_token
            if self._legacy_transport is None and token is None:
                return self.connector
            return type(self.connector)(
                self._legacy_transport or self.connector._transport,
                access_token=token,
                timeout=self.connector._timeout,
                api_endpoint=self.connector._api_endpoint,
            )

    return LegacyGoogleSheetsAdapter


def _legacy_feishu_adapter(adapter_type):
    """Keep the old transport override accepted by CLI fixture callers."""

    class LegacyFeishuBitableAdapter(adapter_type):
        def __init__(self, connector, transport=None, environment_token=None):
            self._legacy_transport = transport
            self._legacy_environment_token = environment_token
            super().__init__(connector)

        def _connector_for_options(self, options):
            token = getattr(options, "token", None) or self._legacy_environment_token
            if self._legacy_transport is None and token is None:
                return self.connector
            return type(self.connector)(
                self._legacy_transport or self.connector._transport,
                tenant_access_token=token,
                timeout=self.connector._timeout,
                api_endpoint=self.connector._api_endpoint,
            )

    return LegacyFeishuBitableAdapter
