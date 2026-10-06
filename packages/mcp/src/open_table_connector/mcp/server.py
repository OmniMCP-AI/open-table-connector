"""Official MCP stdio adapter over the typed OTC tool functions."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .policy import load_policy
from .tools import otc_discover


def create_server() -> FastMCP:
    """Build a fresh server with exactly the three public OTC tools."""

    server = FastMCP(
        "otc",
        instructions="Use otc_discover before invoking a typed OTC operation.",
    )

    @server.tool(
        name="otc_discover",
        description="Describe a registered OTC operation without dispatching it.",
        structured_output=True,
    )
    def discover(selector: dict[str, object] | None = None) -> dict[str, object]:
        return otc_discover(selector)

    @server.tool(
        name="otc_inspect",
        description="Inspect a read-only OTC operation through the configured SDK host.",
        structured_output=True,
    )
    def inspect(request: dict[str, object]) -> dict[str, object]:
        return {
            "isError": True,
            "structuredContent": {
                "code": "configuration",
                "message": "MCP server requires an SDK host for inspection",
            },
        }

    @server.tool(
        name="otc_execute",
        description="Execute a typed OTC operation through the configured SDK host.",
        structured_output=True,
    )
    def execute(request: dict[str, object]) -> dict[str, object]:
        return {
            "isError": True,
            "structuredContent": {
                "code": "configuration",
                "message": "MCP server requires an SDK host for execution",
            },
        }

    return server


def handle_request(request):
    if not isinstance(request, dict) or request.get("method") != "tools/call":
        return {"isError": True, "structuredContent": {"code": "invalid_request", "message": "expected tools/call"}}
    params = request.get("params")
    if not isinstance(params, dict) or params.get("name") not in {"otc_discover", "otc_inspect", "otc_execute"}:
        return {"isError": True, "structuredContent": {"code": "invalid_request", "message": "unknown MCP tool"}}
    name = params["name"]
    arguments = params.get("arguments", {})
    if name == "otc_discover":
        return otc_discover(arguments)
    return {"isError": True, "structuredContent": {"code": "configuration", "message": "MCP server requires an SDK host"}}


def main() -> int:
    config_path = os.environ.get("OTC_MCP_CONFIG")
    if not config_path or not os.path.isabs(config_path):
        print("MCP policy is required via absolute OTC_MCP_CONFIG", file=sys.stderr)
        return 2
    try:
        load_policy(Path(config_path))
    except (OSError, ValueError, TypeError) as exc:
        print(f"MCP policy unavailable: {type(exc).__name__}", file=sys.stderr)
        return 2
    asyncio.run(create_server().run_stdio_async())
    return 0


__all__ = ["create_server", "handle_request", "main"]
