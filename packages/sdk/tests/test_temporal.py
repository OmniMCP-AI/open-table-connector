from __future__ import annotations

from datetime import UTC, datetime

import open_table_connector.sdk as otc
import polars as pl
import pytest

from packages.timeseries.tests.fixtures import descriptor as temporal_descriptor


def _event_frame(symbol: str, venue: str, price: float, size: int) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "ts": [datetime(2026, 8, 29, 0, 30, 0, tzinfo=UTC)],
            "symbol": [symbol],
            "venue": [venue],
            "price": [price],
            "size": [size],
            "received_at": [datetime(2026, 8, 29, 0, 30, 1, tzinfo=UTC)],
        }
    ).cast(
        {
            "ts": pl.Datetime("ns", "UTC"),
            "received_at": pl.Datetime("ns", "UTC"),
        }
    )


def test_time_series_helpers_build_queries_and_collect(fake_connector) -> None:
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    table = client.open("fake://warehouse/orders").require_value()
    series = table.time_series(temporal_descriptor())

    latest = series.latest(
        at_or_before="2026-08-29T00:05:00.000000000Z",
        columns=("ts", "symbol", "venue", "price"),
    )
    assert latest.lane is otc.QueryLane.TEMPORAL

    latest_result = client.collect(latest)
    latest_frame = latest_result.require_value()
    latest_payload = latest_frame.to_dict(as_series=False)
    assert [value.isoformat() for value in latest_payload["ts"]] == [
        "2026-08-29T00:05:00+00:00",
        "2026-08-29T00:05:00+00:00",
    ]
    assert latest_payload["symbol"] == ["AAPL", "MSFT"]
    assert latest_payload["venue"] == ["XNAS", "ARCX"]
    assert latest_payload["price"] == [102.0, 202.0]
    assert latest_result.receipts[-1].details["plan_hash"] == latest.plan_hash
    assert latest_result.receipts[-1].details["definition_hash"] == latest.definition_hash

    scan = series.scan_range(
        "2026-08-29T00:00:00.000000000Z",
        "2026-08-29T00:10:00.000000000Z",
        columns=("ts", "symbol", "price"),
    )
    scan_frame = client.collect(scan).require_value()
    assert scan_frame.height == 4


def test_time_series_aggregate_and_gap_fill_collect(fake_connector) -> None:
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    table = client.open("fake://warehouse/orders").require_value()
    series = table.time_series(temporal_descriptor())
    bucket = otc.FixedBucket(
        width_ns=300_000_000_000,
        origin="2026-08-29T00:00:00.000000000Z",
    )
    measures = (otc.AggregateMeasure("sum_size", otc.AggregateFunction.SUM, "size"),)

    aggregate = series.aggregate(
        "2026-08-29T00:00:00.000000000Z",
        "2026-08-29T00:10:00.000000000Z",
        bucket=bucket,
        group_by=("symbol",),
        measures=measures,
    )
    aggregate_frame = client.collect(aggregate).require_value()
    assert aggregate_frame.to_dict(as_series=False)["sum_size"] == [10, 12, 20, 22]

    gap_fill = series.gap_fill(
        "2026-08-29T00:00:00.000000000Z",
        "2026-08-29T00:15:00.000000000Z",
        bucket=bucket,
        group_by=("symbol",),
        measures=measures,
        fills=(otc.FillRule("sum_size", otc.FillMode.CONSTANT, 0),),
    )
    gap_frame = client.collect(gap_fill).require_value()
    assert gap_frame.height == 6
    assert gap_frame.to_dict(as_series=False)["sum_size"].count(0) == 1


def test_time_series_append_upsert_and_storage_lifecycle(fake_connector) -> None:
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    table = client.open("fake://warehouse/orders").require_value()
    series = table.time_series(temporal_descriptor())
    frame = _event_frame("AAPL", "XNAS", 111.0, 14)

    appended = series.append(frame, idempotency_key="append-1").require_value()
    upserted = series.upsert(frame, idempotency_key="upsert-1").require_value()
    assert appended == 1
    assert upserted == 1

    stage = series.storage.stage(
        frame,
        idempotency_key="stage-1",
        lease_expires_at="2026-08-29T00:40:00.000000000Z",
    ).require_value()
    snapshot = series.storage.commit(
        stage,
        retention_expires_at="2026-08-30T00:00:00.000000000Z",
    ).require_value()
    readback = series.storage.readback(snapshot).require_value()
    aborted = series.storage.abort(stage).require_value()

    assert readback.to_dict(as_series=False)["price"] == [111.0]
    assert aborted is otc.AbortDisposition.ALREADY_COMMITTED


