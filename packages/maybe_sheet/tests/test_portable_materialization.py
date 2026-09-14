"""Recorded native Maybe Base create-only materialization coverage."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import open_table_connector.sdk as otc
import polars as pl
import pytest
from open_table_connector.contract import (
    PROVIDER_MAYBE_SHEET,
    ProviderConfig,
    ProviderFactoryContext,
)
from open_table_connector.maybe_sheet import MaybeSheetCliAdapter, maybe_sheet_cli_plugin

_FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "portable-materialization-v1.json").read_text(
        encoding="utf-8"
    )
)
_URI = "https://www.maybe.ai/docs/spreadsheets/d/doc-123"


class RecordedNativeProcess:
    """Deterministic process fixture, including provider-side idempotency state."""

    def __init__(self, *, supported: bool = True, mode: str = "success") -> None:
        self.supported = supported
        self.mode = mode
        self.calls: list[tuple[str, ...]] = []
        self.creates: dict[str, tuple[str, dict]] = {}
        self.last_schema: dict | None = None
        self.last_rows: dict | None = None

    def run(self, argv, *, credentials=None, stdin=None, timeout=None):
        del credentials, stdin, timeout
        argv = tuple(argv)
        self.calls.append(argv)
        if argv[:3] == ("mbs", "db-table", "describe"):
            if not self.supported:
                return {"schema_version": "mbs.db-table-describe/v1", "provider_identity": "maybe-sheet", "capabilities": [], "commands": {}}
            return copy.deepcopy(_FIXTURE["describe"])
        if argv[:3] == ("mbs", "db-table", "create"):
            if self.mode == "timeout":
                from open_table_connector.contract import ConnectorError, ConnectorErrorCode

                raise ConnectorError(ConnectorErrorCode.TIMEOUT, "lost response", {})
            key = argv[argv.index("--idempotency-key") + 1]
            schema = json.loads(Path(argv[argv.index("--schema-in") + 1]).read_text())
            rows = json.loads(Path(argv[argv.index("--frame-in") + 1]).read_text())
            self.last_schema, self.last_rows = schema, rows
            payload = {"schema": schema, "rows": rows, "uri": argv[argv.index("--uri") + 1]}
            previous = self.creates.get(key)
            if previous is not None:
                if previous[0] != json.dumps(payload, sort_keys=True):
                    return {"error": {"code": "idempotency_conflict"}}
                return copy.deepcopy(_FIXTURE["create"])
            self.creates[key] = (json.dumps(payload, sort_keys=True), payload)
            if self.mode == "duplicate-name":
                return {"error": {"code": "duplicate_name"}}
            if self.mode == "partial":
                return {"error": {"code": "partial_effect", "receipt_id": "vendor-partial"}}
            return copy.deepcopy(_FIXTURE["create"])
        if argv[:3] == ("mbs", "db-table", "read"):
            assert argv[argv.index("--table-id") + 1] == "tbl-orders"
            result = copy.deepcopy(_FIXTURE["read"])
            if self.mode == "mismatch":
                result["result"]["rows"] = [[2]]
            if self.mode == "revision-mismatch":
                result["result"]["source_revision"] = "rev-2"
            return result
        if argv[:3] == ("mbs", "db-table", "reconcile"):
            return copy.deepcopy(_FIXTURE["create"])
        raise AssertionError(argv)


def _client(process: RecordedNativeProcess) -> otc.Client:
    return otc.Client(
        registry=otc.ConnectorRegistry.from_descriptors(
            [maybe_sheet_cli_plugin()],
            otc.ClientConfig(providers={PROVIDER_MAYBE_SHEET: ProviderConfig(PROVIDER_MAYBE_SHEET)}),
            transports={PROVIDER_MAYBE_SHEET: process},
        )
    )


def _materialize(process: RecordedNativeProcess, frame=None, *, key="maybe-create-1", uri=_URI):
    return _client(process).materialize(
        pl.DataFrame({"id": [1]}) if frame is None else frame,
        to=otc.BaseModeDestination(uri, "Orders"),
        profile=otc.PORTABLE_TABLE_PROFILE_V1,
        idempotency_key=key,
    )


def test_native_create_uses_canonical_uri_typed_files_and_stable_id_readback() -> None:
    process = RecordedNativeProcess()
    result = _materialize(process)

    address = result.require_value().address
    assert isinstance(address, otc.BaseModeTableAddress)
    assert address.container.value == _URI
    assert address.table_id == "tbl-orders"
    assert result.require_value().read().require_value().to_dicts() == [{"id": 1}]
    assert process.calls[1][:4] == ("mbs", "db-table", "create", "--uri")
    assert process.calls[1][4] == _URI
    assert "--schema-in" in process.calls[1] and "--frame-in" in process.calls[1]
    assert process.calls[1][-2:] == ("--idempotency-key", "maybe-create-1")
    assert process.last_schema == {"fields": [{"name": "id", "type": "Int64"}]}
    assert process.last_rows == {"rows": [[1]]}
    assert [receipt.operation for receipt in result.receipts] == [
        "table.materialize.create",
        "table.read",
    ]
    assert all(receipt.safe_target.value == _URI for receipt in result.receipts)
    assert _client(process).open(address).require_value().read().require_value().to_dicts() == [
        {"id": 1}
    ]


def test_native_capability_is_not_advertised_without_all_provider_proofs() -> None:
    process = RecordedNativeProcess(supported=False)
    adapter = MaybeSheetCliAdapter.from_context(
        ProviderFactoryContext(ProviderConfig(PROVIDER_MAYBE_SHEET), transports={PROVIDER_MAYBE_SHEET: process})
    )
    connector = adapter.sdk_connector()

    assert otc.MATERIALIZE_CREATE_CAPABILITY not in connector.capabilities
    with pytest.raises(otc.OTCError) as raised:
        _materialize(process)
    assert raised.value.result.error.code is otc.ErrorCode.UNSUPPORTED_CAPABILITY
    assert not any(call[:3] == ("mbs", "db-table", "create") for call in process.calls)


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("duplicate-name", otc.ErrorCode.DESTINATION_EXISTS),
        ("partial", otc.ErrorCode.PARTIAL_EFFECT),
        ("mismatch", otc.ErrorCode.READBACK_MISMATCH),
        ("revision-mismatch", otc.ErrorCode.READBACK_MISMATCH),
    ],
)
def test_native_create_preserves_provider_failure_state(mode, expected) -> None:
    with pytest.raises(otc.OTCError) as raised:
        _materialize(RecordedNativeProcess(mode=mode))
    assert raised.value.result.error.code is expected
    if mode == "partial":
        assert raised.value.result.outcome is otc.Outcome.PARTIAL
        assert raised.value.result.commit is otc.CommitState.PARTIAL
    if mode in {"mismatch", "revision-mismatch"}:
        assert raised.value.result.commit is otc.CommitState.COMMITTED
        assert [receipt.operation for receipt in raised.value.result.receipts] == [
            "table.materialize.create",
            "table.read",
        ]


def test_native_create_replays_key_and_rejects_changed_payload() -> None:
    process = RecordedNativeProcess()
    _materialize(process)
    _materialize(process)
    with pytest.raises(otc.OTCError) as raised:
        _materialize(process, pl.DataFrame({"id": [2]}))
    assert raised.value.result.error.code is otc.ErrorCode.IDEMPOTENCY_CONFLICT


def test_timeout_requires_reconciliation_with_the_same_key() -> None:
    process = RecordedNativeProcess(mode="timeout")
    with pytest.raises(otc.OTCError) as raised:
        _materialize(process)
    result = raised.value.result
    assert result.outcome is otc.Outcome.UNKNOWN
    assert result.commit is otc.CommitState.UNKNOWN
    assert result.verification is otc.VerificationState.UNAVAILABLE
    assert result.error.code is otc.ErrorCode.UNCERTAIN_MUTATION
    assert result.error.reconciliation is not None
    assert result.error.reconciliation.idempotency_key == "maybe-create-1"


def test_reconciliation_uses_provider_key_without_name_lookup() -> None:
    process = RecordedNativeProcess()
    connector = _client(process)._registry.connector_for(_URI)
    result = connector.reconcile_materialization(otc.BaseModeDestination(_URI, "Orders"), "maybe-create-1")
    assert result.require_value().address == otc.BaseModeTableAddress(_URI, "tbl-orders")
    assert process.calls[-2] == (
        "mbs", "db-table", "reconcile", "--uri", _URI, "--idempotency-key", "maybe-create-1"
    )


@pytest.mark.parametrize(
    "uri",
    [
        "maybe://doc-123",
        "https://www.maybe.ai/docs/spreadsheets/d/doc-123?share=1",
        "https://www.maybe.ai/docs/spreadsheets/d/doc-123#table",
        "https://www.maybe.ai/sheet/doc-123",
    ],
)
def test_native_create_rejects_noncanonical_destination_before_mutation(uri) -> None:
    process = RecordedNativeProcess()
    with pytest.raises(otc.OTCError) as raised:
        _materialize(process, uri=uri)
    assert raised.value.result.error.code is otc.ErrorCode.INVALID_TARGET
    assert not any(call[:3] == ("mbs", "db-table", "create") for call in process.calls)
