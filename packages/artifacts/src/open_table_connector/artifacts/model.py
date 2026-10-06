"""Neutral, closed models for optional document artifacts and views."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Any

from open_table_connector.contract import SCHEME_XLSX, TargetSelector


def _freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def display_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def validate_asset_path(value: str) -> str:
    if not isinstance(value, str) or not value or os.path.isabs(value) or ".." in PurePosixPath(value).parts:
        raise ValueError("asset path must stay inside the configured asset root")
    return value


def _format(destination: str, spec: Mapping[str, object]) -> str:
    suffix = destination.rsplit(".", 1)[-1].casefold() if "." in destination else ""
    value = spec.get("format", suffix)
    if value not in {"docx", "pptx", SCHEME_XLSX} or suffix != value:
        raise ValueError("artifact format does not match destination")
    return str(value)


@dataclass(frozen=True, slots=True)
class ExportRequest:
    source_uri: str
    destination_uri: str
    engine: str
    spec: Mapping[str, object]

    def __post_init__(self):
        if self.engine != "officecli":
            raise ValueError("unsupported artifact engine")
        if self.destination_uri.rsplit(".", 1)[-1].casefold() in {"doc", "ppt", "xls"}:
            raise ValueError("legacy artifact extensions are rejected")
        _format(self.destination_uri, self.spec)
        object.__setattr__(self, "spec", _freeze(self.spec))


@dataclass(frozen=True, slots=True)
class ViewRequest:
    source: TargetSelector
    mode: str
    destination_uri: str | None = None
    selector: Mapping[str, object] = MappingProxyType({})

    def __post_init__(self):
        if self.mode not in {"html", "screenshot", "text", "outline", "stats", "issues"}:
            raise ValueError("unsupported artifact view mode")
        object.__setattr__(self, "selector", _freeze(self.selector))


@dataclass(frozen=True, slots=True)
class WatchRequest:
    action: str
    source: TargetSelector | None = None
    session_id: str | None = None
    read_only_required: bool = False

    def __post_init__(self):
        if self.action not in {"start", "status", "refresh", "stop"}:
            raise ValueError("unsupported watch action")
        if type(self.read_only_required) is not bool:
            raise TypeError("read_only_required must be boolean")


@dataclass(frozen=True, slots=True)
class ArtifactValue:
    uri: str
    media_type: str
    content_hash: str
    engine: str
    coverage: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ViewValue:
    outputs: tuple[Mapping[str, object], ...]
    source_uri: str
    source_hash: str
    renderer: Mapping[str, object] = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class WatchValue:
    session_id: str
    state: str
    url: str | None = None
    source_hash: str | None = None
    snapshot_hash: str | None = None
    editability: str = "preview_copy_only"
    persistence: str = "discard"


__all__ = ["ArtifactValue", "ExportRequest", "ViewRequest", "ViewValue", "WatchRequest", "WatchValue", "display_cell", "validate_asset_path"]
