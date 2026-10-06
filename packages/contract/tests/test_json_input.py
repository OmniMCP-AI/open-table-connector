import io

import pytest

from open_table_connector.contract.json_input import JsonInputError, read_json_input


def test_duplicate_nested_key_and_nonfinite_values_reject():
    with pytest.raises(JsonInputError):
        read_json_input("-", stdin=io.BytesIO(b'{"a":{"x":1,"x":2}}'))
    with pytest.raises(JsonInputError):
        read_json_input("-", stdin=io.BytesIO(b'{"value":NaN}'))


def test_exact_byte_limit_and_utf8_are_bounded():
    assert read_json_input("-", stdin=io.BytesIO(b'{"x":"a"}'), max_bytes=9) == {"x": "a"}
    with pytest.raises(JsonInputError):
        read_json_input("-", stdin=io.BytesIO(b'{"x":"ab"}'), max_bytes=9)
    with pytest.raises(JsonInputError):
        read_json_input("-", stdin=io.BytesIO(b"\xff"), max_bytes=10)


def test_source_dash_requires_explicit_stdin():
    with pytest.raises(JsonInputError):
        read_json_input("-")
