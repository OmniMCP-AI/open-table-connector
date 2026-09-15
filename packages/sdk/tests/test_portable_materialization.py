from __future__ import annotations

import math
from dataclasses import replace

import open_table_connector.sdk as otc
import polars as pl
import pytest
from open_table_connector.contract import MaterializationCapability, TableMode


def _advertise_portable_create(fake_connector, *modes: TableMode) -> None:
    fake_connector.capabilities += (otc.MATERIALIZE_CREATE_CAPABILITY,)
    fake_connector.materialization = (
        MaterializationCapability(
            capability=otc.MATERIALIZE_CREATE_CAPABILITY,
            profiles=(otc.PORTABLE_TABLE_PROFILE_V1,),
            modes=modes,
        ),
    )


def test_portable_materialization_request_has_stable_logical_fingerprints() -> None:
    request = otc.MaterializationRequest(
        source=pl.DataFrame(
            {
                "name": ["東京", ""],
                "amount": [1, None],
            },
            schema={"name": pl.String, "amount": pl.Int64},
        ),
        destination=otc.DirectDestination("fake://warehouse/portable"),
        profile=otc.PORTABLE_TABLE_PROFILE_V1,
        idempotency_key="materialize-001",
    )

    assert request.schema_fingerprint.startswith("sha256:")
    assert request.content_fingerprint.startswith("sha256:")
    assert request.row_count == 2


@pytest.mark.parametrize(
    "frame",
    [
        pl.DataFrame({"values": [["not portable"]]}),
        pl.DataFrame({"values": [math.nan]}, schema={"values": pl.Float64}),
    ],
)
def test_portable_materialization_rejects_invalid_schema_before_dispatch(
    fake_connector, frame: pl.DataFrame
) -> None:
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))

    with pytest.raises(otc.OTCError) as raised:
        client.materialize(
            frame,
            to=otc.DirectDestination("fake://warehouse/portable"),
            profile=otc.PORTABLE_TABLE_PROFILE_V1,
            idempotency_key="materialize-002",
        )

    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.INVALID_SCHEMA
    assert not any(call[0] == "create_table" for call in fake_connector.calls)


def test_portable_materialization_rejects_missing_or_secret_key_before_dispatch(
    fake_connector,
) -> None:
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))

    for key in (None, "Bearer secret-value"):
        with pytest.raises(otc.OTCError) as raised:
            client.materialize(
                pl.DataFrame({"id": [1]}),
                to=otc.DirectDestination("fake://warehouse/portable"),
                profile=otc.PORTABLE_TABLE_PROFILE_V1,
                idempotency_key=key,
            )
        assert raised.value.result.error is not None
        assert raised.value.result.error.code is otc.ErrorCode.INVALID_CONFIGURATION

    assert not any(call[0] == "create_table" for call in fake_connector.calls)


def test_portable_materialize_dispatches_structured_request_and_returns_evidence(
    fake_connector,
) -> None:
    _advertise_portable_create(fake_connector, TableMode.BASE)
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))

    result = client.materialize(
        pl.DataFrame({"id": [1]}),
        to=otc.DirectDestination("fake://warehouse/portable"),
        profile=otc.PORTABLE_TABLE_PROFILE_V1,
        idempotency_key="materialize-003",
    )

    request = next(call[1] for call in fake_connector.calls if call[0] == "create_table")
    binding = result.require_value()._binding
    assert isinstance(request, otc.MaterializationRequest)
    assert request.idempotency_key == "materialize-003"
    assert binding.profile == otc.PORTABLE_TABLE_PROFILE_V1
    assert binding.row_count == 1
    assert binding.schema_fingerprint == request.schema_fingerprint
    assert binding.content_fingerprint == request.content_fingerprint


def test_portable_materialize_requires_exact_advertised_profile_and_mode_before_dispatch(
    fake_connector,
) -> None:
    fake_connector.capabilities += (otc.MATERIALIZE_CREATE_CAPABILITY,)
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))

    with pytest.raises(otc.OTCError) as raised:
        client.materialize(
            pl.DataFrame({"id": [1]}),
            to=otc.DirectDestination("fake://warehouse/portable"),
            profile=otc.PORTABLE_TABLE_PROFILE_V1,
            idempotency_key="materialize-004",
        )

    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.UNSUPPORTED_CAPABILITY
    assert not any(call[0] == "create_table" for call in fake_connector.calls)


