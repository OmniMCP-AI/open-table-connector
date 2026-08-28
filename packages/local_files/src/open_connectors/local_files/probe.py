"""Conservative content probing for local tabular files."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
import re

from open_connectors.contract.errors import ConnectorError, ConnectorErrorCode


class LocalFormat(StrEnum):
    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"
    XLSX = "excel"
    XLS = "xls"


XLSX_ZIP_SIGNATURE = b"PK\x03\x04"
XLS_OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
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
    if payload.startswith(XLS_OLE_SIGNATURE):
        return LocalFormat.XLS
    text = payload.decode("utf-8", errors="replace")
    if path.suffix.casefold() == ".json":
        return LocalFormat.JSON
    if path.suffix.casefold() in {".csv", ".tsv"}:
        lines = [line for line in text.splitlines() if line.strip()]
        if len(lines) >= 2:
            return LocalFormat.CSV
    if text.lstrip().startswith(("[", "{")):
        try:
            import json

            json.loads(payload.decode("utf-8"))
            return LocalFormat.JSON
        except (UnicodeError, ValueError):
            pass
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) >= 2:
        for delimiter in (",", "\t", ";"):
            if delimiter in lines[0] and lines[0].count(delimiter) == lines[1].count(delimiter):
                return LocalFormat.CSV
    raise ConnectorError(
        ConnectorErrorCode.INVALID_URI,
        "local file has no supported CSV, JSON, XLSX, or XLS signature",
        {"path": str(path), "suffix": path.suffix.casefold()},
    )
