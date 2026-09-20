from __future__ import annotations

import json

from open_table_connector.cli.__main__ import main


def test_cli_style_and_config_read_return_physical_evidence(tmp_path, capsys):
    destination = tmp_path / "report.xlsx"
    commands = tmp_path / "commands.json"
    commands.write_text(json.dumps({"version": "1.0", "changes": [
        {"operation_id": "worksheet.create", "target_key": "Report", "arguments": {}},
        {"operation_id": "range.write", "target_key": "Report", "arguments": {"address": "A1", "values": [["value"]]}},
        {"operation_id": "range.style", "target_key": "Report", "arguments": {"address": "A1", "bold": True}},
    ]}))
    assert main(["spreadsheet", "batch", "--uri", destination.as_uri(), "--create", "--commands", str(commands)]) == 0
    capsys.readouterr()
    assert main(["spreadsheet", "style-read", "--uri", destination.as_uri(), "--sheet", "Report", "--range", "A1", "--fields", '["bold"]']) == 0
    style = json.loads(capsys.readouterr().out)
    assert style["value"]["kind"] == "spreadsheet.range.style.observation/1.0"
    assert main(["spreadsheet", "config-read", "--uri", destination.as_uri(), "--sheet", "Report", "--rows", "[1]", "--columns", '["A"]']) == 0
    config = json.loads(capsys.readouterr().out)
    assert config["value"]["kind"] == "spreadsheet.worksheet.config.observation/1.0"


def test_cli_config_read_requires_explicit_rows_and_columns(tmp_path, capsys):
    assert main(["spreadsheet", "config-read", "--uri", (tmp_path / "x.xlsx").as_uri(), "--sheet", "Report", "--rows", "[1]"]) != 0
    assert json.loads(capsys.readouterr().err)["code"] == "usage"
