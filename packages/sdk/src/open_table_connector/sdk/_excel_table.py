"""Lexical Excel table conversion; persistence stays with workbook providers."""

from __future__ import annotations

import re

import polars as pl


def _text(value):
    if value is None:
        return None
    text = str(value)
    if len(text) > 32767 or any(
        not (c in '\t\n\r' or '\x20' <= c <= '\ud7ff' or '\ue000' <= c <= '\ufffd' or '\U00010000' <= c <= '\U0010ffff')
        for c in text
    ):
        raise ValueError('Excel table text exceeds cell limits or contains invalid XML characters')
    return text


def table_matrix(frame: pl.DataFrame, *, header: bool = True):
    if not isinstance(frame, pl.DataFrame):
        raise TypeError('table write requires a Polars DataFrame')
    if not isinstance(header, bool):
        raise TypeError('header must be a bool')
    if not frame.width or any(not name.strip() for name in frame.columns):
        raise ValueError('table requires nonempty unique column names')
    allowed = {pl.String, pl.Null, pl.Boolean, pl.Int8, pl.Int16, pl.Int32, pl.Int64,
               pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64, pl.Float32, pl.Float64}
    if any(dtype not in allowed for dtype in frame.dtypes):
        raise TypeError('Excel table requires scalar string, boolean or numeric columns')
    # Polars casting is the lexical contract (including lowercase booleans).
    lexical = frame.cast(pl.String)
    rows = [[_text(value) for value in row] for row in lexical.iter_rows()]
    return ([[_text(name) for name in frame.columns]] if header else []) + rows


def matrix_table(values, *, header: bool = True):
    if not isinstance(header, bool):
        raise TypeError('header must be a bool')
    if not values or not values[0]:
        raise ValueError('table rectangle is empty')
    width = len(values[0])
    if any(len(row) != width for row in values):
        raise ValueError('table rows must be rectangular')
    names = values[0] if header else [f'column_{i + 1}' for i in range(width)]
    if any(not isinstance(name, str) or not name.strip() for name in names) or len(set(names)) != width:
        raise ValueError('table headers must be nonempty unique strings')
    rows = values[1:] if header else values
    return pl.DataFrame([[_text(value) for value in row] for row in rows],
                        schema={name: pl.String for name in names}, orient='row')


def rectangle_shape(address):
    def coordinate(cell):
        match = re.fullmatch(r'([A-Z]+)([1-9][0-9]*)', cell)
        if match is None:
            raise ValueError('table requires a finite A1 rectangle')
        column = 0
        for char in match[1]:
            column = column * 26 + ord(char) - 64
        return int(match[2]), column
    start, _, end = address.partition(':')
    top, left = coordinate(start)
    bottom, right = coordinate(end or start)
    return bottom - top + 1, right - left + 1


def table_address(rows, columns):
    letters = ''
    while columns:
        columns, remainder = divmod(columns - 1, 26)
        letters = chr(65 + remainder) + letters
    return f'A1:{letters}{rows}'
