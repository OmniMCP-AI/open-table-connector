from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import open_table_connector.sdk as otc
import polars as pl
from open_table_connector.sqlite import SQLiteConnector

from packages.timeseries.tests.fixtures import descriptor as make_descriptor


def _frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "ts": [
                datetime(2026, 8, 29, 0, 1, tzinfo=UTC),
                datetime(2026, 8, 29, 0, 6, tzinfo=UTC),
            ],
            "symbol": ["AAPL", "AAPL"],
            "venue": ["XNAS", "XNAS"],
            "price": [100.0, 102.0],
            "size": [10, 12],
            "received_at": [
                datetime(2026, 8, 29, 0, 1, 1, tzinfo=UTC),
                datetime(2026, 8, 29, 0, 6, 1, tzinfo=UTC),
            ],
        }
    ).cast({"ts": pl.Datetime("ns", "UTC"), "received_at": pl.Datetime("ns", "UTC")})


def _table(client: otc.Client, path: Path, frame: pl.DataFrame) -> otc.Table:
    return client.materialize(
        pl.DataFrame(schema=frame.schema),
        to=otc.BaseModeDestination(f"sqlite://{path.as_posix()}", "ticks"),
    ).require_value()


def test_public_sdk_sql_profile_executes_against_real_sqlite(tmp_path: Path) -> None:
    frame = _frame()
    client = otc.Client(registry=otc.ConnectorRegistry([SQLiteConnector()]))
    table = _table(client, tmp_path / "ticks.db", frame)
    series = table.time_series(make_descriptor())
    snapshot = series.storage.commit(
        series.storage.stage(frame, idempotency_key="sql-profile").require_value()
    ).require_value()

    scan = series.sql(
        "SELECT ts, symbol, price FROM series "
        "WHERE ts >= $1 AND ts < $2 AND symbol = $3 "
        "ORDER BY symbol, ts LIMIT 100",
        parameters={
            "1": "2026-08-29T00:00:00.000000000Z",
            "2": "2026-08-29T01:00:00.000000000Z",
            "3": "AAPL",
        },
        snapshot_reference=snapshot.snapshot_reference,
    )
    result = client.collect(scan)
    assert result.require_value().to_dict(as_series=False)["price"] == [100.0, 102.0]
    assert result.receipts[-1].details["snapshot_reference"] == snapshot.snapshot_reference

    aggregate = series.sql(
        "SELECT time_bucket('5 minutes', ts) AS bucket, symbol, "
        "sum(size) AS total_size FROM series "
        "WHERE ts >= $1 AND ts < $2 GROUP BY bucket, symbol "
        "ORDER BY symbol, bucket LIMIT 100",
        parameters={
            "1": "2026-08-29T00:00:00.000000000Z",
            "2": "2026-08-29T01:00:00.000000000Z",
        },
        snapshot_reference=snapshot.snapshot_reference,
    )
    assert client.collect(aggregate).require_value().to_dict(as_series=False)["total_size"] == [
        10,
        12,
    ]


def test_public_sdk_typed_latest_and_as_of_helpers_remain_available(tmp_path: Path) -> None:
    frame = _frame()
    client = otc.Client(registry=otc.ConnectorRegistry([SQLiteConnector()]))
    table = _table(client, tmp_path / "ticks.db", frame)
    series = table.time_series(make_descriptor())

    assert (
        series.latest(at_or_before="2026-08-29T00:10:00.000000000Z").lane is otc.QueryLane.TEMPORAL
    )
    assert series.as_of("2026-08-29T00:10:00.000000000Z").lane is otc.QueryLane.TEMPORAL
