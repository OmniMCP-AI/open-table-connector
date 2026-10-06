"""Typed spreadsheet command shortcuts compiled to SDK requests."""

from __future__ import annotations

import json
import re
from argparse import Namespace
from typing import Any

from open_table_connector.contract import OperationRequest, TargetSelector, read_json_input

_CELL = re.compile(r"^([A-Za-z]+)([1-9][0-9]*)$")


def _column_number(value: str) -> int:
    result = 0
    for character in value.upper():
        result = result * 26 + ord(character) - 64
    return result


def _shape(address: str) -> tuple[int, int]:
    parts = address.split(":")
    if len(parts) not in {1, 2}:
        raise ValueError("range must be a single cell or rectangle")
    first = _CELL.fullmatch(parts[0])
    second = _CELL.fullmatch(parts[-1])
    if first is None or second is None:
        raise ValueError("range must use A1 notation")
    rows = int(second.group(2)) - int(first.group(2)) + 1
    columns = _column_number(second.group(1)) - _column_number(first.group(1)) + 1
    if rows < 1 or columns < 1:
        raise ValueError("range coordinates must be ordered")
    return rows, columns


def _values(args: Namespace) -> Any:
    source = getattr(args, "values_file", None)
    if source is not None:
        try:
            value = read_json_input(source)
        except Exception as exc:
            raise ValueError("values file is invalid") from exc
    else:
        raw = getattr(args, "values", None)
        if raw is None:
            raise ValueError("write requires --values-file or --values")
        if isinstance(raw, str):
            try:
                value = json.loads(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError("values must be JSON") from exc
        else:
            value = raw
    if not isinstance(value, list) or not value or any(not isinstance(row, list) for row in value):
        raise ValueError("values must be a non-empty two-dimensional array")
    width = len(value[0])
    if width == 0 or any(len(row) != width for row in value):
        raise ValueError("values must be rectangular")
    expected = _shape(args.range)
    if expected != (len(value), width):
        raise ValueError("values dimensions do not match range dimensions")
    return value


def compile_shortcut(args: Namespace) -> OperationRequest:
    action = getattr(args, "action", None)
    uri = getattr(args, "uri", None)
    sheet = getattr(args, "sheet", None)
    if not isinstance(uri, str) or not uri.strip() or not isinstance(sheet, str) or not sheet.strip():
        raise ValueError("shortcut requires --uri and --sheet")
    target = TargetSelector(uri, sheet)
    arguments: dict[str, object] = {}
    operation_id: str
    if action == "style":
        operation_id = "range.style"
        if not getattr(args, "range", None):
            raise ValueError("style requires --range")
        arguments["address"] = args.range
        for name in ("bold", "italic"):
            positive = getattr(args, name, None)
            negative = bool(getattr(args, f"no_{name}", False))
            if positive is not None and negative:
                raise ValueError(f"conflicting {name} flags")
            if negative:
                arguments[name] = False
            elif positive is not None:
                arguments[name] = bool(positive)
    elif action == "format":
        operation_id = "range.format"
        if not getattr(args, "range", None) or getattr(args, "pattern", None) is None:
            raise ValueError("format requires --range and --pattern")
        arguments.update(address=args.range, pattern=args.pattern)
    elif action == "write":
        operation_id = "range.write"
        if not getattr(args, "range", None):
            raise ValueError("write requires --range")
        arguments.update(address=args.range, values=_values(args))
    elif action == "worksheet":
        worksheet_action = getattr(args, "worksheet_action", None)
        if worksheet_action not in {"create", "rename", "delete"}:
            raise ValueError("worksheet requires create, rename or delete")
        operation_id = f"worksheet.{worksheet_action}"
        if worksheet_action in {"create", "rename"}:
            name = getattr(args, "name", None)
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f"worksheet {worksheet_action} requires --name")
            arguments["name"] = name
    else:
        raise ValueError("unsupported spreadsheet shortcut")
    return OperationRequest("spreadsheet", operation_id, "1.0", target, arguments)


__all__ = ["compile_shortcut"]
