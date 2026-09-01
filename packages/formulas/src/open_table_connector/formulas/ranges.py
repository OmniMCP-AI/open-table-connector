"""Bounded A1 rectangle parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass

_A1_PATTERN = re.compile(
    r"^(?:(?P<sheet>(?:'[^']+'|[A-Za-z0-9_ .-]+))!)?"
    r"(?P<start>\$?[A-Za-z]+\$?[1-9]\d*)"
    r"(?::(?P<end>\$?[A-Za-z]+\$?[1-9]\d*))?$"
)
_CELL_PATTERN = re.compile(
    r"^(?P<abs_col>\$?)(?P<col>[A-Za-z]+)(?P<abs_row>\$?)(?P<row>[1-9]\d*)$"
)


def _column_index(label: str) -> int:
    value = 0
    for character in label:
        value = (value * 26) + (ord(character) - ord("A") + 1)
    return value


def _normalize_cell(address: str) -> tuple[str, int, int]:
    match = _CELL_PATTERN.fullmatch(address)
    if match is None:
        raise ValueError("A1 selector must use bounded cell coordinates")
    column = match.group("col").upper()
    row = int(match.group("row"))
    return (
        f"{match.group('abs_col')}{column}{match.group('abs_row')}{row}",
        _column_index(column),
        row,
    )


@dataclass(frozen=True, slots=True)
class A1Rectangle:
    worksheet_name: str | None
    start_address: str
    end_address: str
    start_column: int
    start_row: int
    end_column: int
    end_row: int

    @classmethod
    def parse(cls, selector: str) -> A1Rectangle:
        if not isinstance(selector, str) or not selector.strip():
            raise ValueError("A1 selector must be a non-empty string")
        match = _A1_PATTERN.fullmatch(selector.strip())
        if match is None:
            raise ValueError("A1 selector must be one bounded cell or rectangle")
        start_address, start_column, start_row = _normalize_cell(match.group("start"))
        end_address, end_column, end_row = _normalize_cell(match.group("end") or match.group("start"))
        if end_column < start_column or end_row < start_row:
            raise ValueError("A1 rectangle cannot be reversed")
        worksheet_name = match.group("sheet")
        if worksheet_name is not None and worksheet_name.startswith("'") and worksheet_name.endswith("'"):
            worksheet_name = worksheet_name[1:-1]
        return cls(
            worksheet_name=worksheet_name,
            start_address=start_address,
            end_address=end_address,
            start_column=start_column,
            start_row=start_row,
            end_column=end_column,
            end_row=end_row,
        )

    @property
    def height(self) -> int:
        return self.end_row - self.start_row + 1

    @property
    def width(self) -> int:
        return self.end_column - self.start_column + 1

    @property
    def cell_count(self) -> int:
        return self.height * self.width

    def require_unbound_selector(self, selector: str) -> A1Rectangle:
        if "!" in selector:
            raise ValueError("worksheet prefix is not allowed after binding")
        return self.parse(selector)


__all__ = ["A1Rectangle"]
