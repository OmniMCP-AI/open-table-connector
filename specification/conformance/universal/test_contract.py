from __future__ import annotations

import json

import polars as pl
import pyarrow as pa
import pytest

from open_connectors.contract import ConnectorError, ConnectorErrorCode, ResourceLimits, TableMode, TableURI

from specification.conformance.universal.assertions import (
    assert_error_is_safe,
    assert_receipt_matches_table,
    assert_safe_uri,
)
from specification.conformance.universal.cases import ConnectorCase, all_cases, cases_with

_CASE_NAMES = tuple(item.name for item in all_cases())
_READ_ARROW_CASE_NAMES = tuple(item.name for item in cases_with("table.read.arrow"))
_INSPECT_CASE_NAMES = tuple(
    item.name for item in cases_with("table.inspect") if item.name != "sqlite"
)
_WRITE_CASE_NAMES = tuple(item.name for item in cases_with("table.write"))


def _canonical_write_table(connector_case: ConnectorCase, write_frame: pl.DataFrame) -> pa.Table:
    if connector_case.name in {"google_sheets", "feishu_bitable"}:
        return pa.Table.from_pydict(
            {
                name: write_frame.get_column(name).to_list()
                for name in write_frame.columns
            }
        )
    return write_frame.to_arrow()


@pytest.mark.parametrize("connector_case", _CASE_NAMES, ids=str, indirect=True)
def test_case_uri_is_absolute_and_credential_free(connector_case: ConnectorCase) -> None:
    assert_safe_uri(connector_case.table_uri, allowed_schemes=connector_case.schemes)


def test_connector_error_wire_is_closed_and_safe() -> None:
    error = ConnectorError(
        code=ConnectorErrorCode.AUTHENTICATION,
        message="fixture authentication failed",
        safe_details={
            "host": "fixture.local",
            "token": "fixture-token",
            "nested": {"password": "fixture-secret", "attempt": 1},
        },
    )

    assert_error_is_safe(error)
    assert "fixture-token" not in json.dumps(error.to_wire(), sort_keys=True)


def test_invalid_credential_bearing_uris_are_rejected(
    invalid_credential_bearing_uris: tuple[str, ...],
) -> None:
    for uri_value in invalid_credential_bearing_uris:
        with pytest.raises(ValueError):
            TableURI(uri_value)


@pytest.mark.parametrize("connector_case", _READ_ARROW_CASE_NAMES, ids=str, indirect=True)
def test_read_receipt_wire_is_closed_and_metadata_is_deterministic(
    connector_case: ConnectorCase,
) -> None:
    binding = connector_case.capability_binding("table.read.arrow")
    first = binding.read_arrow(ResourceLimits())
    second = binding.read_arrow(ResourceLimits())

    assert_receipt_matches_table(
        first.receipt,
        first.table,
        expected_connector=connector_case.identity,
        expected_capability=binding.capability,
        expected_mode=first.receipt.mode,
        expected_safe_uri=connector_case.table_uri,
    )
    assert second.receipt.to_wire() == first.receipt.to_wire()


@pytest.mark.parametrize("connector_case", _INSPECT_CASE_NAMES, ids=str, indirect=True)
def test_inspection_metadata_is_stable_and_matches_read_receipts(
    connector_case: ConnectorCase,
) -> None:
    inspection = connector_case.inspect(ResourceLimits())
    repeated = connector_case.inspect(ResourceLimits())

    assert inspection.safe_uri == connector_case.table_uri
    assert inspection.mode in connector_case.modes
    assert inspection.columns
    assert inspection.schema_fingerprint == repeated.schema_fingerprint
    assert inspection.row_count == repeated.row_count
    if "table.read.arrow" in connector_case.capabilities:
        result = connector_case.capability_binding("table.read.arrow").read_arrow(ResourceLimits())
        assert inspection.schema_fingerprint == result.receipt.schema_fingerprint
        assert inspection.row_count == result.table.num_rows


@pytest.mark.parametrize("connector_case", _WRITE_CASE_NAMES, ids=str, indirect=True)
def test_write_receipt_wire_is_closed_and_safe(
    connector_case: ConnectorCase,
    write_frame: pl.DataFrame,
    expected_write_affected_rows_by_case: dict[str, int],
    write_if_exists_by_case: dict[str, str],
) -> None:
    result = connector_case.write(write_frame, write_if_exists_by_case[connector_case.name])

    assert result.affected_rows == expected_write_affected_rows_by_case[connector_case.name]
    assert_receipt_matches_table(
        result.receipt,
        _canonical_write_table(connector_case, write_frame),
        expected_connector=connector_case.identity,
        expected_capability="table.write",
        expected_mode=result.receipt.mode,
        expected_safe_uri=connector_case.table_uri,
    )
