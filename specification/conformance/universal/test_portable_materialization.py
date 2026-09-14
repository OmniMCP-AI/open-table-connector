from __future__ import annotations

import json

import open_table_connector.sdk as otc
import pytest

from specification.conformance.universal.assertions import assert_sdk_materialization_safe
from specification.conformance.universal.fixtures import portable_materialization_cases


@pytest.mark.parametrize("case", portable_materialization_cases(), ids=lambda item: item.name)
def test_portable_materialization_case_replays_and_reads_from_a_fresh_client(case) -> None:
    first_client, fresh_client = case.make_clients()

    first = first_client.materialize(
        case.source,
        to=case.destination,
        profile=otc.PORTABLE_TABLE_PROFILE_V1,
        idempotency_key="universal-materialization-1",
    )
    replay = first_client.materialize(
        case.source,
        to=case.destination,
        profile=otc.PORTABLE_TABLE_PROFILE_V1,
        idempotency_key="universal-materialization-1",
    )
    readback = fresh_client.open(first.require_value().uri).require_value().read()
    process_readback = case.read_in_fresh_process(first.require_value().uri)

    assert replay.require_value().uri == first.require_value().uri
    assert readback.require_value().equals(case.source)
    assert process_readback.equals(case.source)

    with pytest.raises(otc.OTCError) as raised:
        first_client.materialize(
            case.changed_source,
            to=case.destination,
            profile=otc.PORTABLE_TABLE_PROFILE_V1,
            idempotency_key="universal-materialization-1",
        )
    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.IDEMPOTENCY_CONFLICT


@pytest.mark.parametrize("case", portable_materialization_cases(), ids=lambda item: item.name)
def test_portable_materialization_case_keeps_receipts_and_results_secret_safe(case) -> None:
    client, _ = case.make_clients()
    result = client.materialize(
        case.source,
        to=case.destination,
        profile=otc.PORTABLE_TABLE_PROFILE_V1,
        idempotency_key="universal-materialization-2",
    )
    error = otc.ErrorInfo(
        code=otc.ErrorCode.UNCERTAIN_MUTATION,
        message="provider response is uncertain",
        safe_details={"token": "fixture-secret", "attempt": 1},
    )
    failed = otc.OperationResult(
        value=None,
        outcome=otc.Outcome.UNKNOWN,
        commit=otc.CommitState.UNKNOWN,
        verification=otc.VerificationState.UNAVAILABLE,
        receipts=result.receipts,
        error=error,
    )

    assert_sdk_materialization_safe(result.receipts, failed, forbidden_values=(
        "fixture-secret",
        "universal-materialization-2",
    ))
    assert "fixture-secret" not in json.dumps(failed.to_wire(), sort_keys=True)
