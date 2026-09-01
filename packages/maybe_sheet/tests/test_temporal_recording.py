from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from open_table_connector.contract import TableURI
from open_table_connector.maybe_sheet import MaybeSheetTemporalExecutor
from open_table_connector.timeseries import (
    PolarsTemporalExecutor,
    TemporalErrorCode,
    TemporalExecutionRequest,
    TemporalExtensionError,
)

from packages.local_files.tests.test_temporal_csv import operations
from packages.timeseries.tests.fixtures import MemoryTemporalSource, bounds, descriptor

FIXTURES = Path(__file__).parent / "fixtures"


class RecordingTemporalProcess:
    def __init__(self, description=None, read_result=None):
        self.description = description or json.loads(
            (FIXTURES / "temporal-describe.json").read_text()
        )
        self.read_result = read_result or json.loads(
            (FIXTURES / "temporal-read.jsonl").read_text()
        )
        self.calls = []

    def run(self, argv, *, credentials=None, stdin=None, timeout=None):
        self.calls.append((argv, credentials, stdin, timeout))
        if argv[2] == "describe":
            return self.description
        if argv[2] == "read":
            return self.read_result
        raise AssertionError(f"unexpected command: {argv}")


def test_recording_read_is_bounded_credential_isolated_and_connector_evaluated() -> None:
    process = RecordingTemporalProcess()
    secret = "recording-access-token"
    executor = MaybeSheetTemporalExecutor(
        process,
        descriptor(),
        credential_resolver=lambda reference: {"access_token": secret}
        if reference == "credential-ref"
        else {},
    )
    target = TableURI("maybe://document/ticks")

    for plan in operations():
        request = TemporalExecutionRequest(
            target,
            plan,
            "credential-ref",
            f"mbs-{type(plan.operation).__name__}",
            None,
        )
        actual = executor.execute(request)
        expected = PolarsTemporalExecutor(MemoryTemporalSource()).execute(request)
        assert actual.table is not None and expected.table is not None
        assert actual.table.equals(expected.table)
        assert actual.receipt.execution_location.value == "connector"

    assert [call[0][2] for call in process.calls].count("describe") == 1
    for argv, credentials, stdin, timeout in process.calls[1:]:
        assert argv == ("mbs", "timeseries", "read", "--input", "-")
        assert credentials == {"access_token": secret}
        document = json.loads(stdin)
        assert document["resource_bounds"] == operations()[0].resource_bounds.to_wire()
        assert "credential" not in stdin.casefold()
        assert secret not in repr(argv)
        assert secret not in stdin
        assert timeout == operations()[0].resource_bounds.max_duration_ms / 1000


def test_recording_read_rejects_provider_over_return() -> None:
    process = RecordingTemporalProcess()
    plan = replace(operations()[0], resource_bounds=bounds(max_rows=1))
    executor = MaybeSheetTemporalExecutor(process, descriptor())

    with pytest.raises(TemporalExtensionError) as error:
        executor.execute(
            TemporalExecutionRequest(
                TableURI("maybe://document/ticks"), plan, None, "over-return", None
            )
        )

    assert error.value.code is TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED
