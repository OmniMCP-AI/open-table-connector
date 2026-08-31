"""Compatibility imports for local codecs now owned by ``local_files``."""

from open_table_connector.local_files.cli_adapter import (
    infer_format,
    json_safe_value,
    read_local,
    write_local,
    write_markdown_table,
)

__all__ = [
    "infer_format",
    "json_safe_value",
    "read_local",
    "write_local",
    "write_markdown_table",
]
