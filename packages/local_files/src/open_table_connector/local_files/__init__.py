"""Neutral local-files Connector package."""

from .bounded_reader import LocalBoundedReader
from .csv_connector import CsvConnector, CsvReadOptions, CsvTableReadRequest
from .excel_connector import ExcelConnector, ExcelReadOptions, ExcelTableReadRequest
from .excel_reader import read_excel_arrow
from .excel_writer import write_excel
from .identity import CONNECTOR_IDENTITY
from .json_codec import (
    encode_json_table,
    encode_jsonl_table,
    parse_json_table,
    parse_jsonl_table,
)
from .json_connector import JsonConnector, JsonTableReadRequest
from .local_files_connector import LocalFilesConnector, LocalReadOptions, LocalTableReadRequest
from .manifest import CAPABILITY_MANIFEST
from .markdown_connector import MarkdownConnector, MarkdownReadOptions, MarkdownTableReadRequest
from .markdown_reader import is_markdown_payload, read_markdown_arrow, write_markdown_table
from .probe import LocalFormat, detect_format
from .resolver import LocalURIResolver, ResolvedLocalTable
from .temporal_csv import CsvManagedTemporalStore, CsvTemporalExecutor
from .temporal_excel import ExcelManagedTemporalStore, ExcelTemporalExecutor
from .temporal_json import JsonManagedTemporalStore, JsonTemporalExecutor

__all__ = [
    "CAPABILITY_MANIFEST",
    "CONNECTOR_IDENTITY",
    "CsvConnector",
    "CsvManagedTemporalStore",
    "CsvReadOptions",
    "CsvTableReadRequest",
    "CsvTemporalExecutor",
    "ExcelConnector",
    "ExcelManagedTemporalStore",
    "ExcelReadOptions",
    "ExcelTableReadRequest",
    "ExcelTemporalExecutor",
    "JsonConnector",
    "JsonManagedTemporalStore",
    "JsonTableReadRequest",
    "JsonTemporalExecutor",
    "read_excel_arrow",
    "LocalFormat",
    "LocalURIResolver",
    "ResolvedLocalTable",
    "LocalFilesConnector",
    "LocalReadOptions",
    "LocalTableReadRequest",
    "LocalBoundedReader",
    "MarkdownConnector",
    "MarkdownReadOptions",
    "MarkdownTableReadRequest",
    "detect_format",
    "encode_json_table",
    "encode_jsonl_table",
    "is_markdown_payload",
    "parse_json_table",
    "parse_jsonl_table",
    "read_markdown_arrow",
    "write_markdown_table",
    "write_excel",
]
