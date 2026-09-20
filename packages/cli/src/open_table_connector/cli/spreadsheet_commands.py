"""Workbook commands through the same buffered SDK surface as Python callers."""

from __future__ import annotations

import base64
import binascii
import json
from pathlib import Path

from .model import parse_endpoint
from .output import CliUsageError

_MAX_INPUT = 16 * 1024 * 1024


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "spreadsheet", help="buffer, save, read and verify workbook operations"
    )
    parser.add_argument("action", choices=("batch", "operation", "read", "style-read", "config-read", "verify", "inspect"))
    parser.add_argument("--uri", required=True)
    parser.add_argument("--commands", help="version 1.0 JSON command file")
    parser.add_argument("--operation", help="existing spreadsheet operation verb")
    parser.add_argument("--arguments", default="{}", help="operation arguments as JSON")
    parser.add_argument("--sheet")
    parser.add_argument("--range")
    parser.add_argument("--fields", help="style fields as a JSON array")
    parser.add_argument("--rows", help="row numbers as a JSON array")
    parser.add_argument("--columns", help="column letters as a JSON array")
    parser.add_argument("--view-fields", help="view fields as a JSON array")
    parser.add_argument("--create", action="store_true")
    parser.add_argument("--profile", choices=("general/1.0", "literal-artifact/1.0"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--expected", help="retained independent expected intent JSON file")
    parser.add_argument("--expected-revision")
    parser.add_argument("--idempotency-key")
    parser.add_argument("--failure-directory")
    parser.add_argument("--credential-key", action="append", default=[])


def _json(text):
    if len(text.encode("utf-8")) > _MAX_INPUT:
        raise CliUsageError("workbook command input exceeds 16 MiB")

    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise CliUsageError("duplicate JSON property")
            value[key] = item
        return value

    def nonfinite(_):
        raise CliUsageError("non-finite JSON number")

    try:
        return json.loads(text, object_pairs_hook=unique, parse_constant=nonfinite)
    except (ValueError, TypeError) as exc:
        raise CliUsageError("invalid workbook command JSON") from exc


def _read_json(path):
    with Path(path).open("rb") as stream:
        data = stream.read(_MAX_INPUT + 1)
    if len(data) > _MAX_INPUT:
        raise CliUsageError("workbook command input exceeds 16 MiB")
    try:
        return _json(data.decode("utf-8"))
    except UnicodeError as exc:
        raise CliUsageError("workbook command file must be UTF-8") from exc


def _changes(args):
    if args.action == "batch":
        if not args.commands:
            raise CliUsageError("batch requires --commands")
        payload = _read_json(args.commands)
        if (
            not isinstance(payload, dict)
            or set(payload) != {"version", "changes"}
            or payload["version"] != "1.0"
        ):
            raise CliUsageError("command file requires version 1.0 and changes")
        changes = payload["changes"]
        if not isinstance(changes, list) or len(changes) > 10_000:
            raise CliUsageError("changes must be a list of at most 10000 operations")
    elif args.action == "operation":
        if not args.operation or not args.sheet:
            raise CliUsageError("operation requires --operation and --sheet")
        changes = [
            {
                "operation_id": args.operation,
                "target_key": args.sheet,
                "arguments": _json(args.arguments),
            }
        ]
    else:
        return ()
    for item in changes:
        if not isinstance(item, dict) or set(item) != {"operation_id", "target_key", "arguments"}:
            raise CliUsageError("change requires operation_id, target_key and arguments")
        if not all(
            isinstance(item[key], str) and item[key].strip()
            for key in ("operation_id", "target_key")
        ) or not isinstance(item["arguments"], dict):
            raise CliUsageError("invalid change arguments or target")
        if item["operation_id"] in {
            "range.read",
            "worksheet.list",
            "workbook.verify",
            "workbook.write",
        }:
            raise CliUsageError("batch accepts buffered mutations only")
        if item["operation_id"] == "image.insert" and "content_base64" in item["arguments"]:
            arguments = dict(item["arguments"])
            if "content" in arguments:
                raise CliUsageError("image content must have one encoding")
            encoded = arguments.pop("content_base64")
            if not isinstance(encoded, str):
                raise CliUsageError("image content_base64 must be a string")
            try:
                arguments["content"] = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise CliUsageError("image content_base64 is invalid") from exc
            item["arguments"] = arguments
    return changes


def _json_array(text, name):
    if text is None:
        return None
    value = _json(text)
    if not isinstance(value, list) or not value or any(isinstance(item, (dict, list)) for item in value):
        raise CliUsageError(f"{name} must be a non-empty JSON array of scalars")
    return value


def run_spreadsheet(args, registry, out, err):
    from open_table_connector.sdk import Client, ConnectorRegistry, OTCError
    from open_table_connector.sdk.workbook import WorkbookSession

    changes = _changes(args)
    requested_fields = _json_array(args.fields, "--fields") if args.action == "style-read" else None
    requested_rows = _json_array(args.rows, "--rows") if args.action == "config-read" else None
    requested_columns = _json_array(args.columns, "--columns") if args.action == "config-read" else None
    requested_view_fields = _json_array(args.view_fields, "--view-fields") if args.action == "config-read" else None
    if args.action == "style-read" and (not args.sheet or not args.range):
        raise CliUsageError("style-read requires --sheet and --range")
    if args.action == "config-read" and (not args.sheet or requested_rows is None or requested_columns is None):
        raise CliUsageError("config-read requires --sheet, --rows and --columns")
    if requested_rows is not None and any(type(row) is not int or row < 1 for row in requested_rows):
        raise CliUsageError("--rows must contain positive integers")
    if requested_columns is not None and any(not isinstance(column, str) for column in requested_columns):
        raise CliUsageError("--columns must contain column strings")
    endpoint = parse_endpoint(args.uri)
    if endpoint.is_stdio:
        raise CliUsageError("workbook requires a URI or filesystem path")
    target = endpoint.uri.value if endpoint.uri is not None else endpoint.path.resolve().as_uri()
    expected = _read_json(args.expected) if args.expected else None
    profile = args.profile or (
        "literal-artifact/1.0" if args.create and target.startswith("file:") else "general/1.0"
    )
    with registry.open_adapter(endpoint) as adapter, Client(registry=ConnectorRegistry()) as client:
        provider_factory = getattr(adapter, "spreadsheet_provider", None)
        if not callable(provider_factory):
            provider_factory = getattr(
                getattr(adapter, "connector", None), "spreadsheet_provider", None
            )
        if not callable(provider_factory):
            raise CliUsageError("provider does not support buffered workbook commands")
        try:
            with WorkbookSession(
                client,
                provider_factory(),
                target,
                new=args.create,
                profile=profile,
                failure_directory=args.failure_directory,
            ) as book:
                for change in changes:
                    book._queue(change["operation_id"], change["target_key"], change["arguments"])
                if args.action in {"batch", "operation"}:
                    result = book.write(
                        dry_run=args.dry_run,
                        allow_partial=args.allow_partial,
                        expected_revision=args.expected_revision,
                        idempotency_key=args.idempotency_key,
                    )
                elif args.action == "read":
                    if not args.sheet or not args.range:
                        raise CliUsageError("read requires --sheet and --range")
                    result = book.worksheet(args.sheet).range(args.range).read()
                elif args.action == "style-read":
                    if not args.sheet or not args.range:
                        raise CliUsageError("style-read requires --sheet and --range")
                    result = book.worksheet(args.sheet).range(args.range).read_style(fields=requested_fields)
                elif args.action == "config-read":
                    if not args.sheet or args.rows is None or args.columns is None:
                        raise CliUsageError("config-read requires --sheet, --rows and --columns")
                    result = book.worksheet(args.sheet).read_config(
                        rows=requested_rows, columns=requested_columns, view_fields=requested_view_fields
                    )
                elif args.action == "verify":
                    result = book.verify(expected)
                else:
                    result = book.inspect()
                out.write(json.dumps(result.to_wire(), ensure_ascii=False, allow_nan=False) + "\n")
            return 0
        except OTCError as exc:
            err.write(json.dumps(exc.result.to_wire(), ensure_ascii=False, allow_nan=False) + "\n")
            return 5
