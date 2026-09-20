"""Physical layout readback for the MaybeSheet provider.

`mbs range read` already returns every fact the layout observations need: a
per-cell style index matrix, the font/fill/alignment tables those indices point
at, and the sheet's explicit row heights and column widths.  This module turns
that raw evidence into the provider-neutral observation shapes and then decodes
them strictly, so a caller can never mistake an acknowledgement for evidence.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from open_table_connector.spreadsheets.observations import decode_observation

# Border and shrink-to-fit have no readback surface in `mbs range read`, so they
# are deliberately absent instead of being reported as unknown values.
STYLE_FIELDS = (
    "bold",
    "italic",
    "font_size",
    "foreground",
    "fill",
    "number_format",
    "horizontal",
    "vertical",
    "wrap_text",
    "text_layout",
)
# Row heights are points; column widths are pixels, matching the units the write
# path sends through `worksheet.config`.
CONFIG_FIELDS = ("row_heights", "column_sizes", "gridlines", "default_row_height")
LAYOUT_DIALECT = "maybe-sheet-a1"
_ALIGNMENT_FIELDS = ("horizontal", "vertical", "wrap_text", "text_layout")
_RGB = re.compile(r"^[0-9A-F]{6}$")

LAYOUT_DESCRIPTOR: dict[str, Any] = {
    "target": LAYOUT_DIALECT,
    "dialect": LAYOUT_DIALECT,
    "limits": {"max_cells": 10000},
    "operations": {
        "range.style": {field: {"read": True, "write": True} for field in STYLE_FIELDS},
        "worksheet.config": {
            "row_heights": {"read": True, "write": True, "units": ["pt"]},
            "column_sizes": {"read": True, "write": True, "units": ["px", "excel_character"]},
            "gridlines": {"read": True, "write": True},
            "default_row_height": {"read": True, "write": False},
        },
    },
}


def _rgb(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, str):
        return None
    text = value.strip().lstrip("#").upper()
    if len(text) == 8 and text.startswith("FF"):
        text = text[2:]
    return {"type": "rgb", "value": "#" + text} if _RGB.fullmatch(text) else None


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _points(value: Any) -> int | float | None:
    """Convert a provider row height (pixels) to the facade's point unit.

    `mbs` accepts only a bare number or an explicit pixel value for row
    heights, and returns that same number, while the provider-neutral
    `worksheet.config` contract states row heights in points.
    """

    pixels = _number(value)
    return None if pixels is None else round(pixels * 72 / 96, 6)


def _source(sources: dict[str, Any], ref: str, kind: str) -> str:
    sources[ref] = {"kind": kind}
    return ref


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _style_fields(
    *,
    style_index: Any,
    mapped: Mapping[str, Any],
    fonts: Mapping[str, Any],
    fills: Mapping[str, Any],
    alignments: Mapping[str, Any],
    fields: Sequence[str],
    sources: dict[str, Any],
    coordinate: str,
) -> dict[str, Any]:
    font = _mapping(fonts.get(str(mapped.get("font"))))
    fill = _mapping(fills.get(str(mapped.get("fill"))))
    alignment = _mapping(alignments.get(str(mapped.get("alignment"))))
    stored = style_index not in (None, 0, "0", "")
    wrap = bool(alignment.get("wrap_text", False))
    values: dict[str, Any] = {
        "bold": bool(font.get("bold", False)),
        "italic": bool(font.get("italic", False)),
        "font_size": _number(font.get("size")),
        "foreground": _rgb(font.get("color")),
        "fill": _rgb((fill.get("color") or [None])[0]) if fill.get("pattern") == 1 else None,
        "number_format": {
            "storage_kind": "custom" if isinstance(mapped.get("custom_num_fmt"), str) else "builtin",
            "code": mapped.get("custom_num_fmt") or "General",
            "builtin_id": None,
            "locale": None,
            "date_system": None,
        },
        "horizontal": alignment.get("horizontal"),
        "vertical": alignment.get("vertical"),
        "wrap_text": wrap,
        "text_layout": "wrap" if wrap else "no_wrap",
    }
    result: dict[str, Any] = {}
    for field in fields:
        kind = "explicit" if stored else "default"
        if field in _ALIGNMENT_FIELDS and not alignment:
            kind = "default"
        result[field] = {
            "effective": values[field],
            "source_ref": _source(sources, f"cell:{coordinate}:{field}", kind),
        }
    return result


def style_observation(
    *,
    target: Mapping[str, Any],
    address: str,
    start: tuple[int, int],
    end: tuple[int, int],
    result: Mapping[str, Any],
    fields: Sequence[str],
) -> dict[str, Any]:
    """Build a complete `range.style` observation from recorded read evidence."""

    matrix = result.get("styles")
    if not isinstance(matrix, list) or not matrix or any(not isinstance(row, list) for row in matrix):
        raise ValueError("MaybeSheet style read returned no style matrix")
    expected_rows = end[0] - start[0] + 1
    expected_columns = end[1] - start[1] + 1
    if len(matrix) != expected_rows or any(len(row) != expected_columns for row in matrix):
        raise ValueError("MaybeSheet style matrix does not cover the requested range")
    mapped_by_index = _mapping(result.get("style_map"))
    fonts = _mapping(result.get("fonts"))
    fills = _mapping(result.get("fills"))
    alignments = _mapping(result.get("alignments"))
    sources: dict[str, Any] = {}
    cells: list[dict[str, Any]] = []
    for row_offset, row in enumerate(matrix):
        for column_offset, style_index in enumerate(row):
            row_number = start[0] + row_offset
            column_number = start[1] + column_offset
            coordinate = f"{column_letter(column_number)}{row_number}"
            cells.append(
                {
                    "row": row_number,
                    "column": column_number,
                    "fields": _style_fields(
                        style_index=style_index,
                        mapped=_mapping(mapped_by_index.get(str(style_index))),
                        fonts=fonts,
                        fills=fills,
                        alignments=alignments,
                        fields=fields,
                        sources=sources,
                        coordinate=coordinate,
                    ),
                }
            )
    return {
        "kind": "spreadsheet.range.style.observation/1.0",
        "target": dict(target),
        "coverage": {"complete": True, "range": address, "fields": list(fields)},
        "physical": {"cells": cells, "sources": sources},
    }


def config_observation(
    *,
    target: Mapping[str, Any],
    rows: Sequence[int],
    columns: Sequence[str],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a complete `worksheet.config` observation from recorded read evidence."""

    formatting = _mapping(result.get("formatting"))
    widths = _mapping(formatting.get("column_widths"))
    heights = _mapping(formatting.get("row_heights"))
    sources: dict[str, Any] = {}
    row_values: dict[str, Any] = {}
    for row in rows:
        explicit = _points(heights.get(str(row)))
        row_values[str(row)] = {
            "height": explicit,
            "hidden": False,
            "source_ref": _source(sources, f"row:{row}", "explicit" if explicit is not None else "default"),
        }
    column_values: dict[str, Any] = {}
    for column in columns:
        explicit = _number(widths.get(column))
        column_values[column] = {
            "width_pixels": explicit,
            "hidden": False,
            "source_ref": _source(sources, f"column:{column}", "explicit" if explicit is not None else "default"),
        }
    return {
        "kind": "spreadsheet.worksheet.config.observation/1.0",
        "target": dict(target),
        "coverage": {
            "complete": True,
            "rows": list(rows),
            "columns": list(columns),
            "fields": list(CONFIG_FIELDS),
        },
        "physical": {
            "rows": row_values,
            "columns": column_values,
            "view": {
                "show_gridlines": bool(formatting.get("show_gridlines", True)),
                "default_row_height": _points(formatting.get("default_row_height")),
            },
            "sources": sources,
        },
    }


