"""Neutral local-files Connector package."""

from .identity import CONNECTOR_IDENTITY
from .manifest import CAPABILITY_MANIFEST
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
]
