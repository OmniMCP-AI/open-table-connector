"""Local-file URI resolver owned by the local-files Connector."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit

from open_table_connector.contract import ResolveContext, ResolvedTable, TableMode, TableURI
from open_table_connector.contract.errors import ConnectorError, ConnectorErrorCode

from .probe import LocalFormat, detect_format


@dataclass(frozen=True)
class ResolvedLocalTable:
    path: Path
    format: LocalFormat
    sheet: str | None = None


def _resolve_explicit_local_path(
    uri: TableURI,
    context: ResolveContext,
    *,
    scheme: str,
    expected_format: LocalFormat,
    allow_sheet_fragment: bool = False,
) -> tuple[Path, str | None]:
    if uri.scheme != scheme:
        raise ConnectorError(
            ConnectorErrorCode.INVALID_URI,
            f"{scheme} Connector accepts only {scheme} URIs",
            {"scheme": uri.scheme},
        )
    parsed = urlsplit(uri.value)
    if parsed.query:
        raise ConnectorError(
            ConnectorErrorCode.INVALID_URI,
            f"{scheme} URI query parameters are unsupported",
            {"query_keys": sorted(key for key, _ in parse_qsl(parsed.query))},
        )
    if parsed.netloc not in ("", "localhost"):
        raise ConnectorError(
            ConnectorErrorCode.INVALID_URI,
            f"{scheme} URI host is unsupported",
            {"host": parsed.netloc},
        )
    path = Path(unquote(parsed.path))
    if not path.is_absolute():
        raise ConnectorError(
            ConnectorErrorCode.INVALID_URI,
            f"{scheme} URI must contain an absolute path",
            {},
        )
    if not path.is_file():
        raise ConnectorError(
            ConnectorErrorCode.INVALID_URI,
            "local file is not a regular file",
            {"path": str(path)},
        )
    size = path.stat().st_size
    limits = context.resource_limits
    if limits.max_bytes is not None and size > limits.max_bytes:
        raise ConnectorError(
            ConnectorErrorCode.INVALID_URI,
            "local file exceeds the configured byte limit",
            {"size": size, "max_bytes": limits.max_bytes},
        )
    fragment_values = dict(parse_qsl(parsed.fragment, keep_blank_values=True))
    if allow_sheet_fragment:
        if set(fragment_values) - {"sheet"}:
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                f"{scheme} URI fragment is unsupported",
                {"fragment_keys": sorted(fragment_values)},
            )
        sheet = fragment_values.get("sheet") or None
    else:
        if fragment_values:
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                f"{scheme} URI fragment is unsupported",
                {"fragment_keys": sorted(fragment_values)},
            )
        sheet = None
    detected = detect_format(path)
    if detected is not expected_format:
        raise ConnectorError(
            ConnectorErrorCode.INVALID_URI,
            f"{scheme} URI payload does not match the requested connector format",
            {"path": str(path), "expected": expected_format.value, "detected": detected.value},
        )
    return path, sheet


def _sheet_from_uri(uri: TableURI) -> str | None:
    parsed = urlsplit(uri.value)
    values = dict(parse_qsl(parsed.fragment, keep_blank_values=True))
    sheet = values.get("sheet")
    return sheet or None


class LocalURIResolver:
    def resolve(self, uri: TableURI, context: ResolveContext) -> ResolvedTable:
        if uri.scheme != "file":
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "local-files Connector accepts only file URIs",
                {"scheme": uri.scheme},
            )
        parsed = urlsplit(uri.value)
        if parsed.query:
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "local file URI query parameters are unsupported",
                {"query_keys": sorted(key for key, _ in parse_qsl(parsed.query))},
            )
        if parsed.netloc not in ("", "localhost"):
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "local file URI host is unsupported",
                {"host": parsed.netloc},
            )
        path = Path(unquote(parsed.path))
        if not path.is_absolute():
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "local file URI must contain an absolute path",
                {},
            )
        if not path.is_file():
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "local file is not a regular file",
                {"path": str(path)},
            )
        limits = context.resource_limits
        if limits.max_bytes is not None and path.stat().st_size > limits.max_bytes:
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "local file exceeds the configured byte limit",
                {"size": path.stat().st_size, "max_bytes": limits.max_bytes},
            )
        return ResolvedTable(
            uri=uri,
            mode=TableMode.SHEET,
            resource=ResolvedLocalTable(
                path=path,
                format=detect_format(path),
                sheet=_sheet_from_uri(uri),
            ),
        )
