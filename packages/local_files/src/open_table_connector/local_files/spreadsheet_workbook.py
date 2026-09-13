"""Local workbook storage behind the neutral spreadsheet provider seam."""

from __future__ import annotations

import hashlib
import math
import os
import re
import stat
import tempfile
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from copy import copy
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

from open_table_connector.contract import SCHEME_FILE, ConnectorError, ConnectorErrorCode
from open_table_connector.spreadsheets import ArtifactLimits, RangeRef, SpreadsheetTarget

PROFILE = "literal-artifact/1.0"
OPERATIONS = (
    "worksheet.create",
    "worksheet.rename",
    "worksheet.delete",
    "worksheet.move",
    "worksheet.config",
    "worksheet.list",
    "range.read",
    "range.write",
    "range.clear",
    "range.style",
    "range.format",
    "range.merge",
    "range.unmerge",
    "range.sort",
    "formula.set",
    "image.insert",
    "image.list",
    "image.delete",
    "workbook.write",
    "workbook.verify",
    "workbook.inspect",
)


def _error(reason, message, code=ConnectorErrorCode.CONFIGURATION, **details):
    return ConnectorError(code, message, {"reason": reason, **details})


def _limit(limits, name, observed):
    bound = getattr(limits, name)
    if observed > bound:
        raise _error(
            name,
            "Workbook resource limit exceeded",
            ConnectorErrorCode.RESOURCE_LIMIT_EXCEEDED,
            limit=name,
            bound=bound,
            observed=observed,
        )


