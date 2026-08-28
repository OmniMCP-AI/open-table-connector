"""Conservative content probing for local tabular files."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from open_table_connector.contract.errors import ConnectorError, ConnectorErrorCode
from .markdown_reader import is_markdown_payload


class LocalFormat(StrEnum):
    CSV = "csv"
    EXCEL = "excel"
    MARKDOWN = "md"


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
        if is_markdown_payload(text):
            return LocalFormat.MARKDOWN
        if path.suffix.casefold() in {".csv", ".tsv"}:
            return LocalFormat.CSV
    raise ConnectorError(
        ConnectorErrorCode.INVALID_URI,
        "local file has no supported CSV, Markdown, or XLSX signature",
        {"path": str(path), "suffix": path.suffix.casefold()},
    )
