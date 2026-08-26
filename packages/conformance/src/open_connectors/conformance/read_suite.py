"""Convenience runner for the read conformance assertions."""

from __future__ import annotations

from collections.abc import Iterable

from open_connectors.contract import ArrowTableReader, PolarsTableReader, TableReadRequest

from .assertions import assert_read_connector_conformance


def run_read_suite(
    connector: ArrowTableReader & PolarsTableReader,
    requests: Iterable[TableReadRequest],
) -> None:
    for request in requests:
        assert_read_connector_conformance(connector, request)