def _hash(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _path(uri):
    parsed = urlsplit(uri)
    if (
        parsed.scheme != SCHEME_FILE
        or parsed.netloc not in ("", "localhost")
        or parsed.query
        or parsed.fragment
    ):
        raise _error(
            "invalid_target",
            "Workbook requires an absolute file URI",
            ConnectorErrorCode.INVALID_URI,
        )
    path = Path(unquote(parsed.path))
    if not path.is_absolute() or path.suffix.lower() != ".xlsx":
        raise _error(
            "invalid_target",
            "Workbook requires an absolute .xlsx file",
            ConnectorErrorCode.INVALID_URI,
        )
    # Normalize parent aliases but do not follow the destination symlink.
    return path.parent.resolve() / path.name


def _limits(binding):
    value = binding.get("limits")
    return value if isinstance(value, ArtifactLimits) else ArtifactLimits(**(value or {}))


def _bytes(path, limits):
    if path.is_symlink():
        raise _error("symlink", "Workbook symlinks are not writable", ConnectorErrorCode.CONFLICT)
    try:
        with path.open("rb") as stream:
            data = stream.read(limits.archive_bytes + 1)
    except OSError:
        raise _error(
            "target_not_found", "Workbook cannot be read", ConnectorErrorCode.INVALID_URI
        ) from None
    if len(data) > limits.archive_bytes:
        raise _error(
            "archive_bytes",
            "Workbook exceeds byte limit",
            ConnectorErrorCode.RESOURCE_LIMIT_EXCEEDED,
        )
    return data


def _archive(data, limits):
    from .spreadsheet_verify import read_archive

    return read_archive(data, limits)


def _preservation(data, limits):
    parts = _archive(data, limits)
    # Parts outside openpyxl's proven round-trip subset fail before editing.
    allowed = re.compile(
        r"^(\[Content_Types\]\.xml|_rels/\.rels|docProps/(core|app)\.xml|xl/(workbook\.xml|_rels/workbook\.xml.rels|styles\.xml|theme/theme\d+\.xml|sharedStrings\.xml|worksheets/sheet\d+\.xml|worksheets/_rels/sheet\d+\.xml.rels|drawings/drawing\d+\.xml|drawings/_rels/drawing\d+\.xml.rels|media/image\d+\.(png|jpeg|jpg)|tables/table\d+\.xml|charts/chart\d+\.xml))$"
    )
    cell_count = text_bytes = sheets = images = image_bytes = 0
    for name, content in parts.items():
        if name.startswith("xl/media/"):
            from PIL import Image

            images += 1
            image_bytes += len(content)
            for limit_name, count in (
                ("image_bytes", len(content)),
                ("total_image_bytes", image_bytes),
                ("images", images),
            ):
                _limit(limits, limit_name, count)
            try:
                with Image.open(BytesIO(content)) as picture:
                    _limit(limits, "image_pixels", picture.width * picture.height)
                    if picture.format not in ("PNG", "JPEG"):
                        raise _error("image_format", "Unsupported stored image format")
                    picture.verify()
            except ConnectorError:
                raise
            except Exception:
                raise _error("image_decode", "Stored image cannot be decoded") from None
        if not allowed.fullmatch(name):
            raise _error(
                "unsupported_part",
                "Workbook contains a part that cannot be preserved",
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                part=name,
            )
        if name.endswith((".xml", ".rels")):
            root = ET.fromstring(content)
            if (name.startswith("xl/worksheets/") or name == "xl/sharedStrings.xml") and any(
                el.tag == "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}r"
                for el in root.iter()
            ):
                raise _error(
                    "rich_text",
                    "Rich-text preservation is unsupported",
                    ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                )
            if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                sheets += 1
                coordinates = set()
                for cell in root.iter(
                    "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"
                ):
                    address = cell.get("r", "")
                    if address in coordinates:
                        raise _error("duplicate_cell", "Duplicate cell coordinate")
                    a, b, c, d = _rect(address, limits)
                    if a != c or b != d:
                        raise _error("coordinate", "Cell address must identify one cell")
                    coordinates.add(address)
                cell_count += len(coordinates)
            if name.startswith("xl/worksheets/") or name == "xl/sharedStrings.xml":
                text_bytes += sum(
                    len((el.text or "").encode())
                    for el in root.iter(
                        "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"
                    )
                )
            for limit_name, count in (
                ("sheets", sheets),
                ("cells", cell_count),
                ("text_bytes", text_bytes),
            ):
                _limit(limits, limit_name, count)
            if name.startswith("xl/drawings/") and not name.endswith(".rels"):
                unsupported = {"sp", "grpSp", "cxnSp", "contentPart"}
                if any(el.tag.rsplit("}", 1)[-1] in unsupported for el in root.iter()):
                    raise _error(
                        "unsupported_drawing",
                        "Drawing shapes cannot be preserved",
                        ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                    )
            if any(
                el.tag.rsplit("}", 1)[-1] in ("extLst", "AlternateContent") for el in root.iter()
            ):
                raise _error(
                    "unsupported_extension",
                    "Workbook extension preservation is unavailable",
                    ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                )
            if name.endswith(".rels"):
                for rel in root:
                    if rel.get("TargetMode") == "External" and not rel.get("Type", "").endswith(
                        "/hyperlink"
                    ):
                        raise _error(
                            "external_relationship",
                            "External workbook relationships cannot be preserved",
                            ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                        )
    return parts


def _sheet_name(name):
    if (
        not isinstance(name, str)
        or not name
        or len(name) > 31
        or re.search(r"[\\/*?:\[\]\x00-\x1f]", name)
        or name.startswith("'")
        or name.endswith("'")
    ):
        raise _error("worksheet_name", "Invalid worksheet name")


def _rect(address, limits):
    from openpyxl.utils.cell import range_boundaries

    try:
        normalized = RangeRef(address).address
        a, b, c, d = range_boundaries(normalized)
    except (ValueError, TypeError):
        raise _error("range", "Range must be a finite Excel rectangle") from None
    if c < a or d < b or (c - a + 1) * (d - b + 1) > limits.cells:
        raise _error(
            "cells", "Range exceeds cell limit", ConnectorErrorCode.RESOURCE_LIMIT_EXCEEDED
        )
    return a, b, c, d


def _color(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"#?[0-9a-fA-F]{6}", value):
        raise _error("color", "Color requires opaque sRGB")
    return "FF" + value.lstrip("#").upper()


def _style(cell, changes):
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    changes = dict(changes)
    aliases = {"font_size": "size", "font_family": "family"}
    changes = {aliases.get(k, k): v for k, v in changes.items() if v is not None}
    known = {
        "family",
        "size",
        "bold",
        "italic",
        "foreground",
        "fill",
        "vertical",
        "horizontal",
        "wrap_text",
        "border",
        "reset",
    }
    if set(changes) - known:
        raise _error(
            "style", "Unsupported style property", ConnectorErrorCode.UNSUPPORTED_CAPABILITY
        )
    reset = changes.pop("reset", False)
    if not isinstance(reset, bool):
        raise _error("style", "Style reset must be boolean")
    if reset:
        cell.font, cell.fill, cell.alignment, cell.border = (
            Font(),
            PatternFill(),
            Alignment(),
            Border(),
        )
    font, alignment, border = copy(cell.font), copy(cell.alignment), copy(cell.border)
    for key, value in changes.items():
        if key in ("bold", "italic", "wrap_text") and not isinstance(value, bool):
            raise _error("style", "Style flags must be boolean")
        if key == "size" and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not 0 < value <= 409
        ):
            raise _error("style", "Font size is outside supported bounds")
        if key == "family":
            font.name = value
        elif key == "size":
            font.sz = value
        elif key in ("bold", "italic"):
            setattr(font, key, value)
        elif key == "foreground":
            font.color = _color(value)
        elif key == "fill":
            cell.fill = PatternFill("solid", fgColor=_color(value))
        elif key in ("vertical", "horizontal", "wrap_text"):
            setattr(alignment, key, value)
        elif key == "border":
            if set(value) - {"left", "right", "top", "bottom"}:
                raise _error("border", "Unsupported border edge")
            for edge, spec in value.items():
                if set(spec) - {"style", "color"} or spec.get("style") not in (
                    None,
                    "none",
                    "thin",
                    "medium",
                    "thick",
                    "dashed",
                    "dotted",
                    "double",
                ):
                    raise _error("border", "Unsupported border style")
                setattr(
                    border,
                    edge,
                    Side(
                        style=None if spec.get("style") == "none" else spec.get("style"),
                        color=_color(spec.get("color")),
                    ),
                )
    cell.font, cell.alignment, cell.border = font, alignment, border


