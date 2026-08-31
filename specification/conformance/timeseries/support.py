from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import openpyxl
import pyarrow as pa

from open_table_connector.contract import TableURI
from open_table_connector.timeseries import (
    DuplicatePolicy,
    ResourceBounds,
    TemporalTableDescriptor,
    TemporalOrdering,
    TimestampPrecision,
)


def ns(minutes: int, extra_ns: int = 0) -> int:
    return 1_787_961_600_000_000_000 + minutes * 60_000_000_000 + extra_ns


def ticks_table() -> pa.Table:
    order = [3, 0, 5, 2, 6, 1, 4]
    rows = {
        "ts": [ns(10), ns(0, 123), ns(5), ns(5), ns(0), ns(5), ns(5)],
        "symbol": ["AAPL", "AAPL", "AAPL", "AAPL", "MSFT", "MSFT", "MSFT"],
        "venue": ["XNAS", "XNAS", "XNAS", "XNAS", "XNYS", "XNYS", "ARCX"],
        "price": [103.0, 100.0, 101.0, 102.0, 200.0, None, 202.0],
        "size": [13, 10, 11, 12, 20, 21, 22],
        "received_at": [ns(10, 1), ns(0, 124), ns(5, 1), ns(5, 2), ns(0, 1), ns(5, 1), ns(5, 2)],
    }
    arrays = [
        pa.array([rows["ts"][index] for index in order], type=pa.timestamp("ns", tz="UTC")),
        pa.array([rows["symbol"][index] for index in order]),
        pa.array([rows["venue"][index] for index in order]),
        pa.array([rows["price"][index] for index in order], type=pa.float64()),
        pa.array([rows["size"][index] for index in order], type=pa.int64()),
        pa.array([rows["received_at"][index] for index in order], type=pa.timestamp("ns", tz="UTC")),
    ]
    return pa.Table.from_arrays(arrays, names=["ts", "symbol", "venue", "price", "size", "received_at"])


def descriptor() -> TemporalTableDescriptor:
    return TemporalTableDescriptor(
        time_field="ts", timezone="UTC", precision=TimestampPrecision.NANOSECOND,
        series_key_fields=("symbol",), tag_fields=("venue",), value_fields=("price", "size"),
        ingestion_time_field="received_at", duplicate_policy=DuplicatePolicy.REPLACE_LATEST,
        ordering=TemporalOrdering.UNSPECIFIED,
    )


class MemoryTemporalSource:
    def __init__(self) -> None:
        self.table = ticks_table()
        self.descriptor = descriptor()

    def read_bounded(self, target, projection, predicates, bounds):
        del target, predicates, bounds
        return self.table.select(projection)


def create_ticks(path: Path) -> None:
    table = ticks_table()
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE ticks (ts INTEGER, symbol TEXT, venue TEXT, price REAL, size INTEGER, received_at INTEGER)")
        rows = list(zip(
            table["ts"].cast(pa.int64()).to_pylist(), table["symbol"].to_pylist(),
            table["venue"].to_pylist(), table["price"].to_pylist(), table["size"].to_pylist(),
            table["received_at"].cast(pa.int64()).to_pylist(), strict=True,
        ))
        connection.executemany("INSERT INTO ticks VALUES (?, ?, ?, ?, ?, ?)", rows)


def sqlite_uri(path: Path) -> TableURI:
    return TableURI(f"sqlite://{path.as_posix()}")


def value_workbook(path: Path, *, sheet: str = "Ticks") -> Path:
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = sheet
    table = ticks_table()
    worksheet.append(table.column_names)
    temporal = {name: table[name].cast("int64").to_pylist() for name in ("ts", "received_at")}
    columns = {name: table[name].to_pylist() for name in ("symbol", "venue", "price", "size")}
    for index in range(table.num_rows):
        worksheet.append([
            _format_ns(temporal["ts"][index]), columns["symbol"][index], columns["venue"][index],
            columns["price"][index], columns["size"][index], _format_ns(temporal["received_at"][index]),
        ])
    metadata = workbook.create_sheet("_otc_ts_schema")
    metadata.sheet_state = "hidden"
    metadata["A1"] = base64.b64encode(table.schema.serialize().to_pybytes()).decode("ascii")
    metadata["A2"] = sheet
    workbook.save(path)
    return path


class RecordingTemporalProcess:
    def __init__(self) -> None:
        table = ticks_table()
        sink = pa.BufferOutputStream()
        with pa.ipc.new_stream(sink, table.schema) as writer:
            writer.write_table(table)
        encoded = base64.b64encode(sink.getvalue().to_pybytes()).decode("ascii")
        self.description = {
            "schema_version": "mbs.temporal-describe/v1",
            "provider_identity": "mbs.recording/1.0.0",
            "capabilities": ["timeseries.describe/1.0", "timeseries.scan.range/1.0", "timeseries.lookup.latest/1.0", "timeseries.lookup.asof/1.0", "timeseries.aggregate.window/1.0", "timeseries.fill/1.0"],
            "commands": {
                "read": {"version": "1.0", "result_schema": "mbs.temporal-read-result/v1", "receipt_schema": "mbs.temporal-read-receipt/v1"},
            },
            "visibility": {"guarantee": "atomic", "evidence_schema": "mbs.atomic-pointer-evidence/v1"},
        }
        self.read_result = {"schema_version": "mbs.temporal-read-result/v1", "arrow_ipc_base64": encoded, "receipt": {"schema_version": "mbs.temporal-read-receipt/v1", "source_revision": "rev-fixture", "rows": table.num_rows}}
        self.calls = []

    def run(self, argv, *, credentials=None, stdin=None, timeout=None):
        self.calls.append((argv, credentials, stdin, timeout))
        if argv[2] == "describe":
            return self.description
        if argv[2] == "read":
            return self.read_result
        raise AssertionError(f"unexpected command: {argv}")


def _format_ns(value: int) -> str:
    seconds, nanos = divmod(value, 1_000_000_000)
    return datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{nanos:09d}Z"
