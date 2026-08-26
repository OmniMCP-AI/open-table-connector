"""Conservative content probing for local tabular files."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
import re

from open_connectors.contract.errors import ConnectorError, ConnectorErrorCode


class LocalFormat(StrEnum):
    CSV = "csv"
    EXCEL = "excel"


XLSX_ZIP_SIGNATURE = b"PK\x03\x04"
SAMPLE_BYTES = 65_536


def detect_format(path: Path) -> LocalFormat:
    if not path.is_file():
        raise ConnectorError(
            ConnectorErrorCode.INVALID_URI,
            "local file is not a regular file",
            {"path": str(path)},
        )
    try:
        payload = path.read_bytes()[:SAMPLE_BYTES]
    except OSError as exc:
        raise ConnectorError(
            ConnectorErrorCode.INVALID_URI,
            "local file cannot be read",
            {"path": str(path), "reason": str(exc)},
        ) from None
    if payload.startswith(XLSX_ZIP_SIGNATURE):
        return LocalFormat.EXCEL
    text = payload.decode("utf-8", errors="replace")
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) >= 2:
        for delimiter in (",", "\t", ";"):
            if delimiter in lines[0] and lines[0].count(delimiter) == lines[1].count(delimiter):
                return LocalFormat.CSV
    raise ConnectorError(
        ConnectorErrorCode.INVALID_URI,
        "local file has no supported CSV or XLSX signature",
        {"path": str(path), "suffix": path.suffix.casefold()},
    )