def _config(sheet, properties, limits):
    from openpyxl.utils import column_index_from_string

    known = {
        "row_heights",
        "column_widths",
        "show_gridlines",
        "freeze_panes",
        "print_area",
        "orientation",
        "paper_size",
        "fit_to_page",
        "fit_width",
        "fit_height",
        "horizontal_centered",
        "margins",
        "visibility",
    }
    if set(properties) - known:
        raise _error(
            "config", "Unsupported worksheet property", ConnectorErrorCode.UNSUPPORTED_CAPABILITY
        )
    for key, value in properties.items():
        if key in ("row_heights", "column_widths"):
            if not isinstance(value, Mapping) or len(value) > limits.cells:
                raise _error("dimensions", "Invalid dimension mapping")
            for coordinate, size in value.items():
                if (
                    isinstance(size, bool)
                    or not isinstance(size, (int, float))
                    or not math.isfinite(size)
                    or not 0 < size <= (409 if key == "row_heights" else 255)
                ):
                    raise _error("dimensions", "Dimension outside Excel bounds")
                if key == "row_heights":
                    if not str(coordinate).isdigit() or not 1 <= int(coordinate) <= 1048576:
                        raise _error("dimensions", "Invalid row")
                    sheet.row_dimensions[int(coordinate)].height = size
                else:
                    try:
                        col = column_index_from_string(str(coordinate))
                    except ValueError:
                        raise _error("dimensions", "Invalid column") from None
                    if col > 16384:
                        raise _error("dimensions", "Invalid column")
                    sheet.column_dimensions[str(coordinate)].width = size
        elif key == "show_gridlines":
            if not isinstance(value, bool):
                raise _error("config", "Gridline flag must be boolean")
            sheet.sheet_view.showGridLines = value
        elif key == "freeze_panes":
            if value is not None:
                _rect(value, limits)
            sheet.freeze_panes = value
        elif key == "print_area":
            for address in [value] if isinstance(value, str) else value:
                _rect(address.replace("$", ""), limits)
            sheet.print_area = value
        elif key == "fit_to_page":
            if not isinstance(value, bool):
                raise _error("config", "Fit flag must be boolean")
            sheet.sheet_properties.pageSetUpPr.fitToPage = value
        elif key == "horizontal_centered":
            if not isinstance(value, bool):
                raise _error("config", "Center flag must be boolean")
            sheet.print_options.horizontalCentered = value
        elif key == "margins":
            if set(value) - {"left", "right", "top", "bottom", "header", "footer"}:
                raise _error("margins", "Unsupported margin")
            margins = copy(sheet.page_margins)
            for side, inches in value.items():
                if (
                    isinstance(inches, bool)
                    or not isinstance(inches, (int, float))
                    or not math.isfinite(inches)
                    or not 0 <= inches <= 49
                ):
                    raise _error("margins", "Invalid margin")
                setattr(margins, side, inches)
            sheet.page_margins = margins
        elif key == "visibility":
            if value not in ("visible", "hidden", "veryHidden"):
                raise _error("visibility", "Invalid sheet visibility")
            sheet.sheet_state = value
        else:
            attr = {
                "paper_size": "paperSize",
                "fit_width": "fitToWidth",
                "fit_height": "fitToHeight",
            }.get(key, key)
            if key in ("fit_width", "fit_height") and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise _error("config", "Invalid page fit count")
            if key == "orientation" and value not in ("landscape", "portrait"):
                raise _error("config", "Invalid orientation")
            setattr(sheet.page_setup, attr, value)


def _safe_value(value, literal):
    if literal:
        if not isinstance(value, str):
            raise _error("literal_type", "Literal artifacts require strings")
    elif value is not None and not isinstance(value, (str, bool, int, float, date, datetime)):
        raise _error("cell_type", "Unsupported cell value")
    if isinstance(value, str) and (
        len(value) > 32767 or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", value)
    ):
        raise _error(
            "text",
            "Text exceeds Excel limits or contains XML control characters",
            ConnectorErrorCode.RESOURCE_LIMIT_EXCEEDED,
        )
    if isinstance(value, float) and not math.isfinite(value):
        raise _error("number", "Cell number must be finite")
    if isinstance(value, int) and not isinstance(value, bool) and len(str(abs(value))) > 15:
        raise _error("precision", "Numbers beyond Excel precision require literal text")
    if isinstance(value, datetime) and value.tzinfo is not None:
        raise _error("date", "Timezone-aware dates are unsupported")
    return value


