from __future__ import annotations

import io
import json

from open_table_connector.cli.discovery_commands import run_discovery_command
from open_table_connector.sdk.discovery import OperationCatalog


def test_help_and_capabilities_cli_use_sdk_payload() -> None:
    out, err = io.StringIO(), io.StringIO()
    assert run_discovery_command(
        type("Args", (), {"command": "help", "namespace": "spreadsheet", "operation_id": "range.read", "output_format": "json", "uri": None, "sheet": None})(),
        out,
        err,
        catalog=OperationCatalog.default(),
    ) == 0
    payload = json.loads(out.getvalue())
    assert payload["operation_id"] == "range.read"
    assert err.getvalue() == ""
