from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import open_table_connector.sdk as otc
import polars as pl
import pytest
from open_table_connector.sqlite import SQLiteConnector

from packages.timeseries.tests.fixtures import descriptor as make_descriptor


@pytest.fixture
def descriptor():
    return make_descriptor()


@pytest.fixture
def observation_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "ts": [datetime(2026, 8, 29, 0, 30, 0, tzinfo=UTC)],
            "symbol": ["AAPL"],
            "venue": ["XNAS"],
            "price": [111.0],
            "size": [14],
            "received_at": [datetime(2026, 8, 29, 0, 30, 1, tzinfo=UTC)],
        }
    ).cast(
        {
            "ts": pl.Datetime("ns", "UTC"),
            "received_at": pl.Datetime("ns", "UTC"),
        }
    )


def configured_client(connector: SQLiteConnector) -> otc.Client:
    return otc.Client(registry=otc.ConnectorRegistry([connector]))


def sqlite_uri(path: Path) -> str:
    return f"sqlite://{path.as_posix()}"


def open_sqlite_table(client: otc.Client, path: Path, schema: pl.Schema) -> otc.Table:
    return client.materialize(
        pl.DataFrame(schema=schema),
        to=otc.BaseModeDestination(sqlite_uri(path), "ticks"),
    ).require_value()


def test_real_sqlite_sdk_managed_snapshot_round_trip(
    tmp_path: Path,
    observation_frame: pl.DataFrame,
    descriptor,
) -> None:
    client = configured_client(SQLiteConnector())
    table = open_sqlite_table(client, tmp_path / "otc.sqlite", observation_frame.schema)
    series = table.time_series(descriptor)

    stage = series.storage.stage(observation_frame, idempotency_key="commit-1").require_value()
    snapshot = series.storage.commit(stage).require_value()
    actual = series.storage.readback(snapshot).require_value()

    assert actual.equals(observation_frame)
    assert snapshot.snapshot_reference
