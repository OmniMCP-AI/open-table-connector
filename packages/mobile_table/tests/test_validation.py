from __future__ import annotations

import pytest
from open_table_connector.mobile_table.validation import (
    CONTRACT,
    MAX_FIELDS,
    parse_request,
    validate_field_selection,
    validate_patch_size,
)


def test_parse_request_accepts_credential_free_table_uri_and_closed_keys() -> None:
    request = parse_request(
        {
            "contract": CONTRACT,
            "request_id": "req_01J",
            "table_uri": "https://example.invalid/table/123",
        },
        allowed_keys=frozenset({"contract", "request_id", "table_uri"}),
    )

    assert request.contract == CONTRACT
    assert request.request_id == "req_01J"
    assert request.table_uri == "https://example.invalid/table/123"


def test_parse_request_rejects_unknown_keys_and_credentials() -> None:
    base = {"contract": CONTRACT, "request_id": "req_01J", "table_uri": "https://example.invalid/table/123"}

    with pytest.raises(ValueError, match="unknown request field"):
        parse_request({**base, "secret": "should-not-pass"}, frozenset(base))

    with pytest.raises(ValueError, match="credential"):
        parse_request({**base, "table_uri": "https://example.invalid/table/123?access_token=secret"}, frozenset(base))


def test_field_selection_and_patch_limits_are_strict() -> None:
    assert validate_field_selection(tuple(f"field_{i}" for i in range(MAX_FIELDS))) == tuple(
        f"field_{i}" for i in range(MAX_FIELDS)
    )

    with pytest.raises(ValueError, match="at most 50"):
        validate_field_selection(tuple(f"field_{i}" for i in range(MAX_FIELDS + 1)))

    with pytest.raises(ValueError, match="16 KiB"):
        validate_patch_size({"field": "x" * 17_000})
