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


def test_main_missing_policy_fails_closed(monkeypatch, capsys):
    from open_table_connector.mcp.server import main

    monkeypatch.delenv("OTC_MCP_CONFIG", raising=False)
    assert main() == 2
    assert "policy" in capsys.readouterr().err.lower()


def test_host_backed_server_executes_typed_local_operation(tmp_path):
    from open_table_connector.local_files import LocalFilesConnector
    from open_table_connector.mcp.server import MCPHost, create_server
    from open_table_connector.sdk import Client, ConnectorRegistry

    uri = (tmp_path / "mcp.xlsx").as_uri()
    client = Client(registry=ConnectorRegistry([LocalFilesConnector()]))
    book = client.workbook.create(uri)
    book.worksheet.create("Report").range("A1").write([["before"]])
    book.write()
    server = create_server(host=MCPHost(client))
    tools = server._tool_manager._tools
    target = {"uri": uri, "sheet": "Report", "object_id": None}
    inspected = tools["otc_inspect"].fn({"namespace": "spreadsheet", "operation_id": "range.read", "version": "1.0", "target": target, "arguments": {"address": "A1"}})
    assert inspected["isError"] is False
    executed = tools["otc_execute"].fn({"namespace": "spreadsheet", "operation_id": "range.write", "version": "1.0", "target": target, "arguments": {"address": "A1", "values": [["after"]]}})
    assert executed["isError"] is False
    assert executed["structuredContent"]["commit"] == "committed"
    client.close()
