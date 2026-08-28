from __future__ import annotations

from pathlib import Path

import pytest

from open_table_connector.contract.errors import ConnectorError, ConnectorErrorCode
from open_table_connector.local_files.probe import LocalFormat, detect_format


def test_csv_signature_wins_over_misleading_xlsx_suffix(tmp_path: Path) -> None:
    source = tmp_path / "orders.xlsx"
    source.write_text("id,amount\n1,2\n", encoding="utf-8")

    assert detect_format(source) is LocalFormat.CSV


def test_xlsx_zip_signature_wins_over_misleading_csv_suffix(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    source.write_bytes(b"PK\x03\x04fake-xlsx")

    assert detect_format(source) is LocalFormat.EXCEL


def test_unsupported_content_fails_with_structured_error(tmp_path: Path) -> None:
    source = tmp_path / "image.bin"
    source.write_bytes(b"\x89PNG\r\n\x1a\n")

    with pytest.raises(ConnectorError) as raised:
        detect_format(source)

    assert raised.value.code is ConnectorErrorCode.INVALID_URI