def _has_references(book):
    return bool(book.defined_names) or any(
        sheet.defined_names
        or sheet.tables
        or sheet._charts
        or sheet._pivots
        or sheet.data_validations.dataValidation
        or sheet.conditional_formatting
        or any(
            cell.data_type == "f" or getattr(cell, "hyperlink", None)
            for cell in sheet._cells.values()
        )
        for sheet in book
    )


def _apply(book, change, binding):

    op, args, name = change.operation_id, dict(change.arguments), change.target_key
    limits, literal = _limits(binding), binding.get("profile") == PROFILE
    if op.startswith("spreadsheet."):
        op = op[len("spreadsheet.") :]
    if op == "worksheet.create":
        name = args.get("name", name)
        _sheet_name(name)
        if name.casefold() in {x.casefold() for x in book.sheetnames}:
            raise _error(
                "worksheet_exists", "Worksheet already exists", ConnectorErrorCode.CONFLICT
            )
        if len(book.worksheets) >= limits.sheets:
            raise _error(
                "sheets", "Sheet limit exceeded", ConnectorErrorCode.RESOURCE_LIMIT_EXCEEDED
            )
        book.create_sheet(name, index=args.get("index"))
        return
    if name not in book.sheetnames:
        raise _error("worksheet_not_found", "Worksheet does not exist")
    sheet = book[name]
    if op in ("worksheet.rename", "worksheet.delete"):
        # Reference transformations are not generally safe; reject rather than corrupt.
        if _has_references(book):
            raise _error(
                "references",
                "Sheet structural edits with references are unsupported",
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
            )
        if op == "worksheet.delete":
            book.remove(sheet)
        else:
            new = args.get("name", args.get("new_name"))
            _sheet_name(new)
            if new.casefold() != name.casefold() and new.casefold() in {
                x.casefold() for x in book.sheetnames
            }:
                raise _error(
                    "worksheet_exists", "Worksheet already exists", ConnectorErrorCode.CONFLICT
                )
            sheet.title = new
        return
    if op == "worksheet.move":
        index = args.get("index")
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or not 0 <= index < len(book.worksheets)
        ):
            raise _error("index", "Invalid worksheet position")
        book.move_sheet(sheet, index - book.index(sheet))
        return
    if op == "worksheet.config":
        _config(sheet, args.get("properties", args), limits)
        return
    if op in ("image.insert", "image.add"):
        from openpyxl.drawing.image import Image as XLImage
        from openpyxl.drawing.spreadsheet_drawing import AnchorMarker, OneCellAnchor
        from openpyxl.drawing.xdr import XDRPositiveSize2D
        from PIL import Image

        content = args.get("content")
        if not isinstance(content, bytes) or len(content) > limits.image_bytes:
            raise _error(
                "image_bytes",
                "Invalid or oversized image",
                ConnectorErrorCode.RESOURCE_LIMIT_EXCEEDED,
            )
        with Image.open(BytesIO(content)) as image:
            if (
                image.format not in ("PNG", "JPEG")
                or image.width * image.height > limits.image_pixels
            ):
                raise _error("image", "Unsupported image format or size")
            mime = "image/png" if image.format == "PNG" else "image/jpeg"
            width, height = args.get("width", image.width), args.get("height", image.height)
            if args.get("mime_type", mime) != mime:
                raise _error("image", "Image MIME mismatch")
            image.verify()
        digest = args.get("sha256")
        if digest and digest.removeprefix("sha256:") != hashlib.sha256(content).hexdigest():
            raise _error("image_hash", "Image hash mismatch")
        if any(
            isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) or n <= 0
            for n in (width, height)
        ):
            raise _error("image", "Invalid image dimensions")
        a, b, c, d = _rect(args["anchor"], limits)
        if a != c or b != d:
            raise _error("image", "Image anchor must be one cell")
        picture = XLImage(BytesIO(content))
        picture.width = width
        picture.height = height
        picture.anchor = OneCellAnchor(
            _from=AnchorMarker(col=a - 1, row=b - 1),
            ext=XDRPositiveSize2D(cx=round(width * 9525), cy=round(height * 9525)),
        )
        picture._otc_content = content
        sheet.add_image(picture)
        return
    if op == "image.delete":
        index = args.get("index")
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or not 0 <= index < len(sheet._images)
        ):
            raise _error("image", "Invalid image index")
        del sheet._images[index]
        return
    if not (op.startswith("range.") or op == "formula.set"):
        raise _error(
            "unsupported_operation",
            "Workbook operation unavailable",
            ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
            operation=op,
        )
    a, b, c, d = _rect(args["address"], limits)

    def cells():
        return (sheet.cell(row, col) for row in range(b, d + 1) for col in range(a, c + 1))

    if op == "formula.set":
        if literal:
            raise _error("literal_formula", "Literal artifacts forbid formulas")
        expression = args["expression"]
        if (
            a != c
            or b != d
            or not isinstance(expression, str)
            or not expression.startswith("=")
            or len(expression.encode()) > 8192
        ):
            raise _error("formula", "Invalid Excel formula")
        sheet.cell(b, a).value = expression
        return
    if op == "range.write":
        values = args["values"]
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            values = [[values]]
        else:
            values = [
                list(v) if isinstance(v, Sequence) and not isinstance(v, (str, bytes)) else [v]
                for v in values
            ]
        if len(values) != d - b + 1 or any(len(row) != c - a + 1 for row in values):
            raise _error("shape", "Matrix dimensions differ from range")
        for row in values:
            for value in row:
                _safe_value(value, literal)
        for y, row in enumerate(values, b):
            for x, value in enumerate(row, a):
                cell = sheet.cell(y, x)
                cell.value = value
                if isinstance(value, str):
                    cell.data_type = "s"
                if literal:
                    cell.number_format = "@"
        if args.get("style"):
            _apply(
                book,
                type(change)(
                    op.replace("write", "style"),
                    change.capability,
                    name,
                    {"address": args["address"], "style": args["style"]},
                ),
                binding,
            )
        if args.get("format"):
            _apply(
                book,
                type(change)(
                    op.replace("write", "format"),
                    change.capability,
                    name,
                    {"address": args["address"], "format": args["format"]},
                ),
                binding,
            )
    elif op == "range.clear":
        for cell in cells():
            cell.value = None
    elif op == "range.style":
        properties = args.get(
            "style", args.get("properties", {k: v for k, v in args.items() if k != "address"})
        )
        for cell in cells():
            _style(cell, properties)
    elif op == "range.format":
        value = args.get("format", args.get("pattern") or args.get("kind"))
        if isinstance(value, Mapping):
            value = value.get("pattern") or value.get("kind")
        if not isinstance(value, str) or not value or (literal and value != "@"):
            raise _error("format", "Unsupported cell format for profile")
        for cell in cells():
            cell.number_format = value
    elif op in ("range.merge", "range.unmerge"):
        address = args["address"]
        if op == "range.merge":
            for cell in cells():
                if (cell.row, cell.column) != (b, a) and cell.value is not None:
                    raise _error("merge", "Merge would hide populated cells")
            for merged in sheet.merged_cells.ranges:
                if not (
                    c < merged.min_col
                    or a > merged.max_col
                    or d < merged.min_row
                    or b > merged.max_row
                ):
                    raise _error("merge", "Merge overlaps an existing merge")
            sheet.merge_cells(address)
        else:
            sheet.unmerge_cells(address)
    elif op == "range.sort":
        if _has_references(book):
            raise _error(
                "sort_references",
                "Sorting referenced cells is unsupported",
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
            )
        if any(
            not (c < m.min_col or a > m.max_col or d < m.min_row or b > m.max_row)
            for m in sheet.merged_cells.ranges
        ):
            raise _error("sort_merge", "Cannot sort merged cells")
        key = args.get("key_column", 1)
        header = args.get("header", False)
        reverse = args.get("reverse", False)
        blanks = args.get("blanks", "last")
        if (
            isinstance(key, bool)
            or not isinstance(key, int)
            or not 1 <= key <= c - a + 1
            or not isinstance(header, bool)
            or not isinstance(reverse, bool)
            or blanks not in ("first", "last")
        ):
            raise _error("sort", "Invalid sort options")
        rows = [
            [copy(sheet.cell(y, x)) for x in range(a, c + 1)] for y in range(b + int(header), d + 1)
        ]
        empty = [row for row in rows if row[key - 1].value is None]
        rows = [row for row in rows if row[key - 1].value is not None]
        types = {type(row[key - 1].value) for row in rows}
        if len(types) > 1 and not types <= {int, float}:
            raise _error("sort", "Sort key types must be comparable")
        rows.sort(key=lambda row: row[key - 1].value, reverse=reverse)
        rows = empty + rows if blanks == "first" else rows + empty
        for y, row in enumerate(rows, b + int(header)):
            for x, original in enumerate(row, a):
                cell = sheet.cell(y, x)
                cell.value = original.value
                cell.data_type = original.data_type
                cell._style = copy(original._style)
    else:
        raise _error(
            "unsupported_operation",
            "Workbook operation unavailable",
            ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
        )


