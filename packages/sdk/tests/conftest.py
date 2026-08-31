from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import open_table_connector.sdk as otc
import polars as pl
import pytest
from open_table_connector.contract import (
    ArrowReadResult,
    BaseConvention,
    CapabilityIdentity,
    ConnectorIdentity,
    NeutralReceipt,
    PluginDescriptor,
    TableURI,
    TableWriteResult,
)
from open_table_connector.contract import ProviderFactoryContext as LegacyProviderFactoryContext
from open_table_connector.contract import (
    TableInspection as LegacyInspection,
)
from open_table_connector.contract import (
    TableMode as LegacyTableMode,
)


def make_receipt(
    operation: str,
    *,
    uri: str = "fake://warehouse/orders",
    mode: otc.TableMode = otc.TableMode.BASE_MODE,
    row_count: int | None = None,
) -> otc.Receipt:
    return otc.Receipt(
        kind="physical",
        operation=operation,
        connector_id="fake",
        capability=f"{operation}/1.0",
        safe_target=TableURI(uri),
        mode=mode,
        details={} if row_count is None else {"row_count": row_count},
    )


@dataclass
class FakeTransaction:
    connector: FakeSdkConnector

    def insert(self, frame: pl.DataFrame) -> otc.OperationResult[int]:
        return self.connector._insert(frame)

    def update(self, frame: pl.DataFrame, *, keys: tuple[str, ...]) -> otc.OperationResult[int]:
        return self.connector._update(frame, keys=keys)

    def delete(
        self,
        *,
        where: otc.PortablePredicate,
        parameters: dict[str, Any] | None = None,
    ) -> otc.OperationResult[int]:
        return self.connector._delete(where=where, parameters=parameters)

    def commit(self) -> otc.OperationResult[None]:
        self.connector.calls.append(("commit", None))
        return otc.OperationResult(
            value=None,
            outcome=otc.Outcome.SUCCEEDED,
            commit=otc.CommitState.COMMITTED,
            verification=otc.VerificationState.PASSED,
            receipts=(make_receipt("table.commit"),),
        )

    def abort(self) -> otc.OperationResult[None]:
        self.connector.calls.append(("abort", None))
        return otc.OperationResult(
            value=None,
            outcome=otc.Outcome.SUCCEEDED,
            commit=otc.CommitState.NOT_COMMITTED,
            verification=otc.VerificationState.SKIPPED,
            receipts=(make_receipt("table.abort"),),
        )


