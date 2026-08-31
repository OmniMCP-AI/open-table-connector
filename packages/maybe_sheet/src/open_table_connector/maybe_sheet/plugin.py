"""Process-host registration for MaybeSheet."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from open_table_connector.contract import PluginDescriptor


def provider_plugin() -> PluginDescriptor:
    from .identity import CONNECTOR_IDENTITY

    return PluginDescriptor(
        "maybe_sheet",
        CONNECTOR_IDENTITY,
        ("maybe", "https"),
        _provider_factory,
        ("www.maybe.ai",),
    )


def _provider_factory(*, env: Mapping[str, str], transports: Mapping[str, Any]) -> Any:
    from .connector import MaybeSheetConnector
    from .process import SubprocessProcessClient

    process = transports.get("maybe_sheet")
    if process is None:
        process = SubprocessProcessClient(environment=env)
    return MaybeSheetConnector(process)


def process_plugin(**kwargs: Any) -> tuple[Any, None]:
    from .process import SubprocessProcessClient, _absolute_executable
    from .temporal import MaybeSheetTemporalExecutor

    document = kwargs["document"]
    descriptor = kwargs["descriptor"]
    binary = _absolute_executable(_required_text(document, "maybe_sheet_binary"))
    return MaybeSheetTemporalExecutor(SubprocessProcessClient(binary=binary), descriptor), None


def _required_text(document: dict[str, object], field: str) -> str:
    value = document.get(field)
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"process {field} must be a non-empty string")
    return value


__all__ = ["process_plugin", "provider_plugin"]
