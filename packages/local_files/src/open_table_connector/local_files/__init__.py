"""Neutral local-files Connector package."""

from .identity import CONNECTOR_IDENTITY
from .manifest import CAPABILITY_MANIFEST
from .markdown_reader import is_markdown_payload, read_markdown_arrow, write_markdown_table
from .probe import LocalFormat, detect_format
from .resolver import LocalURIResolver, ResolvedLocalTable
from .reader import LocalFilesConnector, LocalReadOptions, LocalTableReadRequest

__all__ = [
    "CAPABILITY_MANIFEST",
    "CONNECTOR_IDENTITY",
    "LocalFormat",
    "LocalURIResolver",
    "ResolvedLocalTable",
    "LocalFilesConnector",
    "LocalReadOptions",
    "LocalTableReadRequest",
    "detect_format",
    "is_markdown_payload",
    "read_markdown_arrow",
    "write_markdown_table",
]
