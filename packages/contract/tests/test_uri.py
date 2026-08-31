from __future__ import annotations

import pytest
from open_table_connector.contract import ResolveContext, TableURI


def test_table_uri_is_a_value_only_credential_free_reference() -> None:
    uri = TableURI("file:///data/orders.csv")

    assert uri.value == "file:///data/orders.csv"
    assert uri.scheme == "file"
    assert uri.to_wire() == {"value": "file:///data/orders.csv"}


@pytest.mark.parametrize(
    "value",
    [
        "relative/orders.csv",
        "file:///data/orders.csv?access_token=secret",
        "csv:///data/orders.csv?token=secret",
        "excel:///tmp/orders.xlsx#access_token=secret",
        "https://user:password@example.test/table",
        "https://example.test/x?token=",
        "https://example.test/x#access_token=abc",
        "https://example.test/x#api_key=",
        "",
    ],
)
def test_table_uri_rejects_relative_or_credential_bearing_values(value: str) -> None:
    with pytest.raises(ValueError):
        TableURI(value)


def test_table_uri_does_not_interpret_vendor_fields() -> None:
    uri = TableURI("https://docs.google.com/spreadsheets/d/abc#gid=123")

    assert uri.value.endswith("#gid=123")
    assert not hasattr(uri, "gid")
    assert not hasattr(uri, "doc_id")


def test_resolve_context_repr_omits_credentials() -> None:
    assert "fixture-secret" not in repr(
        ResolveContext(credentials={"token": "fixture-secret"})
    )
