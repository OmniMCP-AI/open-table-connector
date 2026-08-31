"""Conservative content probing for local tabular files."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from open_table_connector.contract import (
    PROVIDER_CSV,
    PROVIDER_EXCEL,
    PROVIDER_JSON,
    PROVIDER_JSONL,
    SCHEME_MD,
)
from open_table_connector.contract.errors import ConnectorError, ConnectorErrorCode

from .json_codec import parse_json_table, parse_jsonl_table
from .markdown_reader import is_markdown_payload


class LocalFormat(StrEnum):
    CSV = PROVIDER_CSV
    EXCEL = PROVIDER_EXCEL
    JSON = PROVIDER_JSON
    JSONL = PROVIDER_JSONL
    MARKDOWN = SCHEME_MD


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
    suffix = path.suffix.casefold()
    if suffix in {".json", ".jsonl", ".ndjson"}:
        try:
            if suffix == ".json":
                parse_json_table(path.read_text(encoding="utf-8"), source=str(path))
                return LocalFormat.JSON
            parse_jsonl_table(path.read_text(encoding="utf-8"), source=str(path))
            return LocalFormat.JSONL
        except (ConnectorError, OSError, UnicodeError):
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "local JSON file does not match its strict format",
                {"path": str(path), "suffix": suffix},
            ) from None
    try:
        if text.lstrip().startswith("["):
            parse_json_table(path.read_text(encoding="utf-8"), source=str(path))
            return LocalFormat.JSON
        if text.lstrip().startswith("{"):
            parse_jsonl_table(path.read_text(encoding="utf-8"), source=str(path))
            return LocalFormat.JSONL
    except (ConnectorError, OSError, UnicodeError):
        pass
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) >= 2:
        for delimiter in (",", "\t", ";"):
            if delimiter in lines[0] and lines[0].count(delimiter) == lines[1].count(delimiter):
                return LocalFormat.CSV
        if is_markdown_payload(text):
            return LocalFormat.MARKDOWN
        if suffix in {".csv", ".tsv"}:
            return LocalFormat.CSV
    raise ConnectorError(
        ConnectorErrorCode.INVALID_URI,
        "local file has no supported CSV, JSON, JSONL, Markdown, or XLSX signature",
        {"path": str(path), "suffix": path.suffix.casefold()},
    )
