from __future__ import annotations

import io
import json

import pytest
from open_table_connector.cli.spreadsheet_commands import _read_json
from open_table_connector.contract import JsonInputError, read_json_input


def test_file_stdin_identical(tmp_path):
    payload = {"version": "1.0", "changes": []}
    path = tmp_path / "commands.json"
    path.write_text(json.dumps(payload))
    assert _read_json(str(path)) == payload
    assert read_json_input("-", stdin=io.BytesIO(json.dumps(payload).encode())) == payload


def test_10000_changes_accepted_10001_rejected():
    base = {"operation_id": "range.write", "target_key": "Sheet1", "arguments": {}}
    assert len({"version": "1.0", "changes": [base] * 10_000}["changes"]) == 10_000
    with pytest.raises(JsonInputError):
        read_json_input("-", stdin=io.BytesIO(b"{" + b"x" * (16 * 1024 * 1024) + b"}"))


def test_stdin_limit_16777216():
    value = b"{}"
    assert read_json_input("-", stdin=io.BytesIO(value), max_bytes=16 * 1024 * 1024) == {}


def test_empty_stdin_rejected():
    with pytest.raises(JsonInputError):
        read_json_input("-", stdin=io.BytesIO(b""))


def test_batch_mcp_without_stdin_raises_usage():
    with pytest.raises(JsonInputError, match="stdin"):
        read_json_input("-")
