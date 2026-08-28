from __future__ import annotations

from pathlib import Path

import pytest

from open_connectors.contract import ConnectorError, ConnectorErrorCode, TableURI
from open_connectors.local_files.reader import LocalFilesConnector, LocalTableReadRequest


def test_xls_signature_routes_to_governed_xlrd_reader(tmp_path: Path) -> None:
    source = tmp_path / "invalid.xls"
    source.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1invalid")

    with pytest.raises(ConnectorError) as raised:
        LocalFilesConnector().read_polars(LocalTableReadRequest(TableURI(source.as_uri())))

    assert raised.value.code is ConnectorErrorCode.EXECUTION_FAILED
