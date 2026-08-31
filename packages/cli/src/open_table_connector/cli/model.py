"""Shared CLI value objects and parsing helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from open_table_connector.contract import (
    AdapterEndpoint,
    AdapterFormat,
    parse_adapter_endpoint,
    parse_adapter_format,
)

Endpoint = AdapterEndpoint
FormatName = AdapterFormat
parse_endpoint = parse_adapter_endpoint
parse_format = parse_adapter_format


@dataclass(frozen=True)
class CliOptions:
    from_format: FormatName = FormatName.AUTO
    output_format: FormatName = FormatName.AUTO
    to_format: FormatName = FormatName.AUTO
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
        if not isinstance(self.output_format, FormatName):
            object.__setattr__(self, "output_format", parse_format(str(self.output_format)))
        if not isinstance(self.to_format, FormatName):
            object.__setattr__(self, "to_format", parse_format(str(self.to_format)))

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
