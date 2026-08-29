"""Conservative content probing for local tabular files."""

from __future__ import annotations

from enum import StrEnum
import json
from pathlib import Path

from open_table_connector.contract.errors import ConnectorError, ConnectorErrorCode
from .markdown_reader import is_markdown_payload


class LocalFormat(StrEnum):
    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"
    LEGACY_EXCEL = "xls"
    MARKDOWN = "md"


XLSX_ZIP_SIGNATURE = b"PK\x03\x04"
XLS_COMPOUND_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
SAMPLE_BYTES = 65_536


def detect_separator(path: Path) -> str | None:
    """Return the consistent delimiter found in the first two data lines."""

    text = path.read_bytes()[:SAMPLE_BYTES].decode("utf-8", errors="replace")
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return None
    for delimiter in (",", "\t", ";"):
        count = lines[0].count(delimiter)
        if count and count == lines[1].count(delimiter):
            return delimiter
    return None


def _is_json_payload(text: str) -> bool:
    stripped = text.strip()
    if not stripped or stripped[0] not in "[{":
        return False
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        try:
            values = [json.loads(line) for line in stripped.splitlines() if line.strip()]
        except json.JSONDecodeError:
            return False
        return bool(values) and all(isinstance(item, dict) for item in values)
    return isinstance(value, (dict, list))


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
    if payload.startswith(XLS_COMPOUND_SIGNATURE):
        return LocalFormat.LEGACY_EXCEL
    text = payload.decode("utf-8", errors="replace")
    if _is_json_payload(text):
        return LocalFormat.JSON
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) >= 2:
        if detect_separator(path) is not None:
            return LocalFormat.CSV
        if is_markdown_payload(text):
            return LocalFormat.MARKDOWN
        if path.suffix.casefold() in {".csv", ".tsv"}:
            return LocalFormat.CSV
    raise ConnectorError(
        ConnectorErrorCode.INVALID_URI,
        "local file has no supported CSV, JSON, Markdown, XLS, or XLSX signature",
        {"path": str(path), "suffix": path.suffix.casefold()},
    )
