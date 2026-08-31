"""Lazy CLI provider plugin discovery."""

from __future__ import annotations

from collections.abc import Mapping
from importlib.metadata import entry_points
from typing import Any

from open_table_connector.contract import (
    CLI_PLUGIN_GROUP,
    HOST_GOOGLE_DOCS,
    HOST_MAYBE,
    PACKAGE_NAMESPACE,
    PROVIDER_CSV,
    PROVIDER_EXCEL,
    PROVIDER_FEISHU_BITABLE,
    PROVIDER_GOOGLE_SHEETS,
    PROVIDER_LOCAL_FILES,
    PROVIDER_MAYBE_SHEET,
    SCHEME_FEISHU,
    SCHEME_GSHEETS,
    SCHEME_HTTPS,
    SCHEME_MAYBE,
    SCHEME_MD,
    PluginDescriptor,
)


def _descriptor_entries() -> tuple[Any, ...]:
    discovered = entry_points()
    if hasattr(discovered, "select"):
        selected = discovered.select(group=CLI_PLUGIN_GROUP)
    else:  # pragma: no cover - compatibility with Python 3.10 metadata API
        selected = discovered.get(CLI_PLUGIN_GROUP, ())
    return tuple(sorted(selected, key=lambda item: item.name))


def discover_cli_adapters(
    env: Mapping[str, str], transports: Mapping[str, Any]
) -> tuple[Any, ...]:
    """Load installed adapter registrations without importing absent providers."""

    adapters: list[Any] = []
    for entry in _descriptor_entries():
        try:
            descriptor_factory = entry.load()
            descriptor = descriptor_factory()
            if not isinstance(descriptor, PluginDescriptor):
                raise TypeError("CLI plugin entry point must return PluginDescriptor")
            adapter = descriptor.factory(env=env, transports=transports)
            adapter = _wrap_provider_adapter(
                descriptor.name, adapter, env=env, transports=transports
            )
        except ModuleNotFoundError as exc:
            if exc.name and not exc.name.startswith(PACKAGE_NAMESPACE):
                raise
            continue
        if adapter is not None:
            adapters.append(adapter)
    return tuple(adapters)


def _wrap_provider_adapter(
    name: str,
    value: Any,
    *,
    env: Mapping[str, str],
    transports: Mapping[str, Any],
) -> Any:
    """Adapt provider-owned connector factories to the CLI host seam."""

    from open_table_connector.cli.adapters import (
        FeishuBitableAdapter,
        GoogleSheetsAdapter,
        LocalAdapter,
        MaybeSheetAdapter,
    )

    adapters = {
        PROVIDER_GOOGLE_SHEETS: lambda: GoogleSheetsAdapter(
            value,
            transports.get(PROVIDER_GOOGLE_SHEETS),
            env.get("GOOGLE_SHEETS_ACCESS_TOKEN"),
        ),
        PROVIDER_FEISHU_BITABLE: lambda: FeishuBitableAdapter(
            value,
            transports.get(PROVIDER_FEISHU_BITABLE),
            env.get("FEISHU_TENANT_ACCESS_TOKEN"),
        ),
        PROVIDER_MAYBE_SHEET: lambda: MaybeSheetAdapter(value),
        PROVIDER_LOCAL_FILES: lambda: LocalAdapter(value),
    }
    factory = adapters.get(name)
    return factory() if factory is not None else value


def google_plugin() -> PluginDescriptor:
    from open_table_connector.cli.adapters import GoogleSheetsAdapter

    return PluginDescriptor(
        PROVIDER_GOOGLE_SHEETS,
        GoogleSheetsAdapter.identity,
        (SCHEME_GSHEETS, SCHEME_HTTPS),
        _google_factory,
        (HOST_GOOGLE_DOCS,),
    )


def _google_factory(*, env: Mapping[str, str], transports: Mapping[str, Any]) -> Any:
    from open_table_connector.google_sheets import GoogleSheetsConnector

    connector = GoogleSheetsConnector(
        transports.get(PROVIDER_GOOGLE_SHEETS),
        access_token=env.get("GOOGLE_SHEETS_ACCESS_TOKEN"),
    )
    from open_table_connector.cli.adapters import GoogleSheetsAdapter

    return GoogleSheetsAdapter(
        connector,
        transports.get(PROVIDER_GOOGLE_SHEETS),
        env.get("GOOGLE_SHEETS_ACCESS_TOKEN"),
    )