def test_portable_materialize_rejects_an_advertised_profile_for_the_wrong_mode(
    fake_connector,
) -> None:
    _advertise_portable_create(fake_connector, TableMode.SHEET)
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))

    with pytest.raises(otc.OTCError) as raised:
        client.materialize(
            pl.DataFrame({"id": [1]}),
            to=otc.DirectDestination("fake://warehouse/portable"),
            profile=otc.PORTABLE_TABLE_PROFILE_V1,
            idempotency_key="materialize-004-mode",
        )

    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.UNSUPPORTED_CAPABILITY
    assert not any(call[0] == "create_table" for call in fake_connector.calls)


def test_portable_materialization_conformance_replays_and_reads_from_a_fresh_client(
    fake_connector,
) -> None:
    _advertise_portable_create(fake_connector, TableMode.BASE)
    first_client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    destination = otc.DirectDestination("fake://warehouse/portable")
    frame = pl.DataFrame({"id": [1], "label": ["東京"]})

    first = first_client.materialize(
        frame,
        to=destination,
        profile=otc.PORTABLE_TABLE_PROFILE_V1,
        idempotency_key="materialize-005",
    )
    replay = first_client.materialize(
        frame,
        to=destination,
        profile=otc.PORTABLE_TABLE_PROFILE_V1,
        idempotency_key="materialize-005",
    )
    fresh_client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    readback = fresh_client.open("fake://warehouse/portable").require_value().read()

    assert replay.require_value().uri == first.require_value().uri
    assert readback.require_value().equals(frame)

    with pytest.raises(otc.OTCError) as raised:
        first_client.materialize(
            pl.DataFrame({"id": [2], "label": ["changed"]}),
            to=destination,
            profile=otc.PORTABLE_TABLE_PROFILE_V1,
            idempotency_key="materialize-005",
        )
    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.IDEMPOTENCY_CONFLICT


def test_portable_materialization_conformance_receipts_and_errors_are_secret_safe(
    fake_connector,
) -> None:
    _advertise_portable_create(fake_connector, TableMode.BASE)
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))

    result = client.materialize(
        pl.DataFrame({"id": [1]}),
        to=otc.DirectDestination("fake://warehouse/portable"),
        profile=otc.PORTABLE_TABLE_PROFILE_V1,
        idempotency_key="materialize-006",
    )

    assert "materialize-006" not in repr(tuple(receipt.to_wire() for receipt in result.receipts))
    error = otc.ErrorInfo(
        code=otc.ErrorCode.UNCERTAIN_MUTATION,
        message="provider response is uncertain",
        safe_details={"token": "secret-value", "attempt": 1},
    )
    assert "secret-value" not in repr(error.to_wire())
    failed = otc.OperationResult(
        value=None,
        outcome=otc.Outcome.UNKNOWN,
        commit=otc.CommitState.UNKNOWN,
        verification=otc.VerificationState.UNAVAILABLE,
        receipts=result.receipts,
        error=error,
    )
    assert "secret-value" not in repr(failed.to_wire())


def test_portable_materialize_rejects_connector_success_with_bad_evidence(fake_connector) -> None:
    _advertise_portable_create(fake_connector, TableMode.BASE)
    def bad_create(request, destination):
        delivered = fake_connector.__class__.create_table(fake_connector, request, destination)
        return replace(
            delivered,
            value=replace(delivered.require_value(), row_count=999),
            warnings=(otc.OperationWarning("provider-warning", "safe warning"),),
        )
    fake_connector.create_table = bad_create
    with pytest.raises(otc.OTCError) as raised:
        otc.Client(registry=otc.ConnectorRegistry([fake_connector])).materialize(
            pl.DataFrame({"id": [1]}), to=otc.DirectDestination("fake://warehouse/portable"),
            profile=otc.PORTABLE_TABLE_PROFILE_V1, idempotency_key="postcondition",
        )
    result = raised.value.result
    assert result.error.code is otc.ErrorCode.PROTOCOL_FAILURE
    assert result.outcome is otc.Outcome.FAILED
    assert result.commit is otc.CommitState.COMMITTED
    assert result.verification is otc.VerificationState.FAILED
    assert [receipt.operation for receipt in result.receipts] == ["table.create", "table.read"]
    assert result.warnings[0].code == "provider-warning"
