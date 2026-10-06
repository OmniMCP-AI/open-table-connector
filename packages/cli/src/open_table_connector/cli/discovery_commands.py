"""CLI commands backed by the SDK operation catalog."""

from __future__ import annotations

import json
from difflib import get_close_matches
from typing import TextIO

from open_table_connector.contract import FORMAT_TABLE, PROVIDER_JSON
from open_table_connector.sdk import Client
from open_table_connector.sdk.discovery import OperationCatalog, resolve_capabilities


def _emit(payload, output_format: str, out: TextIO) -> None:
    if output_format == PROVIDER_JSON:
        out.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
        return
    if isinstance(payload, dict) and "operations" not in payload:
        out.write("operation_id\tversion\tcapability\teffects\n")
        out.write(f"{payload.get('operation_id')}\t{payload.get('version')}\t{payload.get('capability')}\t{','.join(payload.get('effects', ())) }\n")
        return
    out.write("operation_id\tversion\tcapability\teffects\n")
    for item in payload.get("operations", ()):
        out.write(f"{item['operation_id']}\t{item['version']}\t{item['capability']}\t{','.join(item['effects'])}\n")


def suggest_argument(name: str, descriptor) -> tuple[str, ...]:
    """Suggest only declared schema properties, never values or provider text."""

    candidate = str(name).split("=", 1)[0].removeprefix("--")
    properties = tuple(str(item) for item in descriptor.arguments_schema.get("properties", {}))
    return tuple(get_close_matches(candidate, properties, n=3, cutoff=0.5))


def run_discovery_command(args, out: TextIO, err: TextIO, *, catalog: OperationCatalog | None = None, registry=None) -> int:
    selected = catalog or OperationCatalog.default()
    output_format = getattr(args, "output_format", FORMAT_TABLE)
    if args.command == "help":
        descriptors = selected.describe(args.namespace, getattr(args, "operation_id", None))
        if not descriptors:
            err.write(json.dumps({"code": "usage", "message": "unknown operation"}) + "\n")
            return 2
        if getattr(args, "operation_id", None):
            _emit(descriptors[0].to_wire(), output_format, out)
        else:
            _emit({"namespace": args.namespace, "operations": [item.to_wire() for item in descriptors]}, output_format, out)
        return 0
    if registry is None:
        from .registry import build_default_registry

        registry = build_default_registry(env={})
    target = args.uri
    result = resolve_capabilities(Client(registry=registry), target if getattr(args, "sheet", None) is None else {"uri": target, "sheet": args.sheet}, catalog=selected)
    if result.outcome.value != "succeeded":
        err.write(json.dumps(result.to_wire(), ensure_ascii=False, default=str) + "\n")
        return 5
    _emit(result.require_value().to_wire(), output_format, out)
    return 0


__all__ = ["run_discovery_command", "suggest_argument"]
