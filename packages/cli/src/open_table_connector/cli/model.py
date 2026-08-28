"""Shared CLI value objects and parsing helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.request import url2pathname

from open_table_connector.contract import TableURI


class FormatName(StrEnum):
    AUTO = "auto"
    CSV = "csv"
    JSON = "json"
    JSONL = "jsonl"
    TABLE = "table"


@dataclass(frozen=True)
class Endpoint:
    raw: str
    uri: TableURI | None
    path: Path | None
    is_stdio: bool

    def __post_init__(self) -> None:
        if not isinstance(self.raw, str) or not self.raw:
            raise ValueError("raw must be a non-empty string")
        if self.is_stdio:
            if self.uri is not None or self.path is not None:
                raise ValueError("stdio endpoints cannot carry a uri or path")
            return
        if self.uri is None and self.path is None:
            raise ValueError("endpoint must have either a uri or a path")
        if self.uri is not None and self.path is not None:
            raise ValueError("endpoint cannot have both a uri and a path")


def _looks_like_windows_drive_path(value: str) -> bool:
    return len(value) >= 2 and value[1] == ":" and value[0].isalpha()


def parse_endpoint(value: str) -> Endpoint:
    if value == "-":
        return Endpoint(raw=value, uri=None, path=None, is_stdio=True)

    if _looks_like_windows_drive_path(value):
        return Endpoint(raw=value, uri=None, path=Path(value), is_stdio=False)

    parsed = urlsplit(value)
    if parsed.scheme:
        if parsed.scheme.casefold() == "file":
            validated = TableURI(value)
            file_uri = urlsplit(validated.value)
            if file_uri.netloc.casefold() not in ("", "localhost"):
                raise ValueError("file endpoint authority must be empty or localhost")
            if file_uri.query or file_uri.fragment:
                raise ValueError("file endpoint cannot contain a query or fragment")
            path = Path(url2pathname(file_uri.path))
            return Endpoint(raw=value, uri=None, path=path, is_stdio=False)
        return Endpoint(raw=value, uri=TableURI(value), path=None, is_stdio=False)

    return Endpoint(raw=value, uri=None, path=Path(value), is_stdio=False)


def parse_format(value: str | None) -> FormatName:
    if value is None:
        return FormatName.AUTO
    normalized = value.casefold()
    try:
        return FormatName(normalized)
    except ValueError as exc:
        raise ValueError(f"unsupported format: {value}") from exc


@dataclass(frozen=True)
class CliOptions:
    from_format: FormatName = FormatName.AUTO
    to_format: FormatName = FormatName.AUTO
    output_format: FormatName = FormatName.JSONL
    limit: int | None = None
    timeout: float | int | None = None
    sheet: str | None = None
    range: str | None = None
    field_names: tuple[str, ...] = ()
    if_exists: str = "error"
    token: str | None = None
    target: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.from_format, FormatName):
            object.__setattr__(self, "from_format", parse_format(str(self.from_format)))
        if not isinstance(self.to_format, FormatName):
            object.__setattr__(self, "to_format", parse_format(str(self.to_format)))
        if not isinstance(self.output_format, FormatName):
            object.__setattr__(self, "output_format", parse_format(str(self.output_format)))

        if self.limit is not None and (
            not isinstance(self.limit, int) or isinstance(self.limit, bool) or self.limit <= 0
        ):
            raise ValueError("limit must be a positive integer when supplied")

        if self.timeout is not None and (
            not isinstance(self.timeout, (int, float))
            or isinstance(self.timeout, bool)
            or self.timeout <= 0
        ):
            raise ValueError("timeout must be a positive number when supplied")

        object.__setattr__(self, "field_names", tuple(self.field_names))

        for name in ("sheet", "range", "if_exists", "token", "target"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{name} must be a string when supplied")


@dataclass(frozen=True)
class PipelineSummary:
    status: str
    rows_read: int | None = None
    rows_written: int | None = None
    source_receipt: Any | None = None
    destination_receipt: Any | None = None