def feishu_plugin() -> PluginDescriptor:
    from open_table_connector.cli.adapters import FeishuBitableAdapter

    return PluginDescriptor(
        PROVIDER_FEISHU_BITABLE,
        FeishuBitableAdapter.identity,
        (SCHEME_FEISHU, PROVIDER_FEISHU_BITABLE),
        _feishu_factory,
    )


def _feishu_factory(*, env: Mapping[str, str], transports: Mapping[str, Any]) -> Any:
    from open_table_connector.feishu_bitable import FeishuBitableConnector

    connector = FeishuBitableConnector(
        transports.get(PROVIDER_FEISHU_BITABLE),
        tenant_access_token=env.get("FEISHU_TENANT_ACCESS_TOKEN"),
    )
    from open_table_connector.cli.adapters import FeishuBitableAdapter

    return FeishuBitableAdapter(
        connector,
        transports.get(PROVIDER_FEISHU_BITABLE),
        env.get("FEISHU_TENANT_ACCESS_TOKEN"),
    )


def maybe_sheet_plugin() -> PluginDescriptor:
    from open_table_connector.cli.adapters import MaybeSheetAdapter

    return PluginDescriptor(
        PROVIDER_MAYBE_SHEET,
        MaybeSheetAdapter.identity,
        (SCHEME_MAYBE, SCHEME_HTTPS),
        _maybe_factory,
        (HOST_MAYBE,),
    )


def _maybe_factory(*, env: Mapping[str, str], transports: Mapping[str, Any]) -> Any:
    from open_table_connector.maybe_sheet import MaybeSheetConnector, SubprocessProcessClient

    connector = MaybeSheetConnector(
        transports.get(PROVIDER_MAYBE_SHEET) or SubprocessProcessClient(environment=env)
    )
    from open_table_connector.cli.adapters import MaybeSheetAdapter

    return MaybeSheetAdapter(connector)


def csv_plugin() -> PluginDescriptor:
    from open_table_connector.cli.adapters import CsvAdapter

    return PluginDescriptor(PROVIDER_CSV, CsvAdapter.identity, CsvAdapter.schemes, _csv_factory)


def _csv_factory(*, env: Mapping[str, str], transports: Mapping[str, Any]) -> Any:
    from open_table_connector.cli.adapters import CsvAdapter
    from open_table_connector.local_files import CsvConnector

    return CsvAdapter(CsvConnector())


def excel_plugin() -> PluginDescriptor:
    from open_table_connector.cli.adapters import ExcelAdapter

    return PluginDescriptor(PROVIDER_EXCEL, ExcelAdapter.identity, ExcelAdapter.schemes, _excel_factory)


def _excel_factory(*, env: Mapping[str, str], transports: Mapping[str, Any]) -> Any:
    from open_table_connector.cli.adapters import ExcelAdapter
    from open_table_connector.local_files import ExcelConnector

    return ExcelAdapter(ExcelConnector())


def markdown_plugin() -> PluginDescriptor:
    from open_table_connector.cli.adapters import MarkdownAdapter

    return PluginDescriptor(
        SCHEME_MD, MarkdownAdapter.identity, MarkdownAdapter.schemes, _markdown_factory
    )


def _markdown_factory(*, env: Mapping[str, str], transports: Mapping[str, Any]) -> Any:
    from open_table_connector.cli.adapters import MarkdownAdapter
    from open_table_connector.local_files import MarkdownConnector

    return MarkdownAdapter(MarkdownConnector())


def local_files_plugin() -> PluginDescriptor:
    from open_table_connector.cli.adapters import LocalAdapter

    return PluginDescriptor(
        PROVIDER_LOCAL_FILES, LocalAdapter.identity, LocalAdapter.schemes, _local_factory
    )


def _local_factory(*, env: Mapping[str, str], transports: Mapping[str, Any]) -> Any:
    from open_table_connector.cli.adapters import LocalAdapter
    from open_table_connector.local_files import LocalFilesConnector

    return LocalAdapter(LocalFilesConnector())


__all__ = ["CLI_PLUGIN_GROUP", "discover_cli_adapters"]
