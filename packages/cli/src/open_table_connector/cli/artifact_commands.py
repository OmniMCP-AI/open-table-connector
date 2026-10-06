from __future__ import annotations

import json

from open_table_connector.artifacts import ExportRequest
from open_table_connector.contract import PROVIDER_JSON
from open_table_connector.sdk import Client, ConnectorRegistry


def add_parser(subparsers):
    parser = subparsers.add_parser("artifact", help="create or view document artifacts")
    parser.add_argument("action", choices=("export", "view", "watch"))
    parser.add_argument("watch_action", nargs="?", choices=("start", "status", "refresh", "stop"))
    parser.add_argument("--from", dest="from_value")
    parser.add_argument("--to", dest="to_value")
    parser.add_argument("--mode", choices=("html", "screenshot", "text", "outline", "stats", "issues"))
    parser.add_argument("--uri")
    parser.add_argument("--session")
    parser.add_argument("--output-format", choices=(PROVIDER_JSON, "table"), default=PROVIDER_JSON)
    return parser


def run_artifact(args, out, err) -> int:
    if args.action != "export":
        err.write(json.dumps({"code": "unsupported_capability", "message": "artifact view/watch is not configured"}) + "\n")
        return 5
    source = args.from_value
    destination = args.to_value
    suffix = destination.rsplit(".", 1)[-1].casefold()
    request = ExportRequest(source, destination, "officecli", {"format": suffix})
    result = Client(registry=ConnectorRegistry()).artifacts().export(request)
    out.write(json.dumps(result.to_wire(), ensure_ascii=False, default=str) + "\n")
    return 0 if result.outcome.value == "succeeded" else 5


__all__ = ["add_parser", "run_artifact"]
