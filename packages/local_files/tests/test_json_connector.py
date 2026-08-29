from __future__ import annotations

from pathlib import Path

import pytest

from open_table_connector.contract import (
    ConnectorError,
    ConnectorErrorCode,
    ResourceLimits,
    TableMode,
    TableURI,
)
from open_table_connector.local_files import JsonConnector, JsonTableReadRequest


def json_uri(scheme: str, path: Path) -> TableURI:
    return TableURI(path.as_uri().replace("file://", f"{scheme}://", 1))


def test_json_and_jsonl_use_normal_base_connector_schemes(tmp_path: Path) -> None:
    json_path = tmp_path / "ticks.payload"
    json_path.write_text('[{"ts":"2026-08-29T00:00:00Z","symbol":"A","price":1}]')
    jsonl_path = tmp_path / "ticks.ndjson"
    jsonl_path.write_text('{"ts":"2026-08-29T00:00:00Z","symbol":"A","price":1}\n')
    connector = JsonConnector()

    json_result = connector.read_arrow(JsonTableReadRequest(json_uri("json", json_path)))
    jsonl_result = connector.read_arrow(JsonTableReadRequest(json_uri("jsonl", jsonl_path)))
    assert json_result.table.num_rows == 1
    assert jsonl_result.table.num_rows == 1
    assert json_result.receipt.mode is TableMode.BASE
    assert jsonl_result.receipt.mode is TableMode.BASE


def test_connector_rejects_invalid_utf8_and_enforces_input_and_row_bounds(tmp_path: Path) -> None:
    path = tmp_path / "rows.json"
    path.write_bytes(b"\xff")
    connector = JsonConnector()
    with pytest.raises(ConnectorError, match="UTF-8") as invalid:
        connector.read_arrow(JsonTableReadRequest(json_uri("json", path)))
    assert invalid.value.code is ConnectorErrorCode.EXECUTION_FAILED

    path.write_text('[{"id":1},{"id":2}]', encoding="utf-8")
    with pytest.raises(ConnectorError, match="byte limit"):
        connector.read_arrow(
            JsonTableReadRequest(
                json_uri("json", path),
                resource_limits=ResourceLimits(max_bytes=4),
            )
        )
    with pytest.raises(ConnectorError, match="row limit"):
        connector.read_arrow(
            JsonTableReadRequest(
                json_uri("json", path),
                resource_limits=ResourceLimits(max_rows=1),
            )
        )


def test_connector_enforces_timeout_after_decode(tmp_path: Path) -> None:
    path = tmp_path / "rows.json"
    path.write_text('[{"id":1}]', encoding="utf-8")
    values = iter((0.0, 2.0))
    connector = JsonConnector(clock=lambda: next(values))
    with pytest.raises(ConnectorError) as raised:
        connector.read_arrow(
            JsonTableReadRequest(
                json_uri("json", path),
                resource_limits=ResourceLimits(timeout_seconds=1),
            )
        )
    assert raised.value.code is ConnectorErrorCode.TIMEOUT


def test_scheme_controls_strict_payload_shape_not_filename_suffix(tmp_path: Path) -> None:
    path = tmp_path / "rows.jsonl"
    path.write_text('[{"id":1}]', encoding="utf-8")
    connector = JsonConnector()
    assert connector.read_arrow(JsonTableReadRequest(json_uri("json", path))).table.num_rows == 1
    with pytest.raises(ConnectorError, match="JSONL rows"):
        connector.read_arrow(JsonTableReadRequest(json_uri("jsonl", path)))
