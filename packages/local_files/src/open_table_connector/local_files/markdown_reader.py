"""Neutral Markdown pipe-table codec for local-file connectors."""

from __future__ import annotations

import re
from typing import Iterable, Sequence, TextIO

import pyarrow as pa

from open_table_connector.contract.errors import ConnectorError, ConnectorErrorCode


_MARKDOWN_SEPARATOR_RE = re.compile(r":?-+:?")


def read_markdown_arrow(text: str, *, source: str) -> pa.Table:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return pa.table({})
    rows = [
        (index + 1, _split_markdown_row(line, line_number=index + 1, source=source))
        for index, line in enumerate(lines)
    ]
    _, header = rows[0]
    body_start = 1
    if len(rows) > 1 and _is_separator_row(rows[1][1]):
        separator_line, separator_row = rows[1]
        if len(separator_row) != len(header):
            raise ConnectorError(
                ConnectorErrorCode.EXECUTION_FAILED,
                "Markdown table row has an inconsistent column count",
                {"path": source, "line": separator_line},
            )
        body_start = 2
    for line_number, row in rows[body_start:]:
        if len(row) != len(header):
            raise ConnectorError(
                ConnectorErrorCode.EXECUTION_FAILED,
                "Markdown table row has an inconsistent column count",
                {"path": source, "line": line_number},
            )
    data_rows = [
        {header[index]: _normalize_table_cell(value) for index, value in enumerate(row)}
        for _, row in rows[body_start:]
    ]
    return _rows_to_table(data_rows, header)


def write_markdown_table(
    headers: Sequence[str], rows: Iterable[Sequence[str]], stream: TextIO
) -> None:
    names = [_escape_markdown_cell(str(header)) for header in headers]
    if not names:
        return
    values = [[_escape_markdown_cell(str(value)) for value in row] for row in rows]
    if any(len(row) != len(names) for row in values):
        raise ValueError("table rows must match the header width")
    widths = [
        max([len(name), 3] + [len(row[index]) for row in values])
        for index, name in enumerate(names)
    ]
    stream.write(_format_markdown_row(names, widths))
    stream.write("\n")
    stream.write(_format_markdown_separator(widths))
    stream.write("\n")
    for row in values:
        stream.write(_format_markdown_row(row, widths))
        stream.write("\n")


def is_markdown_payload(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    try:
        header = _split_markdown_row(lines[0], line_number=1, source="<probe>")
        separator = _split_markdown_row(lines[1], line_number=2, source="<probe>")
    except ConnectorError:
        return False
    if not header or len(header) != len(separator):
        return False
    if len(header) == 1 and "|" not in lines[0]:
        return False
    return _is_separator_row(separator)


def _rows_to_table(rows: list[dict[str, object | None]], columns: Iterable[str]) -> pa.Table:
    ordered_columns = list(columns)
    data = {name: [row.get(name) for row in rows] for name in ordered_columns}
    return pa.table(data)


def _normalize_table_cell(value: object | None) -> object | None:
    if value == "":
        return None
    return value


def _split_markdown_row(line: str, *, line_number: int, source: str) -> list[str]:
    content = line.strip()
    if content.startswith("|"):
        content = content[1:]
    if content.endswith("|"):
        backslashes = 0
        for character in reversed(content[:-1]):
            if character != "\\":
                break
            backslashes += 1
        if backslashes % 2 == 0:
            content = content[:-1]

    raw_cells: list[str] = []
    cell: list[str] = []
    index = 0
    while index < len(content):
        character = content[index]
        if character == "\\" and index + 1 < len(content):
            cell.extend((character, content[index + 1]))
            index += 2
            continue
        if character == "|":
            raw_cells.append("".join(cell))
            cell = []
        else:
            cell.append(character)
        index += 1
    raw_cells.append("".join(cell))

    cells = [_unescape_markdown_cell(cell.strip()) for cell in raw_cells]
    if len(cells) == 1 and cells[0] == "":
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "Markdown table row is empty",
            {"path": source, "line": line_number},
        )
    return cells


def _unescape_markdown_cell(value: str) -> str:
    characters: list[str] = []
    index = 0
    while index < len(value):
        character = value[index]
        if character != "\\" or index + 1 == len(value):
            characters.append(character)
            index += 1
            continue

        escaped = value[index + 1]
        if escaped == "n":
            characters.append("\n")
        elif escaped in {"\\", "|"}:
            characters.append(escaped)
        else:
            characters.extend((character, escaped))
        index += 2
    return "".join(characters)


def _is_separator_row(row: list[str]) -> bool:
    return bool(row) and all(_MARKDOWN_SEPARATOR_RE.fullmatch(cell) is not None for cell in row)


def _escape_markdown_cell(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r\n", "\\n")
        .replace("\r", "\\n")
        .replace("\n", "\\n")
    )


def _format_markdown_row(cells: list[str], widths: list[int]) -> str:
    padded = [cell.ljust(widths[index]) for index, cell in enumerate(cells)]
    return "| " + " | ".join(padded) + " |"


def _format_markdown_separator(widths: list[int]) -> str:
    parts = ["-" * max(3, width) for width in widths]
    return "| " + " | ".join(parts) + " |"