def _image_data(picture):
    if hasattr(picture, "_otc_content"):
        return picture._otc_content
    data = picture._data()
    picture.ref = BytesIO(data)
    picture._otc_content = data
    return data


def _general_style(cell):
    return {
        name: ET.tostring(getattr(cell, name).to_tree()).decode()
        for name in ("font", "fill", "border", "alignment", "protection")
    }


def _plain(value):
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _snapshot(book, literal):
    from .spreadsheet_verify import _cell_style, _sheet_config

    style_of = _cell_style if literal else _general_style
    sheets = []
    for sheet in book:
        cells = {}
        styles = {}
        for cell in sheet._cells.values():
            if cell.value is None and cell.has_style:
                styles[cell.coordinate] = {"style": style_of(cell), "format": cell.number_format}
            if cell.value is not None:
                value = cell.value
                if isinstance(value, date) and not isinstance(value, datetime):
                    value = datetime.combine(value, datetime.min.time())
                if isinstance(value, datetime):
                    value = value.isoformat()
                cells[cell.coordinate] = {
                    "value": value,
                    "type": cell.data_type,
                    "format": cell.number_format,
                    "style": style_of(cell),
                }
        images = []
        for pic in sheet._images:
            data = _image_data(pic)
            anchor = pic.anchor
            if isinstance(anchor, str):
                from openpyxl.utils.cell import coordinate_to_tuple

                row, col = coordinate_to_tuple(anchor)
                width = round(pic.width * 9525)
                height = round(pic.height * 9525)
            else:
                if not hasattr(anchor, "ext") or anchor._from.colOff or anchor._from.rowOff:
                    raise _error(
                        "anchor",
                        "Unsupported image anchor",
                        ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                    )
                row, col = anchor._from.row + 1, anchor._from.col + 1
                width, height = anchor.ext.cx, anchor.ext.cy
            from openpyxl.utils import get_column_letter

            images.append(
                {
                    "anchor": f"{get_column_letter(col)}{row}",
                    "sha256": _hash(data),
                    "mime_type": "image/png" if data.startswith(b"\x89PNG") else "image/jpeg",
                    "width_emu": width,
                    "height_emu": height,
                }
            )
        item = {
            "name": sheet.title,
            "cells": cells,
            "styles": styles,
            "config": _sheet_config(sheet),
            "merges": (
                [str(m) for m in sheet.merged_cells.ranges]
                if literal
                else sorted(str(m) for m in sheet.merged_cells.ranges)
            ),
            "images": images,
        }
        if not literal:
            item["visibility"] = sheet.sheet_state
            item["dimension_flags"] = {
                axis: {
                    str(key): {
                        field: getattr(dim, field)
                        for field in ("hidden", "outlineLevel", "collapsed")
                    }
                    for key, dim in dimensions.items()
                }
                for axis, dimensions in (
                    ("rows", sheet.row_dimensions),
                    ("columns", sheet.column_dimensions),
                )
            }
            item["charts"] = [ET.tostring(chart._write()).decode() for chart in sheet._charts]
            item["pivots"] = [ET.tostring(pivot.to_tree()).decode() for pivot in sheet._pivots]
            item["conditional_formats"] = [
                (str(key.sqref), [ET.tostring(rule.to_tree()).decode() for rule in rules])
                for key, rules in sheet.conditional_formatting._cf_rules.items()
            ]
            item["filter"] = ET.tostring(sheet.auto_filter.to_tree()).decode()
            item["hyperlinks"] = {
                cell.coordinate: {
                    "target": cell.hyperlink.target,
                    "location": cell.hyperlink.location,
                    "tooltip": cell.hyperlink.tooltip,
                    "display": cell.hyperlink.display,
                }
                for cell in sheet._cells.values()
                if cell.hyperlink
            }
            item["defined_names"] = {
                key: ET.tostring(value.to_tree()).decode()
                for key, value in sheet.defined_names.items()
            }
            item["tables"] = [ET.tostring(t.to_tree()).decode() for t in sheet.tables.values()]
            item["validations"] = ET.tostring(sheet.data_validations.to_tree()).decode()
            item["protection"] = ET.tostring(sheet.protection.to_tree()).decode()
        sheets.append(item)
    result = {
        "schema": "otc.xlsx-physical/1.0",
        "profile": PROFILE if literal else "general/1.0",
        "sheets": sheets,
    }
    if not literal:
        result["defined_names"] = {
            key: ET.tostring(value.to_tree()).decode() for key, value in book.defined_names.items()
        }
        result["epoch"] = book.epoch.isoformat()
    return result