@dataclass
class FakeSdkConnector:
    identity: ConnectorIdentity = field(
        default_factory=lambda: ConnectorIdentity("fake", "0.1.0", "1.0")
    )
    schemes: tuple[str, ...] = ("fake",)
    hosts: tuple[str, ...] = ()
    capabilities: tuple[CapabilityIdentity, ...] = (
        CapabilityIdentity("table.read", "1.0"),
        CapabilityIdentity("table.write", "1.0"),
        CapabilityIdentity("table.delete", "1.0"),
        CapabilityIdentity("table.drop", "1.0"),
        CapabilityIdentity("table.transaction", "1.0"),
    )
    modes: tuple[otc.TableMode, ...] = (otc.TableMode.BASE_MODE,)
    local: bool = False
    handles_paths: bool = False
    calls: list[tuple[str, Any]] = field(default_factory=list)
    closed: bool = False
    table_uri: str = "fake://warehouse/orders"
    frame: pl.DataFrame = field(
        default_factory=lambda: pl.DataFrame(
            {
                "order_id": [1, 2],
                "status": ["open", "done"],
            }
        )
    )
    existing_destinations: set[str] = field(default_factory=lambda: {"fake://warehouse/existing"})

    def open_table(self, address: object) -> otc.OperationResult[otc.TableBinding]:
        self.calls.append(("open_table", address))
        return otc.OperationResult(
            value=otc.TableBinding(
                uri=TableURI(self.table_uri),
                mode=otc.TableMode.BASE_MODE,
                schema=self.frame.schema,
                observed_revision="rev-1",
                connector_id=self.identity.connector_id,
            ),
            outcome=otc.Outcome.SUCCEEDED,
            commit=otc.CommitState.NOT_APPLICABLE,
            verification=otc.VerificationState.PASSED,
            receipts=(make_receipt("table.open"),),
        )

    def inspect_table(self, binding: otc.TableBinding) -> otc.OperationResult[otc.TableInspection]:
        self.calls.append(("inspect_table", binding.uri.value))
        return otc.OperationResult(
            value=otc.TableInspection(
                uri=binding.uri,
                mode=binding.mode,
                schema=binding.schema,
                row_count=self.frame.height,
                observed_revision=binding.observed_revision,
            ),
            outcome=otc.Outcome.SUCCEEDED,
            commit=otc.CommitState.NOT_APPLICABLE,
            verification=otc.VerificationState.PASSED,
            receipts=(make_receipt("table.inspect", row_count=self.frame.height),),
        )

    def capabilities_for(self, binding: otc.TableBinding) -> otc.OperationResult[otc.CapabilitySet]:
        self.calls.append(("capabilities_for", binding.uri.value))
        return otc.OperationResult(
            value=otc.CapabilitySet(
                capability_ids=tuple(capability.capability_id for capability in self.capabilities),
                modes=self.modes,
            ),
            outcome=otc.Outcome.SUCCEEDED,
            commit=otc.CommitState.NOT_APPLICABLE,
            verification=otc.VerificationState.PASSED,
            receipts=(make_receipt("table.capabilities"),),
        )

    def read_table(
        self,
        binding: otc.TableBinding,
        *,
        limit: int | None = None,
        continuation: str | None = None,
    ) -> otc.OperationResult[pl.DataFrame]:
        self.calls.append(("read_table", {"limit": limit, "continuation": continuation}))
        frame = self.frame if limit is None else self.frame.head(limit)
        next_token = None
        if limit is not None and limit < self.frame.height and continuation is None:
            next_token = "page-2"
        return otc.OperationResult(
            value=frame,
            outcome=otc.Outcome.SUCCEEDED,
            commit=otc.CommitState.NOT_APPLICABLE,
            verification=otc.VerificationState.PASSED,
            receipts=(make_receipt("table.read", row_count=frame.height),),
            continuation=next_token,
        )

    def _insert(self, frame: pl.DataFrame) -> otc.OperationResult[int]:
        self.calls.append(("insert", frame.height))
        self.frame = pl.concat([self.frame, frame], how="vertical_relaxed")
        return otc.OperationResult(
            value=frame.height,
            outcome=otc.Outcome.SUCCEEDED,
            commit=otc.CommitState.COMMITTED,
            verification=otc.VerificationState.PASSED,
            receipts=(make_receipt("table.insert", row_count=frame.height),),
        )

    def insert_rows(
        self, binding: otc.TableBinding, frame: pl.DataFrame
    ) -> otc.OperationResult[int]:
        self.calls.append(("insert_rows", binding.uri.value))
        return self._insert(frame)

    def _update(self, frame: pl.DataFrame, *, keys: tuple[str, ...]) -> otc.OperationResult[int]:
        self.calls.append(("update", keys))
        return otc.OperationResult(
            value=frame.height,
            outcome=otc.Outcome.SUCCEEDED,
            commit=otc.CommitState.COMMITTED,
            verification=otc.VerificationState.PASSED,
            receipts=(make_receipt("table.update", row_count=frame.height),),
        )

    def update_rows(
        self,
        binding: otc.TableBinding,
        frame: pl.DataFrame,
        *,
        keys: tuple[str, ...],
    ) -> otc.OperationResult[int]:
        self.calls.append(("update_rows", binding.uri.value))
        return self._update(frame, keys=keys)

    def _delete(
        self,
        *,
        where: otc.PortablePredicate,
        parameters: dict[str, Any] | None,
    ) -> otc.OperationResult[int]:
        self.calls.append(("delete", where.to_wire()))
        return otc.OperationResult(
            value=1,
            outcome=otc.Outcome.SUCCEEDED,
            commit=otc.CommitState.COMMITTED,
            verification=otc.VerificationState.PASSED,
            receipts=(make_receipt("table.delete", row_count=1),),
        )

    def delete_rows(
        self,
        binding: otc.TableBinding,
        *,
        where: otc.PortablePredicate,
        parameters: dict[str, Any] | None = None,
    ) -> otc.OperationResult[int]:
        self.calls.append(("delete_rows", binding.uri.value))
        return self._delete(where=where, parameters=parameters)

    def drop_table(self, binding: otc.TableBinding) -> otc.OperationResult[None]:
        self.calls.append(("drop_table", binding.uri.value))
        return otc.OperationResult(
            value=None,
            outcome=otc.Outcome.SUCCEEDED,
            commit=otc.CommitState.COMMITTED,
            verification=otc.VerificationState.PASSED,
            receipts=(make_receipt("table.drop"),),
        )

    def begin_transaction(self, binding: otc.TableBinding) -> FakeTransaction:
        self.calls.append(("begin_transaction", binding.uri.value))
        return FakeTransaction(self)

    def create_table(
        self,
        source: object,
        destination: otc.TableDestination,
    ) -> otc.OperationResult[otc.TableBinding]:
        destination_uri = (
            destination.uri.value if isinstance(destination, otc.DirectDestination) else ""
        )
        self.calls.append(("create_table", destination_uri or destination.to_wire()))
        if destination_uri in self.existing_destinations:
            return otc.OperationResult(
                value=None,
                outcome=otc.Outcome.REJECTED,
                commit=otc.CommitState.NOT_STARTED,
                verification=otc.VerificationState.SKIPPED,
                receipts=(make_receipt("table.create", uri=destination_uri or self.table_uri),),
                error=otc.ErrorInfo(
                    code=otc.ErrorCode.DESTINATION_EXISTS,
                    message="destination already exists",
                ),
            )
        uri = destination_uri or self.table_uri
        return otc.OperationResult(
            value=otc.TableBinding(
                uri=TableURI(uri),
                mode=otc.TableMode.BASE_MODE,
                schema=self.frame.schema if not isinstance(source, pl.DataFrame) else source.schema,
                observed_revision="rev-created",
                connector_id=self.identity.connector_id,
            ),
            outcome=otc.Outcome.SUCCEEDED,
            commit=otc.CommitState.COMMITTED,
            verification=otc.VerificationState.PASSED,
            receipts=(make_receipt("table.create", uri=uri),),
        )

    def close(self) -> None:
        self.closed = True
        self.calls.append(("close", None))


