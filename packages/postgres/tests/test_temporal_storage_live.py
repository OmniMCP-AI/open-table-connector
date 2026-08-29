from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
from uuid import uuid4

import pytest

from open_table_connector.contract import TableURI
from open_table_connector.postgres import PostgresManagedTemporalStore, lower_postgres
from open_table_connector.timeseries import (
    CalendarBucket,
    CalendarUnit,
    ManagedAbortRequest,
    ManagedCommitRequest,
    ManagedReadbackRequest,
    ManagedStageRequest,
    ResourceBounds,
    temporal_descriptor_hash,
)

from packages.local_files.tests.test_temporal_csv import operations
from packages.timeseries.tests.fixtures import descriptor, ticks_table

from .test_temporal_storage_recording import artifact


@pytest.mark.skipif(
    not os.environ.get("OTC_TEST_POSTGRES_DSN"),
    reason="OTC_TEST_POSTGRES_DSN is not configured",
)
def test_live_postgres_temporal_storage(tmp_path: Path) -> None:
    psycopg2 = pytest.importorskip("psycopg2")
    dsn = os.environ["OTC_TEST_POSTGRES_DSN"]
    schema = "otc_ts_live_" + uuid4().hex
    target = TableURI("postgres://localhost/otc-live-test")

    def connect(**kwargs):
        del kwargs
        return psycopg2.connect(dsn)

    setup = connect()
    try:
        with setup.cursor() as cursor:
            cursor.execute(f'CREATE SCHEMA "{schema}"')
            cursor.execute(
                f'CREATE TABLE "{schema}"."ticks" ('
                '"ts" TIMESTAMPTZ NOT NULL, "symbol" TEXT NOT NULL, "venue" TEXT NOT NULL, '
                '"price" DOUBLE PRECISION, "size" BIGINT NOT NULL, "received_at" TIMESTAMPTZ NOT NULL)'
            )
            rows = [
                (
                    str(row["ts"]),
                    row["symbol"],
                    row["venue"],
                    row["price"],
                    row["size"],
                    str(row["received_at"]),
                )
                for row in ticks_table().to_pylist()
            ]
            cursor.executemany(
                f'INSERT INTO "{schema}"."ticks" VALUES (%s, %s, %s, %s, %s, %s)',
                rows,
            )
        setup.commit()

        table, _, reference = artifact(tmp_path / "artifacts")
        observed_during_commit: list[str | None] = []

        def observe(event: str) -> None:
            assert event == "before_pointer_update"
            reader = connect()
            try:
                with reader.cursor() as cursor:
                    cursor.execute(
                        f'SELECT snapshot_reference FROM "{schema}"."commits" WHERE current'
                    )
                    row = cursor.fetchone()
                    observed_during_commit.append(None if row is None else row[0])
            finally:
                reader.close()

        store = PostgresManagedTemporalStore(
            target,
            tmp_path / "artifacts",
            descriptor(),
            connection_factory=connect,
            metadata_schema=schema,
            fault_injector=observe,
        )
        staged = store.stage(
            ManagedStageRequest(
                "live-stage",
                reference,
                temporal_descriptor_hash(descriptor(), table.schema),
                target,
                target,
                "live-idempotency",
            )
        )
        committed = store.commit(
            ManagedCommitRequest(
                "live-commit", target, staged.stage_id, "live-idempotency"
            )
        )
        readback = store.readback(
            ManagedReadbackRequest(
                "live-readback",
                target,
                committed.snapshot_id,
                committed.snapshot_reference,
                ResourceBounds(100, 10_000_000, 2_000),
            )
        )
        aborted = store.abort(ManagedAbortRequest("live-abort", target, staged.stage_id))

        assert observed_during_commit == [None]
        assert readback.table is not None and readback.table.equals(table)
        assert aborted.disposition.value == "already_committed"

        fixed = operations()[3]
        calendar = replace(
            fixed,
            operation=replace(
                fixed.operation,
                bucket=CalendarBucket(
                    1,
                    CalendarUnit.DAY,
                    "UTC",
                    1,
                    "2026-01-01T00:00:00.000000000Z",
                    0,
                ),
            ),
        )
        query_connection = connect()
        try:
            with query_connection.cursor() as cursor:
                for plan in (*operations()[:4], calendar):
                    prepared = lower_postgres(plan, descriptor(), f"{schema}.ticks")
                    assert prepared.residual_plan is None
                    cursor.execute(prepared.statement, prepared.parameters)
                    cursor.fetchall()
            query_connection.commit()
        finally:
            query_connection.close()
    finally:
        try:
            setup.rollback()
            with setup.cursor() as cursor:
                cursor.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            setup.commit()
        finally:
            setup.close()
