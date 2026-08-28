from __future__ import annotations

import inspect

from open_table_connector.contract.inspect import TableInspector
from open_table_connector.contract.read import (
    ArrowTableReader,
    PolarsTableReader,
    TableReadRequest,
)
from open_table_connector.contract.resolve import URIResolver


def test_roles_are_small_and_capability_specific() -> None:
    assert set(inspect.signature(URIResolver.resolve).parameters) == {
        "self",
        "uri",
        "context",
    }
    assert set(inspect.signature(TableInspector.inspect).parameters) == {
        "self",
        "request",
    }
    assert set(inspect.signature(ArrowTableReader.read_arrow).parameters) == {
        "self",
        "request",
    }
    assert set(inspect.signature(PolarsTableReader.read_polars).parameters) == {
        "self",
        "request",
    }
    assert "operation" not in inspect.signature(TableReadRequest).parameters
