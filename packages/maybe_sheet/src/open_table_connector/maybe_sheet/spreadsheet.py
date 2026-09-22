"""Buffered Sheet-mode commands for mbs 0.28.4, JSON contract 1.0.

One process invocation is the largest supported boundary. The CLI exposes no
transaction spanning commands. Stable text sorting reads then writes under explicit
partial opt-in, without CAS or formula-reference translation. Read observations are
remote evidence, never physical XLSX verification.
"""

from __future__ import annotations

import json
import math
import re
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from open_table_connector.contract import (
    HOST_MAYBE,
    PROVIDER_JSON,
    PROVIDER_MAYBE_SHEET,
    SCHEME_HTTPS,
    ConnectorError,
    ConnectorErrorCode,
    TableURI,
)
from open_table_connector.spreadsheets import RangeRef, SpreadsheetTarget
from open_table_connector.spreadsheets._operations import Change
from open_table_connector.spreadsheets.model import _coordinate

from .connector import _mbs_target
from .grid_formula import _ENVELOPE_KEYS
from .spreadsheet_observe import (
    LAYOUT_DESCRIPTOR,
    STYLE_FIELDS,
    column_letter,
    config_observation,
    decode_maybe_layout,
    style_observation,
)


def _reject(message, code=ConnectorErrorCode.UNSUPPORTED_CAPABILITY):
    raise ConnectorError(code, message, {})


def _name(value):
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 31
        or re.search(r"[\\/*?:\[\]]", value)
        or value.startswith("'")
        or value.endswith("'")
    ):
        _reject("Invalid worksheet name", ConnectorErrorCode.INVALID_URI)
    return value


def _plain(value):
    if isinstance(value, Mapping):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(v) for v in value]
    return value


def _bounded_span(address):
    """Return one inclusive bounded A1 span, rejecting unbounded rectangles."""

    text = RangeRef(address).address
    first, last = (text.split(":") + [text])[:2]
    start = _coordinate(first)
    end = _coordinate(last)
    if (
        end[0] < start[0]
        or end[1] < start[1]
        or (end[0] - start[0] + 1) * (end[1] - start[1] + 1) > 10000
    ):
        raise ValueError("range is unbounded or too large")
    return (start[0], start[1], end[0], end[1])


def _coordinate_bounds(address):
    """Split a bounded A1 range into inclusive (row, column) start and end."""

    first, last = (str(address).split(":") + [str(address)])[:2]
    start = _coordinate(first)
    end = _coordinate(last)
    if end[0] < start[0] or end[1] < start[1]:
        raise ValueError("range end precedes start")
    return start, end


def _band_key(key, kind):
    """Normalize one dimension selector to a comparable index, or None."""

    if kind == "row":
        if isinstance(key, bool):
            return None
        if isinstance(key, int):
            return key
        if isinstance(key, str) and key.isdigit():
            return int(key)
        return None
    if isinstance(key, str) and re.fullmatch(r"[A-Za-z]{1,3}", key):
        return _coordinate(key.upper() + "1")[1]
    return None


def _size_bands(values, *, kind):
    """Group contiguous dimensions that share one size into inclusive bands.

    The provider's width/height endpoints accept a start and end coordinate, so
    a band of equal sizes costs one provider call and one workbook version
    instead of one per row or column.
    """

    if not isinstance(values, Mapping):
        _reject("Dimension configuration must be an object")
    ordered = []
    for key, size in values.items():
        index = _band_key(key, kind)
        if index is None:
            _reject("Invalid worksheet dimension selector", ConnectorErrorCode.INVALID_URI)
        if type(size) not in (float, int) or not math.isfinite(size) or size <= 0:
            _reject("Dimension configuration requires positive sizes")
        ordered.append((index, size))
    if len({index for index, _ in ordered}) != len(ordered):
        _reject("Dimension configuration repeats a selector")
    ordered.sort()
    bands = []
    for index, size in ordered:
        if bands and bands[-1][1] + 1 == index and bands[-1][2] == size:
            bands[-1][1] = index
        else:
            bands.append([index, index, size])
    return [tuple(band) for band in bands]


