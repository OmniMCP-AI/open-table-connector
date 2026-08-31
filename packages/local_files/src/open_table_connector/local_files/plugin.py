"""Process-host registration for the local-file temporal handlers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from open_table_connector.contract import (
    PROVIDER_JSON,
    PROVIDER_JSONL,
    PROVIDER_LOCAL_FILES,
    SCHEME_FILE,
    PluginDescriptor,
)


def provider_plugin() -> PluginDescriptor:
    from .identity import CONNECTOR_IDENTITY

    return PluginDescriptor(
        PROVIDER_LOCAL_FILES,
        CONNECTOR_IDENTITY,
        (SCHEME_FILE, PROVIDER_JSON, PROVIDER_JSONL),
        _provider_factory,
    )


def _provider_factory(*, env: Mapping[str, str], transports: Mapping[str, Any]) -> Any:
    del env, transports
    from .local_files_connector import LocalFilesConnector

    return LocalFilesConnector()


def csv_process_plugin(**kwargs: Any) -> tuple[Any, Any]:
    from .temporal_csv import CsvManagedTemporalStore, CsvTemporalExecutor

    document = kwargs["document"]
    descriptor = kwargs["descriptor"]
    root = kwargs["root"]
    store = CsvManagedTemporalStore(root, descriptor) if bool(document["managed"]) else None
    return CsvTemporalExecutor(descriptor, store), store


def json_process_plugin(**kwargs: Any) -> tuple[Any, Any]:
    from .temporal_json import JsonManagedTemporalStore, JsonTemporalExecutor

    document = kwargs["document"]
    descriptor = kwargs["descriptor"]
    root = kwargs["root"]
    provider = str(document["provider"])
    store = (
        JsonManagedTemporalStore(provider, root, descriptor)
        if bool(document["managed"])
        else None
    )
    return JsonTemporalExecutor(descriptor, store), store


def excel_process_plugin(**kwargs: Any) -> tuple[Any, Any]:
    from .temporal_excel import ExcelManagedTemporalStore, ExcelTemporalExecutor

    document = kwargs["document"]
    descriptor = kwargs["descriptor"]
    root = kwargs["root"]
    worksheet = _required_text(document, "worksheet")
    store = (
        ExcelManagedTemporalStore(root, descriptor, worksheet=worksheet)
        if bool(document["managed"])
        else None
    )
    return ExcelTemporalExecutor(descriptor, worksheet=worksheet, managed_store=store), store


def _required_text(document: Mapping[str, object], field: str) -> str:
    value = document.get(field)
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"process {field} must be a non-empty string")
    return value


__all__ = ["csv_process_plugin", "excel_process_plugin", "json_process_plugin", "provider_plugin"]
