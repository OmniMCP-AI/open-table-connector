"""Command handlers for the OTC CLI."""

from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
from typing import Any, TextIO

from .model import CliOptions, FormatName, parse_endpoint, parse_format
from .output import (
    _wire,
    emit_error,
    emit_read,
    emit_record,
    emit_records,
    emit_summary,
)
from .pipeline import convert_endpoint, import_endpoint, inspect_endpoint, read_endpoint
from .registry import ConnectorRegistry


def _options(args: Namespace) -> CliOptions:
    field_name = getattr(args, "field_name", None)
    if field_name is None:
        field_names = ()
    elif isinstance(field_name, str):
        field_names = (field_name,)
    else:
        field_names = tuple(field_name)
    command = getattr(args, "command", None)
    output_default = FormatName.JSONL
    raw_output = getattr(args, "output_format", None)
    raw_to = getattr(args, "to_format", None)
    output_format = _format(args, "output_format", output_default)
    to_format = _format(args, "to_format", FormatName.AUTO)
    # Preserve the pre-`--to-format` API for callers constructing a Namespace
    # directly. The parser always supplies a `to_format` attribute for modern
    # convert calls, so --output-format remains a stdout-only setting there.
    if command == "convert" and raw_to is None and raw_output is not None:
        to_format, output_format = output_format, FormatName.JSONL
    return CliOptions(
        from_format=_format(args, "from_format", FormatName.AUTO),
        output_format=output_format,
        to_format=to_format,
        if_exists=getattr(args, "if_exists", "error"),
        limit=getattr(args, "limit", None),
        timeout=getattr(args, "timeout", None),
        sheet=getattr(args, "sheet", None),
        range=getattr(args, "range", None),
        field_names=field_names,
        token=getattr(args, "token", None),
        target=getattr(args, "target", None),
    )


def _format(args: Namespace, name: str, default: FormatName) -> FormatName:
    value = getattr(args, name, None)
    return parse_format(default.value if value is None else value)


def _manifest(adapter: Any) -> tuple[Any, tuple[Any, ...], tuple[Any, ...], tuple[str, ...]]:
    manifest = getattr(getattr(adapter, "connector", None), "manifest", None)
    capabilities = tuple(getattr(manifest, "capabilities", getattr(adapter, "capabilities", ())))
    modes = tuple(getattr(manifest, "modes", getattr(adapter, "modes", ())))
    schemes = tuple(getattr(manifest, "uri_schemes", getattr(adapter, "schemes", ())))
    return manifest, capabilities, modes, schemes


def _emit_list(
    registry: ConnectorRegistry, out: TextIO, output_format: FormatName = FormatName.JSONL
) -> None:
    payloads = []
    for adapter in registry.list():
        if hasattr(adapter, "descriptor"):
            adapter = adapter.descriptor
        if hasattr(adapter, "identity") and hasattr(adapter, "schemes"):
            manifest = None
            capabilities = tuple(getattr(adapter, "capabilities", ()))
            modes = tuple(getattr(adapter, "modes", ()))
            schemes = tuple(getattr(adapter, "schemes", ()))
            identity = adapter.identity
        else:
            manifest, capabilities, modes, schemes = _manifest(adapter)
            identity = getattr(manifest, "connector", getattr(adapter, "identity", None))
        payload = {
            "connector_id": identity.connector_id,
            "schemes": list(schemes),
            "capabilities": [_wire_item(item) for item in capabilities],
            "modes": [_wire_item(item) for item in modes],
        }
        payloads.append(payload)
    emit_records(
        payloads,
        output_format,
        out,
        headers=("connector_id", "schemes", "capabilities", "modes"),
    )


def _wire_item(value: Any) -> Any:
    to_wire = getattr(value, "to_wire", None)
    if callable(to_wire):
        return to_wire()
    return getattr(value, "value", value)


def _emit_json(payload: Any, out: TextIO) -> None:
    import json
    out.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def run_command(args: Namespace, registry: ConnectorRegistry, out: TextIO, err: TextIO) -> int:
    try:
        command = getattr(args, "command", None)
        if command == "list":
            _emit_list(registry, out, _format(args, "output_format", FormatName.JSONL))
            return 0
        options = _options(args)
        source = parse_endpoint(args.from_value)
        if command == "inspect":
            inspection = inspect_endpoint(source, registry, options)
            payload = {
                "safe_uri": _wire_item(inspection.safe_uri),
                "mode": _wire_item(inspection.mode),
                "columns": list(inspection.columns),
                "schema_fingerprint": inspection.schema_fingerprint,
                "row_count": inspection.row_count,
                "coordinate_convention": _wire(inspection.coordinate_convention),
                "facts": _wire(dict(inspection.facts)),
            }
            emit_record(payload, options.output_format, out)
        elif command == "read":
            result = read_endpoint(source, registry, options)
            emit_read(result, options.output_format, out)
        elif command in ("convert", "import"):
            destination = parse_endpoint(args.to_value)
            operation = convert_endpoint if command == "convert" else import_endpoint
            if command == "convert" and destination.is_stdio:
                with redirect_stdout(out):
                    summary = operation(source, destination, registry, options)
            else:
                summary = operation(source, destination, registry, options)
            # A conversion to stdio owns stdout for its selected codec. A JSON
            # summary there would corrupt JSON, JSONL, CSV, and table streams.
            if not (command == "convert" and destination.is_stdio):
                summary_format = options.output_format
                emit_summary(summary, out, summary_format)
        else:
            raise ValueError("unsupported command")
        return 0
    except Exception as error:
        return emit_error(error, err)


__all__ = ["run_command"]
