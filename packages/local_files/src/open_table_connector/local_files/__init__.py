"""Neutral local-files Connector package."""

from .csv_connector import CsvConnector, CsvReadOptions, CsvTableReadRequest
from .temporal_csv import CsvManagedTemporalStore, CsvTemporalExecutor
from .excel_connector import ExcelConnector, ExcelReadOptions, ExcelTableReadRequest
from .excel_reader import read_excel_arrow
from .identity import CONNECTOR_IDENTITY
from .markdown_connector import MarkdownConnector, MarkdownReadOptions, MarkdownTableReadRequest
from .manifest import CAPABILITY_MANIFEST
from .markdown_reader import is_markdown_payload, read_markdown_arrow, write_markdown_table
from .excel_writer import write_excel
from .probe import LocalFormat, detect_format
from .resolver import LocalURIResolver, ResolvedLocalTable
from .local_files_connector import LocalFilesConnector, LocalReadOptions, LocalTableReadRequest

__all__ = [
    "CAPABILITY_MANIFEST",
    "CONNECTOR_IDENTITY",
    "CsvConnector",
    "CsvManagedTemporalStore",
    "CsvReadOptions",
    "CsvTableReadRequest",
    "CsvTemporalExecutor",
    "ExcelConnector",
    "ExcelReadOptions",
    "ExcelTableReadRequest",
    "read_excel_arrow",
    "LocalFormat",
    "LocalURIResolver",
    "ResolvedLocalTable",
    "LocalFilesConnector",
    "LocalReadOptions",
    "LocalTableReadRequest",
    "MarkdownConnector",
    "MarkdownReadOptions",
    "MarkdownTableReadRequest",
    "detect_format",
    "is_markdown_payload",
    "read_markdown_arrow",
    "write_markdown_table",
    "write_excel",
]
