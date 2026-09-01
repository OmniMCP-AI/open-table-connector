from __future__ import annotations

from dataclasses import dataclass

import open_table_connector.sdk as otc
import polars as pl
import pyarrow as pa
from open_table_connector.contract import TableURI
from open_table_connector.sdk.temporal import ManagedSnapshotState, TemporalStorage
from open_table_connector.timeseries import (
    ManagedCurrentResult,
    ManagedReadbackResult,
    TemporalTableDescriptor,
    temporal_descriptor_hash,
)

from packages.timeseries.tests.fixtures import descriptor as make_descriptor
from packages.timeseries.tests.fixtures import ticks_table


@dataclass
class CurrentExtension:
    schema: pa.Schema
    descriptor_hash: str
    has_current: bool = True

    def descriptor_hash_for(self, _binding, _descriptor):
        return self.descriptor_hash

    def current_snapshot(self, _binding, _descriptor):
        if not self.has_current:
            return None
        return ManagedCurrentResult(
            snapshot_id="sha256:" + "b" * 64,
            snapshot_reference="snapshot:current",
            committed_at="2026-08-29T00:00:00.000000000Z",
            descriptor_hash=self.descriptor_hash,
            schema=self.schema,
        )

    def executor_for(self, _binding, _descriptor):
        raise AssertionError("current recovery must not construct an executor")

    def append_rows(self, *_args, **_kwargs):
        raise AssertionError("current recovery must not append")

    def upsert_rows(self, *_args, **_kwargs):
        raise AssertionError("current recovery must not upsert")

    def stage_rows(self, *_args, **_kwargs):
        raise AssertionError("current recovery must not stage")

    def commit_stage(self, *_args, **_kwargs):
        raise AssertionError("current recovery must not commit")

    def readback_snapshot(self, *_args, **_kwargs):
        return ManagedReadbackResult(
            table=pa.table({"value": [1]}),
            artifact=None,
            receipt=None,  # type: ignore[arg-type]
        )

    def abort_stage(self, *_args, **_kwargs):
        raise AssertionError("current recovery must not abort")


@dataclass
class Connector:
    extension: CurrentExtension

    def temporal_extension_for(self, _binding, _descriptor):
        return self.extension


@dataclass
class Client:
    connector: Connector
    _client_id: str = "current-test-client"

    def _connector_for_binding(self, _binding):
        return self.connector


@dataclass
class Table:
    _client: Client
    _binding: otc.TableBinding

    @property
    def uri(self):
        return self._binding.uri

    @property
    def connector_id(self):
        return self._binding.connector_id

    @property
    def schema(self):
        return self._binding.schema


def _table_and_extension() -> tuple[Table, CurrentExtension, TemporalTableDescriptor]:
    arrow = ticks_table()
    descriptor = make_descriptor()
    binding_schema = pl.from_arrow(arrow).schema
    schema = (
        pl.DataFrame(schema=binding_schema)
        .select(list(descriptor.declared_fields))
        .to_arrow()
        .schema
    )
    extension = CurrentExtension(schema, temporal_descriptor_hash(descriptor, schema))
    connector = Connector(extension)
    client = Client(connector)
    binding = otc.TableBinding(
        TableURI("fake://warehouse/ticks"),
        otc.TableMode.BASE_MODE,
        pl.from_arrow(arrow).schema,
        "revision-1",
        "fake",
    )
    return Table(client, binding), extension, descriptor


def test_temporal_storage_current_returns_public_snapshot_state() -> None:
    table, _extension, descriptor = _table_and_extension()

    state = TemporalStorage(table, descriptor).current().require_value()

    assert isinstance(state, ManagedSnapshotState)
    assert state.snapshot.snapshot_reference == "snapshot:current"
    assert state.snapshot._owner_client_id == "current-test-client"
    expected_schema = (
        pl.DataFrame(schema=table.schema)
        .select(list(descriptor.declared_fields))
        .to_arrow()
        .schema
    )
    assert state.schema == expected_schema


def test_temporal_storage_current_returns_none_for_empty_target() -> None:
    table, extension, descriptor = _table_and_extension()
    extension.has_current = False

    assert TemporalStorage(table, descriptor).current().value is None