def column_letter(index: int) -> str:
    """Return the A1 column name for a 1-based column index."""

    if type(index) is not int or index < 1 or index > 16384:
        raise ValueError("column index is outside the worksheet bounds")
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def decode_maybe_layout(
    payload: Mapping[str, Any],
    *,
    target: Mapping[str, Any],
    selector: Mapping[str, Any],
    descriptor: Mapping[str, Any],
) -> dict[str, Any]:
    """Decode only provider read evidence; acknowledgements are not evidence."""

    if not isinstance(payload, Mapping):
        raise ValueError("MaybeSheet layout response must be an object")
    observation = payload.get("observation", payload.get("result", payload))
    if not isinstance(observation, Mapping):
        raise ValueError("MaybeSheet layout response has no observation object")
    if observation.get("kind") not in {
        "spreadsheet.range.style.observation/1.0",
        "spreadsheet.worksheet.config.observation/1.0",
    }:
        raise ValueError("MaybeSheet response is not a layout observation")
    expected_target = dict(target)
    if observation.get("target") != expected_target:
        raise ValueError("MaybeSheet observation target does not match the bound sheet")
    coverage = observation.get("coverage")
    if not isinstance(coverage, Mapping) or coverage.get("complete") is not True:
        raise ValueError("MaybeSheet layout response is incomplete")
    fields = coverage.get("fields")
    requested = selector.get("fields") or selector.get("view_fields")
    if requested is not None and (not isinstance(fields, list) or any(item not in fields for item in requested)):
        raise ValueError("MaybeSheet layout response does not cover requested fields")
    if not isinstance(descriptor, Mapping):
        raise ValueError("MaybeSheet layout descriptor is missing")
    # A descriptor can enumerate field-level units and modes.  A response that
    # returns an unknown mode/unit is a protocol failure, never a best-effort
    # conversion.
    operations = descriptor.get("operations", descriptor)
    operation = "range.style" if observation["kind"].startswith("spreadsheet.range.style") else "worksheet.config"
    available = operations.get(operation, {}) if isinstance(operations, Mapping) else {}
    physical = observation.get("physical")
    if not isinstance(physical, Mapping):
        raise ValueError("MaybeSheet layout response has no physical evidence")
    if operation == "range.style":
        for cell in physical.get("cells", ()):
            if not isinstance(cell, Mapping) or not isinstance(cell.get("fields"), Mapping):
                raise ValueError("MaybeSheet style evidence has an invalid cell")
            for field, value in cell["fields"].items():
                spec = available.get(field, {}) if isinstance(available, Mapping) else {}
                allowed = spec.get("values") if isinstance(spec, Mapping) else None
                effective = value.get("effective") if isinstance(value, Mapping) else None
                if allowed is not None and isinstance(effective, str) and effective not in allowed:
                    raise ValueError(f"MaybeSheet response contains unsupported {field} value")
    return decode_observation(observation)


__all__ = [
    "CONFIG_FIELDS",
    "LAYOUT_DESCRIPTOR",
    "LAYOUT_DIALECT",
    "STYLE_FIELDS",
    "column_letter",
    "config_observation",
    "decode_maybe_layout",
    "style_observation",
]
