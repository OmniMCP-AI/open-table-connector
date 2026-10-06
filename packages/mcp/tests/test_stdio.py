from __future__ import annotations


def test_malformed_request_rejected_before_dispatch():
    from open_table_connector.mcp.server import handle_request

    result = handle_request({"method": "tools/call", "params": {}})
    assert result["isError"] is True


def test_official_server_registers_only_closed_tools():
    from open_table_connector.mcp.server import create_server

    server = create_server()
    names = {tool.name for tool in server._tool_manager.list_tools()}
    assert names == {"otc_discover", "otc_inspect", "otc_execute"}
