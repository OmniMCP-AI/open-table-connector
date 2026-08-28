from __future__ import annotations

import polars as pl
import pyarrow as pa
import pytest

from open_table_connector.contract import (
    ConnectorError,
    ConnectorErrorCode,
    ResourceLimits,
    TableInspection,
    TableMode,
    TableURI,
)

from specification.conformance.universal.assertions import (
    assert_error_is_safe,
    assert_receipt_matches_table,
    assert_safe_uri,
)
from specification.conformance.universal.cases import ConnectorCase

_CASE_NAMES = (
    "local_files",
    "google_sheets",
    "feishu_bitable",
    "maybesheet",
    "sqlite",
    "postgres",
    "dbt",
)
_READ_ARROW_CASE_NAMES = (
    "local_files",
    "google_sheets",
    "feishu_bitable",
    "sqlite",
    "postgres",
)
_INSPECT_CASE_NAMES = _READ_ARROW_CASE_NAMES
_SHARED_INSPECT_READ_CASE_NAMES = (
    "local_files",
    "google_sheets",
    "feishu_bitable",
)
_WRITE_CASE_NAMES = (
    "google_sheets",
    "feishu_bitable",
    "maybesheet",
    "sqlite",
    "postgres",
)


def _canonical_write_table(connector_case: ConnectorCase, write_frame: pl.DataFrame) -> pa.Table:
    if connector_case.name in {"google_sheets", "feishu_bitable"}:
        return pa.Table.from_pydict(
            {
                name: write_frame.get_column(name).to_list()
                for name in write_frame.columns
            }
        )
    return write_frame.to_arrow()


def _stable_inspection_metadata(inspection: TableInspection) -> dict[str, object]:
    return {
        "safe_uri": inspection.safe_uri,
        "mode": inspection.mode,
        "columns": inspection.columns,
        "schema_fingerprint": inspection.schema_fingerprint,
        "row_count": inspection.row_count,
        "coordinate_convention": inspection.coordinate_convention,
        "facts": dict(inspection.facts),
    }


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


def test_invalid_credential_bearing_uris_are_rejected(
    invalid_credential_bearing_uri: str,
) -> None:
    with pytest.raises(ValueError, match="credential"):
        TableURI(invalid_credential_bearing_uri)


@pytest.mark.parametrize("connector_case", _READ_ARROW_CASE_NAMES, ids=str, indirect=True)
def test_read_receipt_wire_is_closed_and_metadata_is_deterministic(
    connector_case: ConnectorCase,
) -> None:
    binding = connector_case.capability_binding("table.read.arrow")
    first = binding.read_arrow(ResourceLimits())
    second = binding.read_arrow(ResourceLimits())

    assert binding.expected_mode is not None
    assert_receipt_matches_table(
        first.receipt,
        first.table,
        expected_connector=connector_case.identity,
        expected_capability=binding.capability,
        expected_mode=binding.expected_mode,
        expected_safe_uri=connector_case.table_uri,
    )
    assert second.receipt.to_wire() == first.receipt.to_wire()


@pytest.mark.parametrize("connector_case", _INSPECT_CASE_NAMES, ids=str, indirect=True)
def test_inspection_metadata_is_stable(
    connector_case: ConnectorCase,
) -> None:
    binding = connector_case.capability_binding("table.inspect")
    inspection = binding.inspect(ResourceLimits())
    repeated = binding.inspect(ResourceLimits())

    assert binding.expected_mode is not None
    assert inspection.safe_uri == connector_case.table_uri
    assert inspection.mode is binding.expected_mode
    assert inspection.columns
    assert _stable_inspection_metadata(repeated) == _stable_inspection_metadata(inspection)


@pytest.mark.parametrize(
    "connector_case",
    _SHARED_INSPECT_READ_CASE_NAMES,
    ids=str,
    indirect=True,
)
def test_inspection_matches_the_case_read_resource(
    connector_case: ConnectorCase,
) -> None:
    inspection = connector_case.capability_binding("table.inspect").inspect(
        ResourceLimits()
    )
    result = connector_case.capability_binding("table.read.arrow").read_arrow(
        ResourceLimits()
    )

    assert inspection.columns == tuple(result.table.column_names)
    assert inspection.schema_fingerprint == result.receipt.schema_fingerprint
    assert inspection.row_count == result.table.num_rows


@pytest.mark.parametrize("connector_case", _WRITE_CASE_NAMES, ids=str, indirect=True)
def test_write_receipt_wire_is_closed_and_safe(
    connector_case: ConnectorCase,
    write_frame: pl.DataFrame,
    write_if_exists_by_case: dict[str, str],
) -> None:
    binding = connector_case.capability_binding("table.write")
    result = binding.write(write_frame, write_if_exists_by_case[connector_case.name])

    assert binding.expected_mode is not None
    assert_receipt_matches_table(
        result.receipt,
        _canonical_write_table(connector_case, write_frame),
        expected_connector=connector_case.identity,
        expected_capability="table.write",
        expected_mode=binding.expected_mode,
        expected_safe_uri=connector_case.table_uri,
    )


@pytest.mark.parametrize("connector_case", ("sqlite",), ids=str, indirect=True)
def test_sqlite_case_starts_with_canonical_fixture_rows(
    connector_case: ConnectorCase,
) -> None:
    result = connector_case.capability_binding("table.read.arrow").read_arrow(
        ResourceLimits()
    )

    assert result.table.to_pylist() == [
        {"id": "a", "amount": "1.00"},
        {"id": "b", "amount": None},
    ]