class FakeLegacyAdapter:
    identity = ConnectorIdentity("legacy", "0.1.0", "1.0")
    schemes = ("legacy",)
    hosts: tuple[str, ...] = ()
    capabilities = (CapabilityIdentity("table.write", "1.0"),)
    modes = (LegacyTableMode.BASE,)

    def read(self, *_args):
        receipt = NeutralReceipt(
            connector=self.identity,
            capability=CapabilityIdentity("table.read.arrow", "1.0"),
            operation_id="read-1",
            safe_uri=TableURI("legacy://warehouse/orders"),
            mode=LegacyTableMode.BASE,
            source_revision="rev-legacy",
            schema_fingerprint="schema-1",
            content_fingerprint="content-1",
            coordinate_convention=BaseConvention(key_fields=("order_id",)),
            row_count=1,
            batch_count=1,
        )
        return ArrowReadResult(table=pl.DataFrame({"order_id": [1]}).to_arrow(), receipt=receipt)

    def inspect(self, *_args):
        return LegacyInspection(
            safe_uri=TableURI("legacy://warehouse/orders"),
            mode=LegacyTableMode.BASE,
            columns=("order_id",),
            schema_fingerprint="schema-1",
            row_count=1,
            coordinate_convention=BaseConvention(key_fields=("order_id",)),
        )

    def write(self, _endpoint, table, _options):
        receipt = NeutralReceipt(
            connector=self.identity,
            capability=CapabilityIdentity("table.write", "1.0"),
            operation_id="write-1",
            safe_uri=TableURI("legacy://warehouse/created"),
            mode=LegacyTableMode.BASE,
            source_revision="rev-write",
            schema_fingerprint="schema-1",
            content_fingerprint="content-1",
            coordinate_convention=BaseConvention(key_fields=("order_id",)),
            row_count=table.num_rows,
            batch_count=1,
        )
        return TableWriteResult(receipt=receipt, affected_rows=table.num_rows)


def legacy_descriptor() -> PluginDescriptor:
    return PluginDescriptor(
        "legacy",
        FakeLegacyAdapter.identity,
        ("legacy",),
        lambda _context: FakeLegacyAdapter(),
        capabilities=FakeLegacyAdapter.capabilities,
        modes=FakeLegacyAdapter.modes,
    )


def sdk_descriptor(calls: list[str], connector: FakeSdkConnector) -> PluginDescriptor:
    def factory(_context: LegacyProviderFactoryContext) -> FakeSdkConnector:
        calls.append("factory")
        return connector

    return PluginDescriptor(
        "fake",
        connector.identity,
        connector.schemes,
        factory,
        capabilities=connector.capabilities,
        modes=(LegacyTableMode.BASE,),
    )


@pytest.fixture
def fake_connector() -> FakeSdkConnector:
    return FakeSdkConnector()
