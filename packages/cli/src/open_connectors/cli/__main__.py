"""Executable entrypoint for the Open Table Connector CLI."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

from .commands import run_command
from .output import emit_error
from .registry import build_default_registry


_FORMATS = ("auto", "csv", "json", "jsonl", "table")


def _add_options(parser: argparse.ArgumentParser, *, require_from: bool, require_to: bool) -> None:
    parser.add_argument("--from", dest="from_value", required=require_from, metavar="SOURCE")
    parser.add_argument("--to", dest="to_value", required=require_to, metavar="DESTINATION")
    parser.add_argument("--from-format", choices=_FORMATS, default=None)
    parser.add_argument("--to-format", choices=_FORMATS, default=None)
    parser.add_argument("--output-format", choices=_FORMATS, default="jsonl")
    parser.add_argument("--if-exists", choices=("append", "replace", "error"), default="error")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--sheet")
    parser.add_argument("--range")
    parser.add_argument("--field-name", action="append", default=None)
    parser.add_argument("--token")
    parser.add_argument("--target")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="otc", description="Move and inspect tables through Open Connectors.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="list available connectors")
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
