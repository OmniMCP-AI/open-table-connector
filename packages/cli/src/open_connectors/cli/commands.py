"""Command handlers for the OTC CLI."""

from __future__ import annotations

from argparse import Namespace
from typing import Any, TextIO

from .model import CliOptions, FormatName, parse_endpoint, parse_format
from .output import _wire, emit_error, emit_read, emit_summary
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
    return CliOptions(
        from_format=parse_format(getattr(args, "from_format", None)),
        to_format=parse_format(getattr(args, "to_format", None)),
        output_format=parse_format(getattr(args, "output_format", None)),
        if_exists=getattr(args, "if_exists", "error"),
        limit=getattr(args, "limit", None),
        timeout=getattr(args, "timeout", None),
        sheet=getattr(args, "sheet", None),
        range=getattr(args, "range", None),
        field_names=field_names,
        token=getattr(args, "token", None),
        target=getattr(args, "target", None),
    )


def _manifest(adapter: Any) -> tuple[Any, tuple[Any, ...], tuple[Any, ...], tuple[str, ...]]:
    manifest = getattr(getattr(adapter, "connector", None), "manifest", None)
    capabilities = tuple(getattr(manifest, "capabilities", getattr(adapter, "capabilities", ())))
    modes = tuple(getattr(manifest, "modes", getattr(adapter, "modes", ())))
    schemes = tuple(getattr(manifest, "uri_schemes", getattr(adapter, "schemes", ())))
    return manifest, capabilities, modes, schemes


def _emit_list(registry: ConnectorRegistry, out: TextIO) -> None:
    for adapter in registry.list():
        manifest, capabilities, modes, schemes = _manifest(adapter)
        identity = getattr(manifest, "connector", getattr(adapter, "identity", None))
        _emit_json({
            "connector_id": identity.connector_id,
            "schemes": list(schemes),
            "capabilities": [_wire_item(item) for item in capabilities],
            "modes": [_wire_item(item) for item in modes],
        }, out)


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
            _emit_list(registry, out)
            return 0
        options = _options(args)
        source = parse_endpoint(getattr(args, "from_value"))
        if command == "inspect":
            inspection = inspect_endpoint(source, registry, options)
            _emit_json({
                "safe_uri": _wire_item(inspection.safe_uri),
                "mode": _wire_item(inspection.mode),
                "columns": list(inspection.columns),
                "schema_fingerprint": inspection.schema_fingerprint,
                "row_count": inspection.row_count,
                "coordinate_convention": _wire(inspection.coordinate_convention),
                "facts": _wire(dict(inspection.facts)),
            }, out)
        elif command == "read":
            result = read_endpoint(source, registry, options)
            emit_read(result, options.output_format, out)
        elif command in ("convert", "import"):
            destination = parse_endpoint(getattr(args, "to_value"))
            summary = (convert_endpoint if command == "convert" else import_endpoint)(
                source, destination, registry, options
            )
            emit_summary(summary, out)
        else:
            raise ValueError("unsupported command")
        return 0
    except Exception as error:
        return emit_error(error, err)


__all__ = ["run_command"]
