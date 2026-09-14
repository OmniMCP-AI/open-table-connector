from __future__ import annotations

import math

import open_table_connector.sdk as otc
import polars as pl
import pytest


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
    fake_connector.capabilities += (otc.MATERIALIZE_CREATE_CAPABILITY,)
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
