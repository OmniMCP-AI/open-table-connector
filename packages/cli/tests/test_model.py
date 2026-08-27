from pathlib import Path

import pytest

from open_connectors.cli.model import FormatName, parse_endpoint, parse_format


def test_parse_endpoint_keeps_connector_uri_opaque() -> None:
    endpoint = parse_endpoint("gsheets://book/Orders")
    assert endpoint.uri.value == "gsheets://book/Orders"
    assert endpoint.path is None


def test_parse_endpoint_normalizes_file_uri_to_path() -> None:
    endpoint = parse_endpoint("file:///tmp/orders.csv")
    assert endpoint.uri is None
    assert endpoint.path == Path("/tmp/orders.csv")


def test_parse_format_defaults_to_auto_and_rejects_unknown_values() -> None:
    assert parse_format(None) is FormatName.AUTO
    with pytest.raises(ValueError, match="unsupported format"):
        parse_format("yaml")
