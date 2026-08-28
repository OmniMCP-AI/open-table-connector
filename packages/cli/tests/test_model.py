from pathlib import Path

import pytest

from open_table_connector.cli.model import FormatName, parse_endpoint, parse_format


def test_parse_endpoint_keeps_connector_uri_opaque() -> None:
    endpoint = parse_endpoint("gsheets://book/Orders")
    assert endpoint.uri.value == "gsheets://book/Orders"
    assert endpoint.path is None


def test_parse_endpoint_preserves_bare_local_path() -> None:
    endpoint = parse_endpoint("orders.csv")
    assert endpoint.uri is None
    assert endpoint.path == Path("orders.csv")
    assert endpoint.is_stdio is False


def test_parse_endpoint_preserves_stdin() -> None:
    endpoint = parse_endpoint("-")
    assert endpoint.uri is None
    assert endpoint.path is None
    assert endpoint.is_stdio is True


def test_parse_endpoint_normalizes_file_uri_to_path() -> None:
    endpoint = parse_endpoint("file:///tmp/orders.csv")
    assert endpoint.uri is None
    assert endpoint.path == Path("/tmp/orders.csv")


def test_parse_endpoint_accepts_localhost_file_authority() -> None:
    endpoint = parse_endpoint("file://localhost/tmp/orders.csv")
    assert endpoint.uri is None
    assert endpoint.path == Path("/tmp/orders.csv")


def test_parse_endpoint_treats_windows_drive_path_as_local_path() -> None:
    endpoint = parse_endpoint(r"C:\tmp\orders.csv")
    assert endpoint.uri is None
    assert endpoint.path == Path(r"C:\tmp\orders.csv")


@pytest.mark.parametrize(
    "value",
    [
        "file://server/path",
        "file://secret-server/path",
        "file://user:secret@server/path",
    ],
)
def test_parse_endpoint_rejects_non_local_file_authority_without_leaking_secret(
    value: str,
) -> None:
    with pytest.raises(ValueError) as error:
        parse_endpoint(value)

    assert "secret" not in str(error.value)


@pytest.mark.parametrize(
    "value",
    [
        "file:///tmp/orders.csv?view=secret-query",
        "file:///tmp/orders.csv#secret-fragment",
    ],
)
def test_parse_endpoint_rejects_ignored_file_components_without_leaking_secret(
    value: str,
) -> None:
    with pytest.raises(ValueError) as error:
        parse_endpoint(value)

    assert "secret" not in str(error.value)


def test_parse_endpoint_rejects_credential_bearing_file_uri_without_leaking_secret() -> None:
    with pytest.raises(ValueError) as error:
        parse_endpoint("file:///tmp/x?token=secret")

    assert "secret" not in str(error.value)


def test_parse_endpoint_rejects_relative_file_uri() -> None:
    with pytest.raises(ValueError):
        parse_endpoint("file:relative")


def test_parse_format_defaults_to_auto_and_rejects_unknown_values() -> None:
    assert parse_format(None) is FormatName.AUTO
    with pytest.raises(ValueError, match="unsupported format"):
        parse_format("yaml")
