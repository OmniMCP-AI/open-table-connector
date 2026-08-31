"""Lazy CLI provider plugin discovery."""

from __future__ import annotations

from collections.abc import Mapping
from importlib.metadata import entry_points
from typing import Any

from open_table_connector.contract import PluginDescriptor

CLI_PLUGIN_GROUP = "open_table_connector.cli_adapters"


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
        except ModuleNotFoundError as exc:
            if exc.name and not exc.name.startswith("open_table_connector"):
                raise
            continue
        if adapter is not None:
            adapters.append(adapter)
    return tuple(adapters)


def google_plugin() -> PluginDescriptor:
    from open_table_connector.cli.adapters import GoogleSheetsAdapter

    return PluginDescriptor(
        "google_sheets",
        GoogleSheetsAdapter.identity,
        GoogleSheetsAdapter.schemes,
        _google_factory,
        GoogleSheetsAdapter.hosts,
    )


def _google_factory(*, env: Mapping[str, str], transports: Mapping[str, Any]) -> Any:
    from open_table_connector.google_sheets import GoogleSheetsConnector

    connector = GoogleSheetsConnector(
        transports.get("google_sheets"),
        access_token=env.get("GOOGLE_SHEETS_ACCESS_TOKEN"),
    )
    from open_table_connector.cli.adapters import GoogleSheetsAdapter

    return GoogleSheetsAdapter(
        connector,
        transports.get("google_sheets"),
        env.get("GOOGLE_SHEETS_ACCESS_TOKEN"),
    )


def feishu_plugin() -> PluginDescriptor:
    from open_table_connector.cli.adapters import FeishuBitableAdapter

    return PluginDescriptor(
        "feishu_bitable",
        FeishuBitableAdapter.identity,
        FeishuBitableAdapter.schemes,
        _feishu_factory,
    )


def _feishu_factory(*, env: Mapping[str, str], transports: Mapping[str, Any]) -> Any:
    from open_table_connector.feishu_bitable import FeishuBitableConnector

    connector = FeishuBitableConnector(
        transports.get("feishu_bitable"),
        tenant_access_token=env.get("FEISHU_TENANT_ACCESS_TOKEN"),
    )
    from open_table_connector.cli.adapters import FeishuBitableAdapter

    return FeishuBitableAdapter(
        connector,
        transports.get("feishu_bitable"),
        env.get("FEISHU_TENANT_ACCESS_TOKEN"),
    )


def maybe_sheet_plugin() -> PluginDescriptor:
    from open_table_connector.cli.adapters import MaybeSheetAdapter

    return PluginDescriptor(
        "maybe_sheet",
        MaybeSheetAdapter.identity,
        MaybeSheetAdapter.schemes,
        _maybe_factory,
        MaybeSheetAdapter.hosts,
    )


def _maybe_factory(*, env: Mapping[str, str], transports: Mapping[str, Any]) -> Any:
    from open_table_connector.maybe_sheet import MaybeSheetConnector, SubprocessProcessClient

    connector = MaybeSheetConnector(
        transports.get("maybe_sheet") or SubprocessProcessClient(environment=env)
    )
    from open_table_connector.cli.adapters import MaybeSheetAdapter

    return MaybeSheetAdapter(connector)


def csv_plugin() -> PluginDescriptor:
    from open_table_connector.cli.adapters import CsvAdapter

    return PluginDescriptor("csv", CsvAdapter.identity, CsvAdapter.schemes, _csv_factory)


def _csv_factory(*, env: Mapping[str, str], transports: Mapping[str, Any]) -> Any:
    from open_table_connector.cli.adapters import CsvAdapter
    from open_table_connector.local_files import CsvConnector

    return CsvAdapter(CsvConnector())


def excel_plugin() -> PluginDescriptor:
    from open_table_connector.cli.adapters import ExcelAdapter

    return PluginDescriptor("excel", ExcelAdapter.identity, ExcelAdapter.schemes, _excel_factory)


def _excel_factory(*, env: Mapping[str, str], transports: Mapping[str, Any]) -> Any:
    from open_table_connector.cli.adapters import ExcelAdapter
    from open_table_connector.local_files import ExcelConnector

    return ExcelAdapter(ExcelConnector())


def markdown_plugin() -> PluginDescriptor:
    from open_table_connector.cli.adapters import MarkdownAdapter

    return PluginDescriptor(
        "md", MarkdownAdapter.identity, MarkdownAdapter.schemes, _markdown_factory
    )


def _markdown_factory(*, env: Mapping[str, str], transports: Mapping[str, Any]) -> Any:
    from open_table_connector.cli.adapters import MarkdownAdapter
    from open_table_connector.local_files import MarkdownConnector

    return MarkdownAdapter(MarkdownConnector())


def local_files_plugin() -> PluginDescriptor:
    from open_table_connector.cli.adapters import LocalAdapter

    return PluginDescriptor(
        "local_files", LocalAdapter.identity, LocalAdapter.schemes, _local_factory
    )


def _local_factory(*, env: Mapping[str, str], transports: Mapping[str, Any]) -> Any:
    from open_table_connector.cli.adapters import LocalAdapter
    from open_table_connector.local_files import LocalFilesConnector

    return LocalAdapter(LocalFilesConnector())


__all__ = ["CLI_PLUGIN_GROUP", "discover_cli_adapters"]