def _validate_book(book, binding):
    limits = _limits(binding)
    if len(book.worksheets) > limits.sheets:
        raise _error(
            "sheets", "Worksheet count limit exceeded", ConnectorErrorCode.RESOURCE_LIMIT_EXCEEDED
        )
    count = text = images = image_bytes = 0
    for sheet in book:
        for cell in sheet._cells.values():
            if cell.value is not None:
                count += 1
                if isinstance(cell.value, str):
                    text += len(cell.value.encode())
        for picture in sheet._images:
            data = _image_data(picture)
            images += 1
            image_bytes += len(data)
            if len(data) > limits.image_bytes:
                raise _error(
                    "image_bytes",
                    "Image limit exceeded",
                    ConnectorErrorCode.RESOURCE_LIMIT_EXCEEDED,
                )
    for name, observed, bound in [
        ("cells", count, limits.cells),
        ("text_bytes", text, limits.text_bytes),
        ("images", images, limits.images),
        ("total_image_bytes", image_bytes, limits.total_image_bytes),
    ]:
        if observed > bound:
            raise _error(
                name,
                "Workbook resource limit exceeded",
                ConnectorErrorCode.RESOURCE_LIMIT_EXCEEDED,
                observed=observed,
                bound=bound,
            )


@contextmanager
def _target_lock(path):
    import fcntl

    descriptor = os.open(
        str(path) + ".otc.lock", os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600
    )
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("Invalid lock")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