def test_time_series_storage_expiry_and_reconciliation(fake_connector) -> None:
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    table = client.open("fake://warehouse/orders").require_value()
    series = table.time_series(temporal_descriptor())
    frame = _event_frame("MSFT", "XNYS", 205.0, 23)

    expired_stage = series.storage.stage(
        frame,
        idempotency_key="expired-stage",
        lease_expires_at="2026-08-28T00:00:00.000000000Z",
    ).require_value()

    with pytest.raises(otc.OTCError) as expired:
        series.storage.commit(expired_stage)

    assert expired.value.result.error is not None
    assert expired.value.result.error.code is otc.ErrorCode.INVALID_TARGET

    expired_abort_result = series.storage.abort(expired_stage)
    expired_abort = expired_abort_result.require_value()
    assert expired_abort is otc.AbortDisposition.EXPIRED
    assert expired_abort_result.receipts[0].kind == "managed-abort"
    assert expired_abort_result.receipts[0].details["disposition"] == "expired"
    assert expired_abort_result.receipts[0].details["provider_mutation"] is False

    healthy_stage = series.storage.stage(
        frame,
        idempotency_key="ambiguous-stage",
        lease_expires_at="2026-08-29T00:40:00.000000000Z",
    ).require_value()
    fake_connector.temporal_extension.ambiguous_commit = True

    with pytest.raises(otc.OTCError) as ambiguous:
        series.storage.commit(healthy_stage)

    assert ambiguous.value.result.error is not None
    assert ambiguous.value.result.error.code is otc.ErrorCode.UNCERTAIN_MUTATION
    assert ambiguous.value.result.error.reconciliation is not None
    assert (
        ambiguous.value.result.error.reconciliation.idempotency_key == healthy_stage.idempotency_key
    )


def test_temporal_query_identity_includes_the_portable_operation(fake_connector) -> None:
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    series = (
        client.open("fake://warehouse/orders").require_value().time_series(temporal_descriptor())
    )

    first = series.scan_range(
        "2026-08-29T00:00:00.000000000Z",
        "2026-08-29T00:10:00.000000000Z",
    )
    second = series.scan_range(
        "2026-08-29T00:05:00.000000000Z",
        "2026-08-29T00:15:00.000000000Z",
    )
    latest = series.latest(at_or_before="2026-08-29T00:05:00.000000000Z")

    assert first.plan_hash != second.plan_hash
    assert first.plan_hash != latest.plan_hash


def test_temporal_sql_lowers_scan_latest_bucket_and_gapfill_to_existing_queries(
    fake_connector,
) -> None:
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    series = (
        client.open("fake://warehouse/orders").require_value().time_series(temporal_descriptor())
    )
    parameters = {
        "1": "2026-08-29T00:00:00.000000000Z",
        "2": "2026-08-29T00:10:00.000000000Z",
        "3": "2026-08-29T00:15:00.000000000Z",
    }

    scan = series.sql(
        """
        SELECT ts, symbol, price FROM series
        WHERE ts >= $1 AND ts < $2
        ORDER BY symbol, ts LIMIT 100
        """,
        parameters=parameters,
    )
    latest = series.sql(
        """
        SELECT symbol, last(price, ts) AS price FROM series
        WHERE ts <= $2 GROUP BY symbol
        ORDER BY symbol LIMIT 100
        """,
        parameters=parameters,
    )
    aggregate = series.sql(
        """
        SELECT time_bucket('5 minutes', ts) AS bucket, symbol,
               sum(size) AS total_size
        FROM series WHERE ts >= $1 AND ts < $2
        GROUP BY bucket, symbol ORDER BY symbol, bucket LIMIT 100
        """,
        parameters=parameters,
    )
    gap_fill = series.sql(
        """
        SELECT time_bucket_gapfill('5 minutes', ts) AS bucket, symbol,
               locf(sum(size)) AS total_size
        FROM series WHERE ts >= $1 AND ts < $3
        GROUP BY bucket, symbol ORDER BY symbol, bucket LIMIT 100
        """,
        parameters=parameters,
    )

    assert client.collect(scan).require_value().height == 4
    assert client.collect(latest).require_value().height == 2
    assert client.collect(aggregate).require_value().to_dict(as_series=False)["total_size"] == [
        10,
        12,
        20,
        22,
    ]
    gap = client.collect(gap_fill).require_value()
    assert gap.height == 6
    assert gap.to_dict(as_series=False)["total_size"] == [10, 12, 13, 20, 22, 22]


def test_temporal_sql_rejects_asof_and_unbounded_ranges(fake_connector) -> None:
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    series = (
        client.open("fake://warehouse/orders").require_value().time_series(temporal_descriptor())
    )

    with pytest.raises(otc.OTCError) as unbounded:
        series.sql(
            "SELECT ts, symbol FROM series ORDER BY symbol, ts LIMIT 100",
            parameters={},
        )
    assert unbounded.value.result.error is not None
    assert unbounded.value.result.error.code is otc.ErrorCode.INVALID_SQL

    with pytest.raises(otc.OTCError) as asof:
        series.sql(
            "SELECT * FROM series AS OF $1 ORDER BY symbol, ts LIMIT 100",
            parameters={"1": "2026-08-29T00:05:00.000000000Z"},
        )
    assert asof.value.result.error is not None
    assert asof.value.result.error.code is otc.ErrorCode.INVALID_SQL
