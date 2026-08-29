from __future__ import annotations

import pyarrow as pa
import pytest

from open_table_connector.contract import ConnectorError, ConnectorErrorCode
from open_table_connector.local_files import (
    encode_json_table,
    encode_jsonl_table,
    parse_json_table,
    parse_jsonl_table,
)


def test_json_and_jsonl_preserve_first_seen_columns_missing_nulls_and_nested_values() -> None:
    json_table = parse_json_table(
        '[{"id":"a","meta":{"x":1},"items":[1,2]},'
        '{"id":"b","name":"Bee"}]',
        source="fixture.json",
    )
    jsonl_table = parse_jsonl_table(
        '{"id":"a","meta":{"x":1},"items":[1,2]}\n\n'
        '{"id":"b","name":"Bee"}\n',
        source="fixture.jsonl",
    )

    for table in (json_table, jsonl_table):
        assert table.column_names == ["id", "meta", "items", "name"]
        assert table.to_pylist() == [
            {"id": "a", "meta": {"x": 1}, "items": [1, 2], "name": None},
            {"id": "b", "meta": None, "items": None, "name": "Bee"},
        ]


@pytest.mark.parametrize(
    ("parser", "text", "detail"),
    [
        (parse_json_table, "{}", {}),
        (parse_json_table, "1", {}),
        (parse_json_table, "[1]", {"index": 1}),
        (parse_json_table, '[{"a":1,"a":2}]', {}),
        (parse_json_table, '[{"nested":{"a":1,"a":2}}]', {}),
        (parse_json_table, '[{"a":NaN}]', {}),
        (parse_json_table, '[{"a":Infinity}]', {}),
        (parse_json_table, "[] trailing", {"line": 1}),
        (parse_jsonl_table, '{"a":1}\n{"a":}\n', {"line": 2}),
        (parse_jsonl_table, '{"a":1}\n[]\n', {"line": 2}),
    ],
)
def test_strict_decoders_reject_invalid_or_ambiguous_json_without_record_payload(
    parser,
    text,
    detail,
) -> None:
    secret = "record-secret"
    with pytest.raises(ConnectorError) as raised:
        parser(text.replace("trailing", f"trailing-{secret}"), source="safe-source")
    assert raised.value.code is ConnectorErrorCode.EXECUTION_FAILED
    assert detail.items() <= raised.value.safe_details.items()
    assert secret not in str(raised.value.safe_details)


def test_encoders_are_compact_deterministic_and_round_trip_nested_arrow() -> None:
    table = pa.table(
        {
            "id": ["a"],
            "meta": pa.array([{"z": 1, "a": 2}]),
            "items": pa.array([[1, 2]]),
            "ts": pa.array(
                [1_787_961_600_000_000_123],
                type=pa.timestamp("ns", tz="UTC"),
            ),
        }
    )

    json_text = encode_json_table(table)
    jsonl_text = encode_jsonl_table(table)
    assert json_text == (
        '[{"id":"a","meta":{"a":2,"z":1},"items":[1,2],'
        '"ts":"2026-08-29T00:00:00.000000123Z"}]'
    )
    assert jsonl_text == json_text[1:-1] + "\n"
    assert parse_json_table(json_text, source="roundtrip").to_pylist()[0]["meta"] == {
        "a": 2,
        "z": 1,
    }
    assert parse_jsonl_table(jsonl_text, source="roundtrip").num_rows == 1


@pytest.mark.parametrize("encoder", (encode_json_table, encode_jsonl_table))
def test_encoders_reject_non_finite_values(encoder) -> None:
    with pytest.raises(ConnectorError, match="non-finite"):
        encoder(pa.table({"value": [float("nan")]}))
