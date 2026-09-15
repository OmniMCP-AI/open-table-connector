"""Recorded native Maybe Base create-only materialization coverage."""

from __future__ import annotations

import copy
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import open_table_connector.maybe_sheet.materialization as maybe_materialization
import open_table_connector.sdk as otc
import polars as pl
import pytest
from open_table_connector.contract import (
    OPTION_LIVE_MATERIALIZATION_EVIDENCE,
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

    def _read(self):
        result = copy.deepcopy(_FIXTURE["read"])
        if self.last_schema is not None:
            result["result"]["schema"] = self.last_schema
            result["result"]["rows"] = self.last_rows["rows"]
        return result

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
            if self.mode == "transport-error":
                from open_table_connector.contract import ConnectorError, ConnectorErrorCode

                raise ConnectorError(ConnectorErrorCode.EXECUTION_FAILED, "transport lost", {})
            key = argv[argv.index("--idempotency-key") + 1]
            schema = json.loads(Path(argv[argv.index("--schema-in") + 1]).read_text())
            rows = json.loads(Path(argv[argv.index("--frame-in") + 1]).read_text())
            self.last_schema, self.last_rows = schema, rows
            payload = {"schema": schema, "rows": rows, "uri": argv[argv.index("--uri") + 1]}
            previous = self.creates.get(key)
            if previous is not None:
                if previous[0] != json.dumps(payload, sort_keys=True):
                    return {"error": {"code": "idempotency_conflict", "pre_mutation": True}}
                return copy.deepcopy(_FIXTURE["create"])
            self.creates[key] = (json.dumps(payload, sort_keys=True), payload)
            if self.mode == "duplicate-name":
                return {"error": {"code": "duplicate_name", "pre_mutation": True}}
            if self.mode == "partial":
                return {"error": {"code": "partial_effect", "receipt_id": "vendor-partial"}}
            if self.mode == "provider-unsupported":
                return {"error": {"code": "unsupported_schema", "pre_mutation": True}}
            if self.mode == "provider-limit":
                return {"error": {"code": "resource_limit", "pre_mutation": True}}
            if self.mode == "invalid-response":
                return {"schema_version": "mbs.db-table-create-result/v1", "result": {}}
            result = copy.deepcopy(_FIXTURE["create"])
            result["result"]["affected_rows"] = len(rows["rows"])
            result["result"]["idempotency_key"] = key
            return result
        if argv[:3] == ("mbs", "db-table", "read"):
            assert argv[argv.index("--table-id") + 1] == "tbl-orders"
            if self.mode == "read-failure":
                from open_table_connector.contract import ConnectorError, ConnectorErrorCode

                raise ConnectorError(ConnectorErrorCode.EXECUTION_FAILED, "read failed", {})
            result = self._read()
            if self.mode == "mismatch":
                result["result"]["rows"] = [[2]]
            if self.mode == "revision-mismatch":
                result["result"]["source_revision"] = "rev-2"
            if self.mode == "wrong-id":
                result["result"]["table_id"] = "tbl-other"
            if self.mode == "malformed-read":
                result["result"]["schema"] = {"fields": [{"name": "id"}]}
            if self.mode == "malformed-rows":
                result["result"]["rows"] = [[]]
            return result
        if argv[:3] == ("mbs", "db-table", "reconcile"):
            return copy.deepcopy(_FIXTURE["reconcile"])
        raise AssertionError(argv)


def _client(process: RecordedNativeProcess) -> otc.Client:
    return otc.Client(
        registry=otc.ConnectorRegistry.from_descriptors(
            [maybe_sheet_cli_plugin()],
            otc.ClientConfig(
                providers={
                    PROVIDER_MAYBE_SHEET: ProviderConfig(
                        PROVIDER_MAYBE_SHEET,
                        options={OPTION_LIVE_MATERIALIZATION_EVIDENCE: True},
                    )
                }
            ),
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
    assert all("append" not in call and "insert" not in call for call in process.calls)
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


def test_recorded_probe_does_not_advertise_without_explicit_live_evidence() -> None:
    process = RecordedNativeProcess()
    adapter = MaybeSheetCliAdapter.from_context(
        ProviderFactoryContext(
            ProviderConfig(PROVIDER_MAYBE_SHEET),
            transports={PROVIDER_MAYBE_SHEET: process},
        )
    )
    connector = adapter.sdk_connector()
    assert otc.MATERIALIZE_CREATE_CAPABILITY not in connector.capabilities

    request = otc.MaterializationRequest(
        pl.DataFrame({"id": [1]}),
        otc.BaseModeDestination(_URI, "Orders"),
        otc.PORTABLE_TABLE_PROFILE_V1,
        "recorded-direct-create",
    )
    assert connector.create_table(request).require_value().address == otc.BaseModeTableAddress(
        _URI, "tbl-orders"
    )


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("duplicate-name", otc.ErrorCode.DESTINATION_EXISTS),
        ("partial", otc.ErrorCode.PARTIAL_EFFECT),
        ("mismatch", otc.ErrorCode.READBACK_MISMATCH),
        ("revision-mismatch", otc.ErrorCode.READBACK_MISMATCH),
        ("wrong-id", otc.ErrorCode.READBACK_MISMATCH),
        ("malformed-read", otc.ErrorCode.READBACK_MISMATCH),
        ("malformed-rows", otc.ErrorCode.READBACK_MISMATCH),
    ],
)
def test_native_create_preserves_provider_failure_state(mode, expected) -> None:
    with pytest.raises(otc.OTCError) as raised:
        _materialize(RecordedNativeProcess(mode=mode))
    assert raised.value.result.error.code is expected
    if mode == "partial":
        assert raised.value.result.outcome is otc.Outcome.PARTIAL
        assert raised.value.result.commit is otc.CommitState.PARTIAL
    if mode in {
        "mismatch",
        "revision-mismatch",
        "wrong-id",
        "malformed-read",
        "malformed-rows",
    }:
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


def test_public_reconciliation_uses_dedicated_provider_schema_without_name_lookup() -> None:
    process = RecordedNativeProcess(mode="timeout")
    client = _client(process)
    with pytest.raises(otc.OTCError) as raised:
        client.materialize(
            pl.DataFrame({"id": [1]}),
            to=otc.BaseModeDestination(_URI, "Orders"),
            profile=otc.PORTABLE_TABLE_PROFILE_V1,
            idempotency_key="maybe-create-1",
        )
    result = client.reconcile_materialization(
        raised.value.result.error.reconciliation,
        destination=otc.BaseModeDestination(_URI, "Orders"),
    )
    assert result.require_value().address == otc.BaseModeTableAddress(_URI, "tbl-orders")
    assert process.calls[-2] == (
        "mbs", "db-table", "reconcile", "--uri", _URI, "--idempotency-key", "maybe-create-1"
    )


def test_reconciliation_rejects_contradictory_provider_evidence() -> None:
    process = RecordedNativeProcess(mode="timeout")
    client = _client(process)
    with pytest.raises(otc.OTCError) as raised:
        _materialize(process)
    reference = raised.value.result.error.reconciliation
    original = process.run

    def conflicting(argv, **kwargs):
        payload = original(argv, **kwargs)
        if tuple(argv[:3]) == ("mbs", "db-table", "reconcile"):
            payload["result"]["provider_revision"] = "rev-other"
            payload["result"]["affected_rows"] = 999
        return payload

    process.run = conflicting
    with pytest.raises(otc.OTCError) as mismatch:
        client.reconcile_materialization(reference, destination=otc.BaseModeDestination(_URI, "Orders"))
    assert mismatch.value.result.error.code is otc.ErrorCode.READBACK_MISMATCH
    assert mismatch.value.result.commit is otc.CommitState.COMMITTED
    assert [receipt.operation for receipt in mismatch.value.result.receipts] == [
        "table.materialize.reconcile",
        "table.read",
    ]


def test_reconciliation_rejects_a_different_stable_id_payload() -> None:
    process = RecordedNativeProcess(mode="timeout")
    client = _client(process)
    with pytest.raises(otc.OTCError) as raised:
        _materialize(process)
    reference = raised.value.result.error.reconciliation
    process.mode = "mismatch"

    with pytest.raises(otc.OTCError) as mismatch:
        client.reconcile_materialization(
            reference, destination=otc.BaseModeDestination(_URI, "Orders")
        )

    result = mismatch.value.result
    assert result.error.code is otc.ErrorCode.READBACK_MISMATCH
    assert (result.outcome, result.commit, result.verification) == (
        otc.Outcome.FAILED,
        otc.CommitState.COMMITTED,
        otc.VerificationState.FAILED,
    )
    assert [receipt.operation for receipt in result.receipts] == [
        "table.materialize.reconcile",
        "table.read",
    ]


def test_reconciliation_read_failure_preserves_known_commit_and_receipt() -> None:
    process = RecordedNativeProcess(mode="timeout")
    client = _client(process)
    with pytest.raises(otc.OTCError) as raised:
        _materialize(process)
    reference = raised.value.result.error.reconciliation
    process.mode = "read-failure"

    with pytest.raises(otc.OTCError) as read_failure:
        client.reconcile_materialization(
            reference, destination=otc.BaseModeDestination(_URI, "Orders")
        )

    result = read_failure.value.result
    assert (result.outcome, result.commit, result.verification) == (
        otc.Outcome.FAILED,
        otc.CommitState.COMMITTED,
        otc.VerificationState.FAILED,
    )
    assert result.error.code is otc.ErrorCode.READBACK_MISMATCH
    assert result.receipts[0].operation == "table.materialize.reconcile"


def test_reconciliation_rejects_invalid_reference_before_provider_dispatch() -> None:
    process = RecordedNativeProcess()
    client = _client(process)
    reference = otc.ReconciliationReference(
        "not-a-maybe-operation", "wrong-connector", "maybe-create-1"
    )

    with pytest.raises(otc.OTCError) as raised:
        client.reconcile_materialization(
            reference, destination=otc.BaseModeDestination(_URI, "Orders")
        )

    result = raised.value.result
    assert (result.outcome, result.commit, result.verification) == (
        otc.Outcome.REJECTED,
        otc.CommitState.NOT_STARTED,
        otc.VerificationState.SKIPPED,
    )
    assert not any(call[:3] == ("mbs", "db-table", "reconcile") for call in process.calls)


@pytest.mark.parametrize("mode", ["transport-error", "invalid-response"])
def test_post_dispatch_failure_is_uncertain_and_reconcilable(mode) -> None:
    with pytest.raises(otc.OTCError) as raised:
        _materialize(RecordedNativeProcess(mode=mode))
    result = raised.value.result
    assert (result.outcome, result.commit, result.verification) == (
        otc.Outcome.UNKNOWN,
        otc.CommitState.UNKNOWN,
        otc.VerificationState.UNAVAILABLE,
    )
    assert result.error.code is otc.ErrorCode.UNCERTAIN_MUTATION
    assert result.error.reconciliation.idempotency_key == "maybe-create-1"


@pytest.mark.parametrize(
    ("mode", "code"),
    [
        ("provider-unsupported", otc.ErrorCode.INVALID_SCHEMA),
        ("provider-limit", otc.ErrorCode.RESOURCE_LIMIT),
    ],
)
def test_provider_pre_effect_rejections_do_not_read_or_mutate(mode, code) -> None:
    process = RecordedNativeProcess(mode=mode)
    with pytest.raises(otc.OTCError) as raised:
        _materialize(process)
    assert raised.value.result.error.code is code
    assert raised.value.result.commit is otc.CommitState.NOT_STARTED
    assert not any(call[:3] == ("mbs", "db-table", "read") for call in process.calls)


def test_native_create_round_trips_every_portable_provider_type() -> None:
    source = pl.DataFrame(
        {
            "text": ["東京", "", None],
            "flag": [True, False, None],
            "integer": [-(2**63), 2**63 - 1, None],
            "float": [1.25, -0.0, None],
            "decimal": [Decimal("123.40"), Decimal("-0.01"), None],
            "day": [date(2026, 9, 14), date(1999, 12, 31), None],
            "when": [
                datetime(2026, 9, 14, 1, 2, 3, 456789, UTC),
                datetime(1999, 12, 31, 23, 59, 59, 0, UTC),
                None,
            ],
        },
        schema={
            "text": pl.String,
            "flag": pl.Boolean,
            "integer": pl.Int64,
            "float": pl.Float64,
            "decimal": pl.Decimal(precision=10, scale=2),
            "day": pl.Date,
            "when": pl.Datetime("us", "UTC"),
        },
    )
    process = RecordedNativeProcess()
    materialized = _materialize(process, source)
    assert materialized.require_value().read().require_value().equals(source)
    assert _client(process).open(materialized.require_value().address).require_value().read().require_value().equals(source)


@pytest.mark.parametrize(("limit", "value"), [("_MAX_ROWS", 0), ("_MAX_BYTES", 1)])
def test_native_create_rejects_local_resource_limits_before_process_create(
    monkeypatch, limit, value
) -> None:
    process = RecordedNativeProcess()
    monkeypatch.setattr(maybe_materialization, limit, value)

    with pytest.raises(otc.OTCError) as raised:
        _materialize(process)

    assert raised.value.result.error.code is otc.ErrorCode.RESOURCE_LIMIT
    assert raised.value.result.commit is otc.CommitState.NOT_STARTED
    assert not any(call[:3] == ("mbs", "db-table", "create") for call in process.calls)


def test_native_create_round_trips_zero_rows_and_all_null_columns() -> None:
    zero = pl.DataFrame(schema={"id": pl.Int64, "empty": pl.String})
    all_null = pl.DataFrame(
        {"empty": [None, None]}, schema={"empty": pl.Decimal(precision=8, scale=3)}
    )
    assert _materialize(RecordedNativeProcess(), zero).require_value().read().require_value().equals(zero)
    assert _materialize(RecordedNativeProcess(), all_null).require_value().read().require_value().equals(all_null)


@pytest.mark.parametrize(
    "uri",
    [
        "https://www.maybe.ai/docs/spreadsheets/d/doc-123?table_id=table-1",
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
