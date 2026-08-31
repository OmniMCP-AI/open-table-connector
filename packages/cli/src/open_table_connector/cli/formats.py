"""Temporary migration exports for the provider-owned local file codecs."""

from open_table_connector.local_files.cli_adapter import (
    infer_format,
    read_local,
    write_local,
    write_markdown_table,
)

__all__ = ["infer_format", "read_local", "write_local", "write_markdown_table"]