class MaybeSpreadsheetProvider:
    capabilities = (
        "worksheet.list",
        "worksheet.create",
        "worksheet.rename",
        "worksheet.delete",
        "worksheet.move",
        "worksheet.config",
        "range.read",
        "range.style.read",
        "worksheet.config.read",
        "range.write",
        "range.clear",
        "range.style",
        "range.format",
        "range.merge",
        "range.unmerge",
        "range.sort",
        "row.height",
        "column.width",
        "formula.set",
        "formula.set_range",
        "formula.read",
        "image.insert",
        "image.list",
        "image.read",
        "image.delete",
        "workbook.create",
        "workbook.copy",
        "workbook.write",
        "workbook.verify",
    )

    def __init__(self, connector, credentials=None, timeout=120):
        self._connector = connector
        self._credentials = dict(credentials or {})
        self._timeout = timeout

    def _call(self, argv, operation):
        argv = tuple(argv)
        payload = self._connector._run_process(
            (argv[0], "--contract-version", "1.0", *argv[1:], "--output", PROVIDER_JSON),
            credentials=self._credentials,
            timeout=self._timeout,
        )
        if not isinstance(payload, Mapping) or len(json.dumps(payload).encode()) > 8 * 1024 * 1024:
            _reject("Invalid or oversized MaybeSheet response", ConnectorErrorCode.EXECUTION_FAILED)
        # mbs 0.28.4 still emits this documented compatibility envelope for
        # workbook creation and style/image commands, even with contract 1.0.
        if (
            {"success", "endpoint", "result"}
            <= set(payload)
            <= {"success", "endpoint", "result", "target", "context", "verify", "metadata"}
        ):
            if (
                payload["success"] is not True
                or not isinstance(payload["result"], Mapping)
                or payload["result"].get("success") is False
            ):
                _reject("MaybeSheet command failed", ConnectorErrorCode.EXECUTION_FAILED)
            return dict(result=payload["result"], request_id=None, verification=None)
        if (
            set(payload) != _ENVELOPE_KEYS
            or payload["contract_version"] != "1.0"
            or payload["operation"] != operation
            or payload["ok"] is not True
            or not isinstance(payload["result"], Mapping)
            or payload["verification"] is not None
            and not isinstance(payload["verification"], Mapping)
        ):
            _reject(
                "Invalid or unsuccessful MaybeSheet command evidence",
                ConnectorErrorCode.EXECUTION_FAILED,
            )
        return payload

    def bind(self, target: SpreadsheetTarget):
        parsed = urlsplit(target.uri)
        if parsed.scheme == SCHEME_HTTPS:
            if (
                parsed.hostname != HOST_MAYBE
                or not re.fullmatch(r"/docs/spreadsheets/d/[^/]+/?", parsed.path)
                or parsed.query
                or parsed.fragment
            ):
                _reject(
                    "Workbook requires a canonical MaybeSheet document URL",
                    ConnectorErrorCode.INVALID_URI,
                )
        else:
            _reject("Unsupported MaybeSheet workbook URI", ConnectorErrorCode.INVALID_URI)
        return dict(
            uri=target.uri,
            profile="general/1.0",
            revision=None,
            worksheets=None,
            dialect="maybe-sheet-a1",
            capabilities=self.capabilities,
        )

    def _list(self, binding):
        response = self._call(
            ("mbs", "worksheet", "list", "--uri", _mbs_target(TableURI(binding["uri"]))),
            "worksheet.list",
        )
        rows = response["result"].get("worksheets")
        if not isinstance(rows, list):
            _reject("Invalid worksheet discovery response", ConnectorErrorCode.EXECUTION_FAILED)
        sheets = {}
        for row in rows:
            if not isinstance(row, Mapping):
                _reject("Invalid worksheet discovery row", ConnectorErrorCode.EXECUTION_FAILED)
            gid = row.get("gid", row.get("id"))
            name = row.get("name", row.get("title"))
            engine = row.get("data_engine", row.get("type", row.get("kind")))
            if (
                isinstance(gid, bool)
                or not isinstance(gid, (str, int))
                or not str(gid).isdigit()
                or str(gid) in {row["gid"] for row in sheets.values()}
                or not isinstance(name, str)
                or name in sheets
            ):
                _reject(
                    "Invalid or ambiguous worksheet identity", ConnectorErrorCode.EXECUTION_FAILED
                )
            sheets[name] = dict(gid=str(gid), name=name, engine=engine)
        return sheets

    def _checked_sheets(self, binding):
        current = self._list(binding)
        previous = binding.get("worksheets")
        if previous is not None and list(previous.items()) != list(current.items()):
            _reject(
                "Worksheet identities changed; rebind the workbook", ConnectorErrorCode.CONFLICT
            )
        if isinstance(binding, dict):
            binding["worksheets"] = current
        return {name: dict(row) for name, row in current.items()}

    @staticmethod
    def _expand(changes):
        expanded = []
        for change in changes:
            if change.operation_id != "worksheet.config":
                expanded.append(change)
                continue
            args = change.arguments
            if set(args) - {"row_heights", "column_widths_pixels"}:
                _reject(
                    "MaybeSheet configuration supports row heights in points and column widths in pixels only"
                )
            for start, end, height in _size_bands(args.get("row_heights", {}), kind="row"):
                expanded.append(
                    Change(
                        "row.height",
                        change.capability,
                        change.target_key,
                        {"start_row": start, "end_row": end, "height_points": height},
                    )
                )
            for start, end, width in _size_bands(
                args.get("column_widths_pixels", {}), kind="column"
            ):
                expanded.append(
                    Change(
                        "column.width",
                        change.capability,
                        change.target_key,
                        {
                            "start_column": column_letter(start),
                            "end_column": column_letter(end),
                            "width_pixels": width,
                        },
                    )
                )
        return tuple(expanded)

    def _topology_binding(self, binding):
        """Bind topology reads to a pending copy's source.

        ``mbs workbook copy`` allocates the copy's document id itself, so before
        the copy commits the destination identity in the binding does not exist
        yet.  The copy preserves the source's worksheet names, gids and engines,
        so reads that answer "what worksheets does this workbook have" must ask
        the source until the copy lands.
        """
        source = binding.get("copy_from")
        return dict(binding, uri=str(source)) if source else binding

    def preflight(self, binding, changes: Iterable[Change]):
        changes = self._expand(changes)
        if binding.get("profile") != "general/1.0":
            _reject("MaybeSheet supports the general workbook profile only")
        # A created workbook has no worksheets to validate against until the
        # provider has allocated it.  A copied workbook does: the copy
        # preserves the source names, gids and engines, so the source list is
        # the exact set of targets the queued changes may name -- validated
        # on a copy of the binding because the destination identity is only
        # known once the provider returns it.
        origin = bool(binding.get("new") or binding.get("copy_from"))
        if binding.get("copy_from"):
            sheets = self._checked_sheets(self._topology_binding(binding))
        elif binding.get("new"):
            sheets = {}
        else:
            sheets = self._checked_sheets(binding)
        for change in changes:
            self._validate(change, sheets)
        return dict(
            supported=True,
            atomic=len(changes) + origin <= 1
            and not any(c.operation_id == "range.sort" for c in changes),
            command_count=len(changes) + origin,
            observation="committed",
        )

    def _validate(self, change, sheets):
        op, name, args = change.operation_id, change.target_key, change.arguments
        supported = {
            "worksheet.create",
            "worksheet.rename",
            "worksheet.delete",
            "worksheet.move",
            "range.write",
            "range.sort",
            "range.clear",
            "range.style",
            "range.format",
            "range.merge",
            "range.unmerge",
            "row.height",
            "column.width",
            "formula.set",
            "formula.set_range",
            "image.insert",
            "image.add",
            "image.delete",
        }
        if op not in supported:
            _reject(f"MaybeSheet operation has no tested dispatch: {op}")
        allowed = {
            "worksheet.create": set(),
            "worksheet.rename": {"name", "new_name"},
            "worksheet.delete": set(),
            "worksheet.move": {"index"},
            "range.write": {"address", "values"},
            "range.clear": {"address"},
            "range.merge": {"address"},
            "range.unmerge": {"address"},
            "range.sort": {"address", "key_column", "header", "reverse"},
            "row.height": {"row", "start_row", "end_row", "height_points"},
            "column.width": {"column", "start_column", "end_column", "width_pixels"},
            "formula.set": {"address", "cell", "expression", "formula", "dialect"},
            "formula.set_range": {"address", "formulas", "dialect"},
            "image.delete": {"picture_id"},
        }
        if op in allowed and set(args) - allowed[op]:
            _reject("Operation contains unsupported arguments")
        if op in ("formula.set", "formula.set_range") and (
            args.get("dialect", "maybe-sheet-a1") != "maybe-sheet-a1"
        ):
            _reject("Formula dialect differs from the MaybeSheet workbook")
        if op == "formula.set_range":
            # The batch endpoint rejects an empty slot, so one command can only
            # carry a fully populated rectangle of formulas.
            try:
                start, end = _coordinate_bounds(RangeRef(str(args.get("address"))).address)
            except (TypeError, ValueError):
                _reject("Formula range requires one bounded A1 range")
            matrix = args.get("formulas")
            rows = end[0] - start[0] + 1
            columns = end[1] - start[1] + 1
            if (
                (rows, columns) == (1, 1)
                or not isinstance(matrix, (list, tuple))
                or len(matrix) != rows
                or any(not isinstance(row, (list, tuple)) or len(row) != columns for row in matrix)
            ):
                _reject("Formula range requires one populated formula per cell")
            for row in matrix:
                for cell in row:
                    if (
                        not isinstance(cell, str)
                        or not cell.startswith("=")
                        or len(cell.encode()) > 65536
                    ):
                        _reject("Formula range requires bounded Excel expressions")
        if op == "worksheet.create":
            _name(name)
            if any(s.casefold() == name.casefold() for s in sheets):
                _reject("Worksheet already exists", ConnectorErrorCode.CONFLICT)
            sheets[name] = dict(gid=None, name=name, engine="sheet")
            return
        sheet = sheets.get(name)
        if sheet is None or sheet["engine"] not in ("sheet", "worksheet"):
            _reject("Mutation requires an explicitly identified Sheet-engine worksheet")
        if op == "worksheet.rename":
            new = _name(args.get("name", args.get("new_name")))
            if any(s.casefold() == new.casefold() for s in sheets if s != name):
                _reject("Worksheet already exists", ConnectorErrorCode.CONFLICT)
            renamed = {
                (new if key == name else key): dict(row, name=new) if key == name else row
                for key, row in sheets.items()
            }
            sheets.clear()
            sheets.update(renamed)
        elif op == "worksheet.delete":
            sheets.pop(name)
        elif op == "worksheet.move":
            if type(args.get("index")) is not int or not 0 <= args["index"] < len(sheets):
                _reject("Worksheet index is outside the workbook", ConnectorErrorCode.INVALID_URI)
            items = list(sheets.items())
            item = next(item for item in items if item[0] == name)
            items.remove(item)
            items.insert(args["index"], item)
            sheets.clear()
            sheets.update(items)
        if op.startswith("range.") or op == "formula.set":
            try:
                if op in ("range.style", "range.format") and args.get("addresses") is not None:
                    addresses = args["addresses"]
                    if (
                        not isinstance(addresses, (list, tuple))
                        or not addresses
                        or len(addresses) > 256
                    ):
                        raise ValueError()
                    span = [_bounded_span(str(item)) for item in addresses][-1]
                    address = RangeRef(str(addresses[-1])).address
                else:
                    address = RangeRef(args.get("address", args.get("cell"))).address
                    span = _bounded_span(address)
            except (TypeError, ValueError, AttributeError):
                _reject(
                    "A bounded range of at most 10000 cells is required",
                    ConnectorErrorCode.INVALID_URI,
                )
            r, c, er, ec = span
            if op == "range.sort" and (
                type(args.get("key_column", 1)) is not int
                or not 1 <= args.get("key_column", 1) <= ec - c + 1
                or type(args.get("header", False)) is not bool
                or type(args.get("reverse", False)) is not bool
            ):
                _reject("Invalid sort key, header or direction")
            if op == "range.write":
                rows = args.get("values")
                if (
                    not isinstance(rows, (tuple, list))
                    or len(rows) != er - r + 1
                    or any(
                        not isinstance(row, (tuple, list)) or len(row) != ec - c + 1 for row in rows
                    )
                ):
                    _reject(
                        "Value matrix must match the range shape", ConnectorErrorCode.INVALID_URI
                    )
                for row in rows:
                    for value in row:
                        if value == "" or type(value) in (int, float, bool):
                            _reject(
                                "mbs RAW cannot preserve typed numbers, booleans or literal empty strings"
                            )
                        if value is not None and type(value) not in (str, int, float, bool):
                            _reject("MaybeSheet literal values support JSON scalar cells only")
                        if type(value) in (int, float) and (
                            not math.isfinite(value) or abs(value) > 2**53
                        ):
                            _reject("Numeric value exceeds exact supported precision")
                if len(json.dumps(_plain(rows)).encode()) > 8 * 1024 * 1024:
                    _reject("Value payload exceeds the supported byte limit")
            if op == "formula.set":
                expression = args.get("expression", args.get("formula"))
                if (
                    not isinstance(expression, str)
                    or not expression.startswith("=")
                    or len(expression.encode()) > 65536
                    or ":" in address
                ):
                    _reject("Formula set requires one cell and a bounded Excel expression")
            if op in ("range.style", "range.format"):
                style = {k: v for k, v in args.get("style", args).items() if v is not None}
                if args.get("reset"):
                    _reject("MaybeSheet style reset has no tested dispatch")
                keys = set(style) - {"address", "addresses", "reset", "mode"}
                if keys - {
                    "bold",
                    "italic",
                    "font_size",
                    "foreground",
                    "fill",
                    "number_format",
                    "format",
                    "pattern",
                    "kind",
                }:
                    _reject("Unsupported MaybeSheet style property")
                if "font_size" in style and (
                    type(style["font_size"]) not in (int, float)
                    or not math.isfinite(style["font_size"])
                    or style["font_size"] <= 0
                ):
                    _reject("Invalid font size")
                for k in ("bold", "italic"):
                    if k in style and type(style[k]) is not bool:
                        _reject("Invalid boolean style property")
                for k in ("foreground", "fill"):
                    if k in style and not re.fullmatch(r"#[0-9a-fA-F]{6}", style[k]):
                        _reject("Invalid style color")
        if op in ("row.height", "column.width"):
            size = args.get("height_points") if op == "row.height" else args.get("width_pixels")
            if type(size) not in (float, int) or not math.isfinite(size) or size <= 0:
                _reject("Dimensions require positive height_points or width_pixels")
            if op == "row.height":
                start = args.get("start_row", args.get("row"))
                end = args.get("end_row", start)
                if type(start) is not int or type(end) is not int or not 1 <= start <= end <= 1048576:
                    _reject("Invalid row band")
            else:
                start = args.get("start_column", args.get("column"))
                end = args.get("end_column", start)
                try:
                    first = _coordinate(str(start).upper() + "1")[1]
                    last = _coordinate(str(end).upper() + "1")[1]
                except (TypeError, ValueError):
                    _reject("Invalid column band")
                if first > last:
                    _reject("Invalid column band")
        if op in ("image.insert", "image.add"):
            if (
                args.get("mime_type") not in ("image/png", "image/jpeg")
                or not isinstance(args.get("content"), bytes)
                or not args["content"]
                or len(args["content"]) > 8 * 1024 * 1024
            ):
                _reject("Images require bounded PNG or JPEG bytes")
            try:
                _coordinate(args.get("anchor"))
            except (TypeError, ValueError):
                _reject("Image anchor must be a cell")
            if set(args) - {"mime_type", "content", "anchor", "sha256"}:
                _reject("Explicit image sizing has no tested single-command insertion contract")
        if op == "image.delete" and not args.get("picture_id"):
            _reject("Image deletion requires a stable picture_id")

    def _compile(self, binding, change, sheets, directory):
        op, name, a = change.operation_id, change.target_key, change.arguments
        uri = _mbs_target(TableURI(binding["uri"]))

        def file(value, suffix=".json"):
            path = directory / ("payload" + suffix)
            path.write_bytes(
                value
                if isinstance(value, bytes)
                else json.dumps(_plain(value), allow_nan=False).encode()
            )
            return str(path)

        group, verb = op.split(".")
        argv = ["mbs", group, verb, "--uri", uri]
        if op == "worksheet.create":
            return argv + ["--name", name, "--engine", "sheet"], op
        # Names are necessary for CLI surfaces without gid flags. Discovery pins
        # both before dispatch; stable gids are retained independently of rename.
        argv += ["--worksheet-name", name]
        if (
            group in ("worksheet", "range", "formula", "column")
            and op not in ("range.style", "range.format")
            and sheets[name].get("gid") is not None
        ):
            argv += ["--gid", str(sheets[name]["gid"])]
        if op == "worksheet.rename":
            argv += ["--new-name", a.get("name", a.get("new_name"))]
        elif op == "worksheet.delete":
            argv += ["--yes"]
        elif op == "worksheet.move":
            argv += ["--index", str(a["index"])]
        elif op.startswith("range."):
            # `batch_set_cell_style` accepts repeated ranges, so one command
            # covers every same-specification range of a report.
            for address in a.get("addresses") or [a["address"]]:
                argv += ["--range", address]
            if op == "range.merge":
                response = self._call(
                    (
                        "mbs",
                        "range",
                        "read",
                        "--uri",
                        uri,
                        "--worksheet-name",
                        name,
                        "--range",
                        a["address"],
                    ),
                    "range.read",
                )
                rows = response["result"].get("values")
                start, end = (a["address"].split(":") + [a["address"]])[:2]
                r, c = _coordinate(start)
                er, ec = _coordinate(end)
                for field in ("values", "formulas"):
                    matrix = response["result"].get(field)
                    if (
                        not isinstance(matrix, list)
                        or len(matrix) != er - r + 1
                        or any(
                            not isinstance(row, list) or len(row) != ec - c + 1 for row in matrix
                        )
                    ):
                        raise ValueError("Merge requires complete value and formula evidence")
                    if any(
                        value not in (None, "")
                        for index, row in enumerate(matrix)
                        for value in (row[1:] if index == 0 else row)
                    ):
                        raise ValueError("Merge interior contains values or formulas")
            if op == "range.sort":
                response = self._call(
                    (
                        "mbs",
                        "range",
                        "read",
                        "--uri",
                        uri,
                        "--worksheet-name",
                        name,
                        "--range",
                        a["address"],
                    ),
                    "range.read",
                )
                rows = response["result"].get("values")
                if not isinstance(rows, list) or any(not isinstance(row, list) for row in rows):
                    raise ValueError("Missing sort values")
                start, end = (a["address"].split(":") + [a["address"]])[:2]
                r, c = _coordinate(start)
                er, ec = _coordinate(end)
                for field in ("values", "formulas", "value_types"):
                    matrix = response["result"].get(field)
                    if (
                        not isinstance(matrix, list)
                        or len(matrix) != er - r + 1
                        or any(
                            not isinstance(row, list) or len(row) != ec - c + 1 for row in matrix
                        )
                    ):
                        raise ValueError(
                            "Sort requires complete formula and type evidence for every cell"
                        )
                if any(
                    any(cell not in (None, "") and type(cell) is not str for cell in row)
                    for row in rows
                ):
                    raise ValueError("Sorting typed values cannot preserve MaybeSheet RAW cells")
                if any(
                    any(cell not in (None, "") for cell in row)
                    for row in response["result"]["formulas"]
                ):
                    raise ValueError(
                        "Sorting formulas without reference translation is unsupported"
                    )
                if any(
                    any(kind not in ("string", "blank") for kind in row)
                    for row in response["result"]["value_types"]
                ):
                    raise ValueError(
                        "Sorting native typed values cannot preserve MaybeSheet RAW cells"
                    )
                rows = [[None if cell == "" else cell for cell in row] for row in rows]
                key = a.get("key_column", 1) - 1
                header = rows[:1] if a.get("header", False) else []
                body = rows[1:] if header else rows
                populated = [row for row in body if len(row) > key and row[key] not in (None, "")]
                blanks = [row for row in body if len(row) <= key or row[key] in (None, "")]
                kinds = {type(row[key]) for row in populated}
                if len(kinds) > 1:
                    raise ValueError("Mixed sort key types are unsupported")
                rows = (
                    header
                    + sorted(populated, key=lambda row: row[key], reverse=a.get("reverse", False))
                    + blanks
                )
                argv[2] = "write"
                argv += ["--values", file(rows)]
                return argv, "range.write"
            if op == "range.write":
                if ":" not in a["address"]:
                    argv[argv.index("--range") + 1] = a["address"] + ":" + a["address"]
                argv += ["--values", file(a["values"])]
            elif op == "range.clear":
                if ":" not in a["address"]:
                    argv[argv.index("--range") + 1] = a["address"] + ":" + a["address"]
                argv += ["--yes"]
            elif op in ("range.style", "range.format"):
                s = {k: v for k, v in a.get("style", a).items() if v is not None}
                # The Maybe server only honours `bg_color`; `bgcolor` and
                # `backgroundColor` are silently dropped, which leaves white
                # header text on an unpainted (invisible) header row.
                mapping = {
                    "foreground": "font_color",
                    "fill": "bg_color",
                    "number_format": "format_code",
                    "pattern": "format_code",
                }
                style = {
                    mapping.get(k, k): v
                    for k, v in s.items()
                    if k not in ("address", "addresses", "reset", "mode", "kind")
                }
                if "kind" in s:
                    style["format"] = s["kind"]
                argv[1:3] = ["style", "format"]
                argv += ["--style", file(style)]
                op = "style.format"
        elif op == "formula.set":
            argv += [
                "--cell",
                a.get("address", a.get("cell")),
                "--formula",
                a.get("expression", a.get("formula")),
                "--skip-recalculation",
            ]
        elif op == "formula.set_range":
            # One `formula/batch_set` request covers every cell in the range;
            # per-cell `formula.set` costs one provider call and one workbook
            # version each.
            operations = [
                {
                    "worksheet_name": name,
                    "range_address": str(a["address"]),
                    "formulas": [[_plain(cell) for cell in row] for row in a["formulas"]],
                }
            ]
            return (
                [
                    "mbs",
                    "range",
                    "set-formula",
                    "--uri",
                    uri,
                    "--operations",
                    file(operations),
                    "--skip-recalculation",
                ],
                "range.set-formula",
            )
        elif op == "row.height":
            argv[1:3] = ["style", "rows-height"]
            op = "style.rows-height"
            argv += [
                "--start-row",
                str(a.get("start_row", a.get("row"))),
                "--end-row",
                str(a.get("end_row", a.get("row"))),
                "--height",
                f"{a['height_points'] * 96 / 72:g}px",
            ]
        elif op == "column.width":
            argv += [
                "--start-column",
                a.get("start_column", a.get("column")),
                "--end-column",
                a.get("end_column", a.get("column")),
                "--width",
                f"{a['width_pixels']:g}px",
            ]
        elif op in ("image.insert", "image.add"):
            argv[2] = "insert"
            op = "image.insert"
            argv += [
                "--cell",
                a["anchor"],
                "--file",
                file(a["content"], ".png" if a["mime_type"] == "image/png" else ".jpg"),
            ]
        elif op == "image.delete":
            argv += ["--picture-id", str(a["picture_id"])]
        return argv, op

    def commit(
        self, binding, changes, *, allow_partial=False, expected_revision=None, idempotency_key=None
    ):
        changes = self._expand(changes)
        if expected_revision is not None or idempotency_key is not None:
            _reject("MaybeSheet workbook batches do not provide CAS or idempotency guarantees")
        plan = self.preflight(binding, changes)
        if not allow_partial and not plan["atomic"]:
            _reject(
                "MaybeSheet has no atomic multi-command transaction; explicitly allow partial effects"
            )
        sheets = {name: dict(row) for name, row in (binding.get("worksheets") or {}).items()}
        receipts = []
        created = {}
        if binding.get("copy_from"):
            # `mbs workbook copy` preserves worksheet engine topology: the new
            # workbook starts with the source's sheet tabs, base-table tabs,
            # names, gids and base-table ids, and it is a snapshot -- writes to
            # the source afterwards are not visible through it.  The copy's
            # first write re-materialises its own base tables, so base-table
            # ids change at that point; only names, gids and engines stay
            # stable.  The provider allocates the copy's document id, so the
            # session rebinds to the URI it returns rather than to the
            # requested destination.
            copy_source = str(binding["copy_from"])
            requested = str(binding.get("uri") or "")
            title = binding.get("copy_title")
            if not isinstance(title, str) or not title.strip():
                parts = [part for part in urlsplit(requested).path.split("/") if part]
                title = parts[-1] if parts else "workbook copy"
            try:
                payload = self._call(
                    ("mbs", "workbook", "copy", "--target", copy_source, "--title", title),
                    "workbook.copy",
                )
                result = payload["result"]
                receipts.append(
                    dict(
                        operation="workbook.copy",
                        request_id=payload["request_id"],
                        result=_plain(result),
                    )
                )
                document_id = result.get("new_document_id", result.get("spreadsheet_id"))
                if not isinstance(document_id, str) or not document_id:
                    raise ValueError("Copied workbook identity is missing")
                new_uri = result.get("new_uri")
                if not isinstance(new_uri, str) or not new_uri:
                    new_uri = f"{SCHEME_HTTPS}://{HOST_MAYBE}/docs/spreadsheets/d/{document_id}"
                created["workbook"] = document_id
                binding["uri"] = new_uri
                binding["copy_from"] = None
                binding["copy_title"] = None
                sheets = self._list(binding)
                binding["worksheets"] = sheets
            except Exception:
                # The copy may or may not have landed; the caller must reconcile
                # or rebind instead of repeating the mutation blindly.
                return dict(
                    outcome="unknown",
                    commit="unknown",
                    verification="unavailable",
                    receipts=tuple(receipts),
                    value=dict(
                        created_ids=created,
                        unknown_operation="workbook.copy",
                        requires_rebind=True,
                    ),
                )
        if binding.get("new"):
            try:
                payload = self._call(
                    (
                        "mbs",
                        "workbook",
                        "create",
                        "--title",
                        urlsplit(binding["uri"]).netloc,
                        "--sheet-name",
                        "Sheet1",
                        "--engine",
                        "sheet",
                    ),
                    "workbook.create",
                )
                result = payload["result"]
                document_id = result.get("spreadsheet_id", result.get("document_id"))
                receipts.append(
                    dict(
                        operation="workbook.create",
                        request_id=payload["request_id"],
                        result=_plain(result),
                    )
                )
                if not isinstance(document_id, str) or not document_id:
                    raise ValueError("Missing document identity")
                created["workbook"] = document_id
                binding["uri"] = f"{SCHEME_HTTPS}://{HOST_MAYBE}/docs/spreadsheets/d/{document_id}"
                binding["new"] = False
                sheets = self._list(binding)
                binding["worksheets"] = sheets
            except Exception:
                return dict(
                    outcome="unknown",
                    commit="unknown",
                    verification="unavailable",
                    receipts=tuple(receipts),
                    value=dict(
                        created_ids=created,
                        unknown_operation="workbook.create",
                        requires_rebind=True,
                    ),
                )
        for change in changes:
            dispatched = False
            try:
                with tempfile.TemporaryDirectory(prefix="otc-mbs-sheet-") as directory:
                    argv, operation = self._compile(binding, change, sheets, Path(directory))
                    dispatched = True
                    payload = self._call(argv, operation)
                result = payload["result"]
                receipts.append(
                    dict(
                        operation=change.operation_id,
                        request_id=payload["request_id"],
                        result=_plain(result),
                    )
                )
                if change.operation_id == "worksheet.create":
                    gid = result.get("gid", result.get("id"))
                    if gid is None and isinstance(result.get("worksheet"), Mapping):
                        gid = result["worksheet"].get("gid", result["worksheet"].get("id"))
                    if gid is None and isinstance(result.get("spreadsheet_url"), str):
                        returned_url = urlsplit(result["spreadsheet_url"])
                        bound_url = urlsplit(_mbs_target(TableURI(binding["uri"])))
                        if (
                            returned_url.hostname == bound_url.hostname
                            and returned_url.path == bound_url.path
                        ):
                            gids = parse_qs(returned_url.query).get("gid", [])
                            if len(gids) == 1 and gids[0].isdigit():
                                gid = gids[0]
                    if gid is None:
                        _reject(
                            "Creation response omitted the created worksheet identity",
                            ConnectorErrorCode.EXECUTION_FAILED,
                        )
                    created[change.target_key] = str(gid)
                self._validate(change, sheets)
                if change.target_key in created:
                    sheets[change.target_key]["gid"] = created[change.target_key]
            except Exception:
                return dict(
                    outcome="unknown" if dispatched else "failed",
                    commit="unknown" if dispatched else "partial" if receipts else "not_committed",
                    verification="unavailable",
                    receipts=tuple(receipts),
                    value=dict(
                        created_ids=created,
                        unknown_operation=change.operation_id,
                        requires_rebind=True,
                    ),
                )
        if isinstance(binding, dict):
            binding["worksheets"] = sheets
        return dict(
            outcome="succeeded",
            commit="committed",
            verification="unavailable",
            receipts=tuple(receipts),
            value=dict(created_ids=created, observation="remote_acknowledgment"),
        )

    def observe(self, binding, selector):
        if selector.get("changes") and selector.get("operation") != "workbook.reconcile":
            _reject("MaybeSheet pending overlays are unavailable; commit before reading")
        operation = selector.get("operation", "worksheet.list")
        if operation == "workbook.reconcile":
            sheets = self._list(binding)
            return dict(
                value=dict(
                    worksheets=tuple(sheets.values()), observation="committed", requires_rebind=True
                ),
                resolved=False,
                verification="unavailable",
                receipts=(),
            )
        sheets = self._checked_sheets(self._topology_binding(binding))
        if operation in ("worksheet.list", "workbook.verify", "verify", "reconcile"):
            return dict(
                value=dict(
                    worksheets=tuple(sheets.values()),
                    observation="committed",
                    requires_rebind=operation == "reconcile",
                ),
                verification="unavailable",
                receipts=(),
            )
        name = selector.get("target_key", selector.get("sheet"))
        if name not in sheets or sheets[name]["engine"] not in ("sheet", "worksheet"):
            _reject("Observation requires an explicitly identified Sheet worksheet")
        if operation in ("range.style.read", "worksheet.config.read"):
            return self._observe_layout(binding, name, sheets[name], selector, operation)
        if operation not in ("range.read", "formula.read", "image.list", "image.read"):
            _reject("Unsupported MaybeSheet observation")
        group, verb = operation.split(".")
        argv = [
            "mbs",
            group,
            verb,
            "--uri",
            _mbs_target(TableURI(binding["uri"])),
            "--worksheet-name",
            name,
        ]
        if operation in ("range.read", "formula.read"):
            try:
                address = RangeRef(selector["address"]).address
            except (KeyError, TypeError, ValueError):
                _reject("Observation requires a bounded A1 range")
            first, last = (address.split(":") + [address])[:2]
            r, c = _coordinate(first)
            er, ec = _coordinate(last)
            if er < r or ec < c or (er - r + 1) * (ec - c + 1) > 10000:
                _reject("Observation range exceeds 10000 cells")
            argv += ["--range", address]
        elif operation == "image.read":
            argv += ["--picture-id", str(selector["picture_id"]), "--include-base64"]
        payload = self._call(argv, operation)
        return dict(
            value=dict(payload["result"], observation="committed"),
            verification="unavailable",
            receipts=(),
        )

    def _read_layout(self, binding, name, address):
        """Read the model once; every layout observation is built from this."""

        payload = self._call(
            (
                "mbs",
                "range",
                "read",
                "--uri",
                _mbs_target(TableURI(binding["uri"])),
                "--worksheet-name",
                name,
                "--range",
                address,
            ),
            "range.read",
        )
        result = payload["result"]
        if not isinstance(result, Mapping):
            _reject("Invalid MaybeSheet layout read evidence", ConnectorErrorCode.EXECUTION_FAILED)
        return result

    def _observe_layout(self, binding, name, sheet, selector, operation):
        """Read back persisted physical layout, never a write acknowledgement."""

        target = {
            "provider": PROVIDER_MAYBE_SHEET,
            "resource": binding["uri"],
            "worksheet_id": str(sheet["gid"]),
        }
        if operation == "range.style.read":
            try:
                address = RangeRef(selector["address"]).address
                start, end = _coordinate_bounds(address)
            except (KeyError, TypeError, ValueError):
                _reject("Observation requires a bounded A1 range")
            requested = selector.get("fields")
            fields = list(STYLE_FIELDS if requested is None else requested)
            if (
                not fields
                or len(set(fields)) != len(fields)
                or any(not isinstance(field, str) or field not in STYLE_FIELDS for field in fields)
            ):
                _reject("MaybeSheet cannot read that style field")
            if (end[0] - start[0] + 1) * (end[1] - start[1] + 1) > 10000:
                _reject("Observation range exceeds 10000 cells")
            result = self._read_layout(binding, name, address)
            try:
                observation = style_observation(
                    target=target,
                    address=address,
                    start=start,
                    end=end,
                    result=result,
                    fields=fields,
                )
            except (TypeError, ValueError) as exc:
                _reject(
                    f"MaybeSheet style observation failed: {exc}",
                    ConnectorErrorCode.EXECUTION_FAILED,
                )
        else:
            try:
                rows = sorted({int(row) for row in selector["rows"]})
                columns = sorted(
                    {str(column).upper() for column in selector["columns"]},
                    key=lambda item: _coordinate(item + "1")[1],
                )
            except (KeyError, TypeError, ValueError):
                _reject("Configuration observation requires rows and columns")
            if not rows or not columns or any(not 1 <= row <= 1048576 for row in rows):
                _reject("Configuration observation rows are invalid")
            for column in columns:
                if not re.fullmatch(r"[A-Z]{1,3}", column):
                    _reject("Configuration observation columns are invalid")
                _coordinate(column + "1")
            address = (
                f"{columns[0]}{rows[0]}:{columns[-1]}{rows[-1]}"
            )
            if rows[0] < 1 or _coordinate(columns[-1] + "1")[1] > 16384:
                _reject("Configuration observation is outside the worksheet bounds")
            start = (rows[0], _coordinate(columns[0] + "1")[1])
            end = (rows[-1], _coordinate(columns[-1] + "1")[1])
            if (end[0] - start[0] + 1) * (end[1] - start[1] + 1) > 10000:
                _reject("Observation range exceeds 10000 cells")
            result = self._read_layout(binding, name, address)
            try:
                observation = config_observation(
                    target=target, rows=rows, columns=columns, result=result
                )
            except (TypeError, ValueError) as exc:
                _reject(
                    f"MaybeSheet configuration observation failed: {exc}",
                    ConnectorErrorCode.EXECUTION_FAILED,
                )
        try:
            decoded = decode_maybe_layout(
                observation, target=target, selector=selector, descriptor=LAYOUT_DESCRIPTOR
            )
        except (TypeError, ValueError) as exc:
            _reject(
                f"MaybeSheet layout observation failed: {exc}",
                ConnectorErrorCode.EXECUTION_FAILED,
            )
        return dict(value=decoded, verification="unavailable", receipts=())
