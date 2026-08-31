"""Compatibility facade; concrete adapters live in provider packages."""

from collections.abc import Mapping
from typing import Any

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
    globals()[name] = value
    return value
