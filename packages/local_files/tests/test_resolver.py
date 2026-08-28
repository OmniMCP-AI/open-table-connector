from __future__ import annotations

from pathlib import Path

import pytest

from open_table_connector.contract import ResolveContext, TableURI, TableMode
from open_table_connector.contract.errors import ConnectorError, ConnectorErrorCode
from open_table_connector.local_files.resolver import LocalFormat, LocalURIResolver


def test_resolver_accepts_absolute_file_uri_and_sheet_fragment(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    source.write_text("id,amount\n1,2\n", encoding="utf-8")
    uri = TableURI(f"{source.as_uri()}#sheet=Orders")

    resolved = LocalURIResolver().resolve(uri, ResolveContext())

    assert resolved.mode is TableMode.SHEET
    assert resolved.resource.path == source
    assert resolved.resource.format is LocalFormat.CSV
    assert resolved.resource.sheet == "Orders"


def test_resolver_decodes_percent_encoded_local_path(tmp_path: Path) -> None:
    source = tmp_path / "orders with spaces.csv"
    source.write_text("id,amount\n1,2\n", encoding="utf-8")

    resolved = LocalURIResolver().resolve(TableURI(source.as_uri()), ResolveContext())

    assert resolved.resource.path == source


def test_resolver_rejects_missing_file(tmp_path: Path) -> None:
    uri = TableURI((tmp_path / "missing.csv").as_uri())

    with pytest.raises(ConnectorError) as raised:
        LocalURIResolver().resolve(uri, ResolveContext())

    assert raised.value.code is ConnectorErrorCode.INVALID_URI


def test_resolver_rejects_directory(tmp_path: Path) -> None:
    uri = TableURI(tmp_path.as_uri())

    with pytest.raises(ConnectorError, match="regular file"):
        LocalURIResolver().resolve(uri, ResolveContext())


def test_resolver_never_accepts_non_file_scheme() -> None:
    uri = TableURI("https://example.test/orders.csv")

    with pytest.raises(ConnectorError, match="file"):
        LocalURIResolver().resolve(uri, ResolveContext())


def test_resolver_rejects_credential_query_before_physical_access(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="credential"):
        TableURI(f"{(tmp_path / 'orders.csv').as_uri()}?token=secret")
