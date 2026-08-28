"""Executable entrypoint for the Open Table Connector CLI."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Sequence

from .commands import run_command
from .output import emit_error
from .registry import build_default_registry


_FORMATS = ("auto", "csv", "excel", "json", "jsonl", "table")
_OUTPUT_FORMATS = ("csv", "json", "jsonl", "table")
_PARSER_FLAGS = frozenset(
    {
        "--from",
        "--to",
        "--from-format",
        "--to-format",
        "--output-format",
        "--if-exists",
        "--limit",
        "--timeout",
        "--sheet",
        "--range",
        "--field-name",
        "--token",
        "--target",
    }
)
_KNOWN_VALUES = (*_FORMATS, "append", "replace", "error")


class _ParserError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _ParserError(message)


def _safe_parser_details(message: str) -> dict[str, list[str]]:
    flags = list(
        dict.fromkeys(
            flag for flag in re.findall(r"--[a-z][a-z0-9-]*", message) if flag in _PARSER_FLAGS
        )
    )
    values = [
        value
        for value in _KNOWN_VALUES
        if re.search(rf"\b{re.escape(value)}\b", message)
    ]
    details: dict[str, list[str]] = {}
    if flags:
        details["flags"] = flags
    if values:
        details["values"] = values
    return details


def _emit_parser_error(message: str) -> None:
    payload = {
        "code": "usage",
        "message": "invalid command input",
        "safe_details": _safe_parser_details(message),
    }
    sys.stderr.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")


def _add_options(parser: argparse.ArgumentParser, *, require_from: bool, require_to: bool) -> None:
    parser.add_argument("--from", dest="from_value", required=require_from, metavar="SOURCE")
    parser.add_argument("--to", dest="to_value", required=require_to, metavar="DESTINATION")
    parser.add_argument("--from-format", choices=_FORMATS, default=None)
    parser.add_argument("--to-format", choices=_FORMATS, default=None)
    parser.add_argument("--output-format", choices=_OUTPUT_FORMATS, default="jsonl")
    parser.add_argument("--if-exists", choices=("append", "replace", "error"), default="error")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--sheet")
    parser.add_argument("--range")
    parser.add_argument("--field-name", action="append", default=None)
    parser.add_argument("--token")
    parser.add_argument("--target")


def build_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(prog="otc", description="Move and inspect tables through Open Connectors.")
    subparsers = parser.add_subparsers(dest="command", required=True, parser_class=_ArgumentParser)

    list_parser = subparsers.add_parser("list", help="list available connectors")
    list_parser.add_argument("--output-format", choices=_OUTPUT_FORMATS, default="jsonl")
    inspect_parser = subparsers.add_parser("inspect", help="inspect a table")
    _add_options(inspect_parser, require_from=True, require_to=False)
    read_parser = subparsers.add_parser("read", help="read a table")
    _add_options(read_parser, require_from=True, require_to=False)
    convert_parser = subparsers.add_parser("convert", help="convert a table to a local destination")
    _add_options(convert_parser, require_from=True, require_to=True)
    import_parser = subparsers.add_parser("import", help="import a table into a connector")
    _add_options(import_parser, require_from=True, require_to=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except _ParserError as error:
        _emit_parser_error(error.message)
        sys.stderr.flush()
        return 2
    except SystemExit as error:
        return int(error.code)

    try:
        registry = build_default_registry(env=os.environ)
        result = run_command(args, registry, sys.stdout, sys.stderr)
        sys.stdout.flush()
        sys.stderr.flush()
        return result
    except Exception as error:
        return emit_error(error, sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_parser", "main"]
