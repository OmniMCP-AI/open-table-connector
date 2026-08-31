"""Process-host registration for MaybeSheet."""

from __future__ import annotations

from typing import Any

from .cli_adapter import maybe_sheet_cli_plugin

provider_plugin = maybe_sheet_cli_plugin


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


__all__ = ["maybe_sheet_cli_plugin", "process_plugin", "provider_plugin"]
