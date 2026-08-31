"""Lazy discovery of optional process provider handlers."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any

from open_table_connector.contract import TableURI
from open_table_connector.timeseries import TemporalTableDescriptor

PROCESS_PLUGIN_GROUP = "open_table_connector.process_handlers"
ProcessBinding = tuple[Any, Any]
ProcessPluginFactory = Callable[..., ProcessBinding]


def _plugin_entries() -> tuple[Any, ...]:
    discovered = entry_points()
    if hasattr(discovered, "select"):
        selected = discovered.select(group=PROCESS_PLUGIN_GROUP)
    else:  # pragma: no cover - compatibility with Python 3.10 metadata API
        selected = discovered.get(PROCESS_PLUGIN_GROUP, ())
    return tuple(sorted(selected, key=lambda item: item.name))


def discover_process_binding(
    *,
    provider: str,
    document: Mapping[str, object],
    target: TableURI,
    descriptor: TemporalTableDescriptor,
    root: Path,
) -> ProcessBinding:
    """Load the configured provider handler without importing providers eagerly."""

    for entry in _plugin_entries():
        if entry.name != provider:
            continue
        try:
            factory = entry.load()
            if not callable(factory):
                raise TypeError("process plugin entry point must be callable")
            binding = factory(
                document=document,
                target=target,
                descriptor=descriptor,
                root=root,
            )
        except ModuleNotFoundError as exc:
            if exc.name and not exc.name.startswith("open_table_connector"):
                raise
            raise ValueError(f"process provider is unavailable: {provider}") from exc
        if (
            not isinstance(binding, tuple)
            or len(binding) != 2
            or (binding[0] is None and binding[1] is None)
        ):
            raise TypeError("process plugin must return (executor, store)")
        return binding
    raise ValueError(f"process provider is unavailable: {provider}")


def csv_plugin(**kwargs: Any) -> ProcessBinding:
    from open_table_connector.local_files import CsvManagedTemporalStore, CsvTemporalExecutor

    document = kwargs["document"]
    descriptor = kwargs["descriptor"]
    root = kwargs["root"]
    store = (
        CsvManagedTemporalStore(root, descriptor) if bool(document["managed"]) else None
    )
    return CsvTemporalExecutor(descriptor, store), store


def json_plugin(**kwargs: Any) -> ProcessBinding:
    from open_table_connector.local_files import JsonManagedTemporalStore, JsonTemporalExecutor

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


def excel_plugin(**kwargs: Any) -> ProcessBinding:
    from open_table_connector.local_files import ExcelManagedTemporalStore, ExcelTemporalExecutor

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


def sqlite_plugin(**kwargs: Any) -> ProcessBinding:
    from open_table_connector.sqlite import SQLiteManagedTemporalStore, SQLiteTemporalExecutor

    document = kwargs["document"]
    target = kwargs["target"]
    descriptor = kwargs["descriptor"]
    root = kwargs["root"]
    table = _required_text(document, "physical_table")
    store = (
        SQLiteManagedTemporalStore(target, root, descriptor)
        if bool(document["managed"])
        else None
    )
    return SQLiteTemporalExecutor(descriptor, table, managed_store=store), store


def postgres_plugin(**kwargs: Any) -> ProcessBinding:
    from open_table_connector.postgres import PostgresManagedTemporalStore, PostgresTemporalExecutor

    document = kwargs["document"]
    target = kwargs["target"]
    descriptor = kwargs["descriptor"]
    root = kwargs["root"]
    table = _required_text(document, "physical_table")
    store = (
        PostgresManagedTemporalStore(target, root, descriptor)
        if bool(document["managed"])
        else None
    )
    return PostgresTemporalExecutor(descriptor, table, managed_store=store), store


def maybe_sheet_plugin(**kwargs: Any) -> ProcessBinding:
    from open_table_connector.maybe_sheet import (
        MaybeSheetTemporalExecutor,
        SubprocessProcessClient,
        _absolute_executable,
    )

    document = kwargs["document"]
    descriptor = kwargs["descriptor"]
    binary = _absolute_executable(_required_text(document, "maybe_sheet_binary"))
    return MaybeSheetTemporalExecutor(SubprocessProcessClient(binary=binary), descriptor), None


def _required_text(document: Mapping[str, object], field: str) -> str:
    value = document.get(field)
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"process {field} must be a non-empty string")
    return value


__all__ = ["PROCESS_PLUGIN_GROUP", "discover_process_binding"]
