from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import open_table_connector.sdk as otc
import polars as pl
from open_table_connector.local_files import LocalFilesConnector
from open_table_connector.timeseries import DuplicatePolicy

from packages.timeseries.tests.fixtures import descriptor as make_descriptor
from packages.timeseries.tests.fixtures import ticks_table


def configured_client(connector: LocalFilesConnector) -> otc.Client:
    return otc.Client(registry=otc.ConnectorRegistry([connector]))


def write_captured_csv(path: Path) -> pl.DataFrame:
    frame = pl.from_arrow(ticks_table())
    frame.write_csv(path)
    return frame


def test_real_local_files_sdk_scan_range_reads_captured_csv(tmp_path: Path) -> None:
    source = tmp_path / "ticks.csv"
    expected = write_captured_csv(source)
    client = configured_client(LocalFilesConnector())
    table = client.open(source.as_posix()).require_value()
    series = table.time_series(make_descriptor(DuplicatePolicy.PRESERVE))

    result = client.collect(
        series.scan_range(
            "2026-08-29T00:00:00.000000000Z",
            "2026-08-29T00:10:00.000000000Z",
            columns=("ts", "symbol", "venue", "price"),
        )
    )
    actual = result.require_value().sort(["symbol", "ts", "venue", "price"])

    assert actual.equals(
        expected.filter(
            (pl.col("ts") >= datetime(2026, 8, 29, tzinfo=UTC))
            & (pl.col("ts") < datetime(2026, 8, 29, 0, 10, tzinfo=UTC))
        )
        .select("ts", "symbol", "venue", "price")
        .sort(["symbol", "ts", "venue", "price"])
    )
    assert result.receipts[-1].connector_id == "local_files"
