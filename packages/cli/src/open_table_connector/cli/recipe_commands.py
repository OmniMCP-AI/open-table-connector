"""CLI facade for observed spreadsheet recipes."""

from __future__ import annotations

import json

from open_table_connector.contract import read_json_input
from open_table_connector.sdk import Client, ConnectorRegistry
from open_table_connector.sdk.recipes import apply_recipe, export_recipe
from open_table_connector.spreadsheets import parse_recipe

from .output import CliUsageError


def run_recipe_command(args, registry, out, err) -> int:
    target = args.uri
    if args.action == "recipe":
        selectors = read_json_input(args.selectors)
        with Client(registry=ConnectorRegistry()) as client:
            result = export_recipe(client, target, selectors, allow_incomplete=args.allow_incomplete)
    else:
        payload = read_json_input(args.spec)
        recipe = parse_recipe(payload)
        from open_table_connector.contract import ExecutionOptions

        with Client(registry=ConnectorRegistry()) as client:
            result = apply_recipe(client, target, recipe, ExecutionOptions(dry_run=args.dry_run, allow_partial=args.allow_partial))
    out.write(json.dumps(result.to_wire(), ensure_ascii=False, default=str) + "\n")
    return 0 if result.outcome.value in {"succeeded", "planned"} else 5


__all__ = ["run_recipe_command"]