class LocalSpreadsheetProvider:
    capabilities = OPERATIONS

    def bind(self, target: SpreadsheetTarget):
        path = _path(target.uri)
        return {
            "uri": path.as_uri(),
            "revision": None,
            "new": not path.exists(),
            "profile": "general/1.0",
            "capabilities": OPERATIONS,
            "connector_id": "local-files",
        }

    def _build(self, binding, changes):
        from openpyxl import Workbook, load_workbook

        path = _path(binding["uri"])
        limits = _limits(binding)
        if binding.get("profile") not in (PROFILE, "general/1.0"):
            raise _error(
                "profile", "Unsupported workbook profile", ConnectorErrorCode.UNSUPPORTED_CAPABILITY
            )
        if binding.get("new"):
            if os.path.lexists(path):
                raise _error(
                    "destination_exists",
                    "Workbook destination already exists",
                    ConnectorErrorCode.CONFLICT,
                )
            book = Workbook()
            book.remove(book.active)
            if binding["profile"] == PROFILE:
                book.calculation = None
        else:
            data = _bytes(path, limits)
            if binding.get("revision") and _hash(data) != binding["revision"]:
                raise _error(
                    "stale_revision", "Workbook changed since binding", ConnectorErrorCode.CONFLICT
                )
            if binding.get("revision") is None:
                binding["revision"] = _hash(data)
            _preservation(data, limits)
            book = load_workbook(BytesIO(data), data_only=False)
            # openpyxl decodes serialized literal empty strings as None.
            for sheet in book:
                for cell in sheet._cells.values():
                    if cell.data_type == "inlineStr" and cell.value is None:
                        cell.value = ""
                        cell.data_type = "s"
        try:
            for change in changes:
                _apply(book, change, binding)
            _validate_book(book, binding)
            return book
        except Exception:
            book.close()
            raise

    def preflight(self, binding, changes):
        try:
            book = self._build(binding, changes)
            book.close()
        except ConnectorError:
            raise
        except (TypeError, ValueError, KeyError, AttributeError) as exc:
            raise _error(
                "invalid_operation", "Invalid workbook operation", error_type=type(exc).__name__
            ) from None
        return {"atomic": True, "capabilities": OPERATIONS}

    def observe(self, binding, selector):
        operation = selector.get("operation")
        path = _path(binding["uri"])
        if operation == "workbook.reconcile":
            return {
                "value": {
                    "uri": binding["uri"],
                    "revision": _hash(_bytes(path, _limits(binding))) if path.is_file() else None,
                },
                "verification": "unavailable",
                "commit": "not_applicable",
            }
        if operation == "workbook.verify":
            from .spreadsheet_verify import verify_snapshot

            expected = selector.get("expected") or binding.get("expected")
            if expected is None:
                raise _error(
                    "expected_required", "Independent expected workbook intent is required"
                )
            data = _bytes(path, _limits(binding))
            if expected.get("profile") == PROFILE:
                value = verify_snapshot(data, expected, _limits(binding))
            else:
                value = self._verify_general(data, expected, _limits(binding))
            value = {"status": "verified", **value}
            return {
                "value": value,
                "verification": "passed",
                "commit": "not_applicable",
                "receipts": ({"details": value},),
            }
        book = self._build(binding, selector.get("changes", ()))
        try:
            if operation in ("worksheet.list", "workbook.inspect"):
                value = (
                    tuple(book.sheetnames)
                    if operation == "worksheet.list"
                    else {"sheets": book.sheetnames, "profile": binding["profile"]}
                )
            elif operation == "range.read":
                a, b, c, d = _rect(selector["address"], _limits(binding))
                sheet = book[selector.get("target_key", selector.get("sheet"))]
                value = [[sheet.cell(y, x).value for x in range(a, c + 1)] for y in range(b, d + 1)]
            elif operation == "image.list":
                value = _snapshot(book, binding["profile"] == PROFILE)["sheets"][
                    book.sheetnames.index(selector["target_key"])
                ]["images"]
            else:
                raise _error(
                    "unsupported_operation",
                    "Observation unavailable",
                    ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                )
            return {"value": value, "verification": "unavailable", "commit": "not_applicable"}
        finally:
            book.close()

    def _verify_general(self, data, expected, limits):
        from openpyxl import load_workbook

        _preservation(data, limits)
        book = load_workbook(BytesIO(data), data_only=False)
        try:
            actual = _snapshot(book, False)
            # Explicit empty strings may decode as None; raw inlineStr is retained by the serializer.
            for s in actual["sheets"]:
                wanted = next(x for x in expected["sheets"] if x["name"] == s["name"])
                for address, cell in wanted["cells"].items():
                    if cell["value"] == "" and address not in s["cells"]:
                        original = book[s["name"]][address]
                        if original.data_type == "inlineStr":
                            s["cells"][address] = {
                                "type": "s",
                                "value": "",
                                "format": original.number_format,
                                "style": _general_style(original),
                            }
                            s["styles"].pop(address, None)
            if _plain(actual) != _plain(expected):
                raise _error(
                    "readback_mismatch",
                    "Workbook differs after serialization",
                    ConnectorErrorCode.READBACK_MISMATCH,
                )
            return {
                "status": "verified",
                "content_hash": _hash(data),
                "sheets": book.sheetnames,
                "cells": sum(len(s["cells"]) for s in actual["sheets"]),
            }
        finally:
            book.close()

    def commit(
        self, binding, changes, *, allow_partial=False, expected_revision=None, idempotency_key=None
    ):
        from .spreadsheet_verify import verify_snapshot

        path = _path(binding["uri"])
        limits = _limits(binding)
        if idempotency_key is not None:
            raise _error(
                "idempotency",
                "Workbook storage does not offer idempotency keys",
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
            )
        if expected_revision is not None and expected_revision != binding.get("revision"):
            raise _error("stale_revision", "Expected revision differs", ConnectorErrorCode.CONFLICT)
        # Validate before creating staging or lock files.
        self.preflight(binding, changes)
        if not path.parent.is_dir():
            raise _error("parent_missing", "Workbook parent directory must exist")
        temporary = None
        committed = False
        phase = "build"
        book = None
        try:
            with _target_lock(path):
                book = self._build(binding, changes)
                if not book.worksheets or not any(s.sheet_state == "visible" for s in book):
                    raise _error("sheets", "Workbook requires a visible worksheet")
                expected = _snapshot(book, binding["profile"] == PROFILE)
                fd, name = tempfile.mkstemp(
                    prefix="." + path.stem + "-", suffix=".xlsx", dir=path.parent
                )
                os.close(fd)
                temporary = Path(name)
                phase = "save"
                book.save(temporary)
                book.close()
                book = None
                data = _bytes(temporary, limits)
                phase = "verify"
                value = (
                    verify_snapshot(data, expected, limits)
                    if binding["profile"] == PROFILE
                    else self._verify_general(data, expected, limits)
                )
                value = {"status": "verified", **value}
                phase = "publish"
                if binding.get("new"):
                    os.link(temporary, path)
                else:
                    if _hash(_bytes(path, limits)) != binding.get("revision"):
                        raise _error(
                            "stale_revision",
                            "Workbook changed before replacement",
                            ConnectorErrorCode.CONFLICT,
                        )
                    os.replace(temporary, path)
                committed = True
                phase = "cleanup"
                temporary.unlink(missing_ok=True)
                temporary = None
                updated = {**binding, "new": False, "revision": _hash(data), "expected": expected}
                return {
                    "outcome": "succeeded",
                    "commit": "committed",
                    "verification": "passed",
                    "value": value,
                    "binding": updated,
                    "expected": expected,
                    "receipts": (
                        {"details": {**value, "expected": expected, "profile": binding["profile"]}},
                    ),
                }
        except Exception as exc:
            details = {"phase": phase, "commit": "committed" if committed else "not_committed"}
            if (
                temporary is not None
                and temporary.exists()
                and binding.get("failure_directory")
                and not committed
            ):
                try:
                    directory = Path(binding["failure_directory"])
                    directory.mkdir(parents=True, exist_ok=True)
                    data = _bytes(temporary, limits)
                    fd, name = tempfile.mkstemp(
                        prefix="workbook-failed-", suffix=".xlsx", dir=directory
                    )
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(data)
                    details["evidence"] = {
                        "path": name,
                        "content_hash": _hash(data),
                        "bytes": len(data),
                        "phase": phase,
                        "complete": phase != "save",
                    }
                except Exception as retention:
                    details["retention_error"] = type(retention).__name__
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError as cleanup:
                    details["cleanup_error"] = type(cleanup).__name__
            if isinstance(exc, ConnectorError):
                raise ConnectorError(
                    exc.code, exc.message, {**exc.safe_details, **details}
                ) from None
            code = (
                ConnectorErrorCode.CONFLICT
                if isinstance(exc, FileExistsError)
                else ConnectorErrorCode.EXECUTION_FAILED
            )
            raise _error(
                "destination_exists" if isinstance(exc, FileExistsError) else "write_failed",
                "Workbook write failed",
                code,
                **details,
            ) from None
        finally:
            if book is not None:
                book.close()
