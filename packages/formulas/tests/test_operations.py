from __future__ import annotations

from dataclasses import dataclass

import pytest
from open_table_connector.formulas import (
    FIELD_READ,
    GRID_READ,
    BoundFieldFormulaTarget,
    BoundGridFormulaTarget,
    CalculationState,
    CompositeFormulaConnectorExtension,
    FieldFormulaBinding,
    FieldFormulaReadRequest,
    FieldRef,
    FormulaCapabilityDetails,
    FormulaCapabilitySet,
    FormulaCommitState,
    FormulaError,
    FormulaErrorCode,
    FormulaExtensionErrorInfo,
    FormulaExtensionResult,
    FormulaIdempotencyDisposition,
    FormulaIdempotencyLedger,
    FormulaOutcome,
    FormulaVerificationState,
    GridFormulaBinding,
    GridFormulaConnectorExtension,
    GridFormulaReadRequest,
    GridFormulaRecalculateRequest,
    GridFormulaSetRequest,
    GridFormulaValueReadRequest,
    IdempotencyStrength,
    MutationAtomicity,
    RevisionEnforcement,
    WorksheetRef,
)

HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
HASH_C = "sha256:" + "c" * 64

BOUND_GRID = BoundGridFormulaTarget(
    grid="gsheets://spreadsheet-id",
    worksheet=WorksheetRef(worksheet_id="ws-1"),
)
BOUND_FIELD = BoundFieldFormulaTarget(
    table={"uri": "maybe://orders"},
    field=FieldRef(field_id="fld-1"),
)
GRID_DETAILS = FormulaCapabilityDetails(
    target_kind="grid",
    dialects=("google-sheets-a1",),
    max_cells_per_operation=100,
    max_expression_bytes=1024,
    recalculation_scopes=("range",),
    calculation_states=(CalculationState.PROVIDER_CURRENT, CalculationState.UNKNOWN),
    mutation_atomicity=MutationAtomicity.ATOMIC,
    revision_enforcement=RevisionEnforcement.CHECKED,
    idempotency_strength=IdempotencyStrength.HOST_LEDGER,
)
FIELD_DETAILS = FormulaCapabilityDetails(
    target_kind="field",
    dialects=("maybe-base",),
    max_cells_per_operation=None,
    max_expression_bytes=1024,
    recalculation_scopes=("field",),
    calculation_states=(CalculationState.PROVIDER_CURRENT, CalculationState.UNKNOWN),
    mutation_atomicity=MutationAtomicity.ATOMIC,
    revision_enforcement=RevisionEnforcement.CHECKED,
    idempotency_strength=IdempotencyStrength.RECONCILED,
)


@pytest.mark.parametrize(
    ("outcome", "commit", "verification", "has_value", "has_error"),
    [
        (
            FormulaOutcome.REJECTED,
            FormulaCommitState.NOT_STARTED,
            FormulaVerificationState.SKIPPED,
            False,
            True,
        ),
        (
            FormulaOutcome.SUCCEEDED,
            FormulaCommitState.NOT_APPLICABLE,
            FormulaVerificationState.PASSED,
            True,
            False,
        ),
        (
            FormulaOutcome.SUCCEEDED,
            FormulaCommitState.COMMITTED,
            FormulaVerificationState.PASSED,
            True,
            False,
        ),
        (
            FormulaOutcome.SUCCEEDED,
            FormulaCommitState.NOT_APPLICABLE,
            FormulaVerificationState.UNAVAILABLE,
            True,
            False,
        ),
        (
            FormulaOutcome.FAILED,
            FormulaCommitState.NOT_COMMITTED,
            FormulaVerificationState.SKIPPED,
            False,
            True,
        ),
        (
            FormulaOutcome.FAILED,
            FormulaCommitState.COMMITTED,
            FormulaVerificationState.FAILED,
            False,
            True,
        ),
        (
            FormulaOutcome.PARTIAL,
            FormulaCommitState.PARTIAL,
            FormulaVerificationState.FAILED,
            True,
            True,
        ),
        (
            FormulaOutcome.UNKNOWN,
            FormulaCommitState.UNKNOWN,
            FormulaVerificationState.UNAVAILABLE,
            False,
            True,
        ),
    ],
)
def test_formula_extension_result_accepts_only_legal_state_rows(
    outcome: FormulaOutcome,
    commit: FormulaCommitState,
    verification: FormulaVerificationState,
    has_value: bool,
    has_error: bool,
) -> None:
    value = "bound" if has_value else None
    error = (
        FormulaExtensionErrorInfo(
            code=FormulaErrorCode.UNCERTAIN_MUTATION
            if outcome is FormulaOutcome.UNKNOWN
            else FormulaErrorCode.EXECUTION_FAILED,
            message="safe message",
            safe_details={"target_kind": "grid"},
        )
        if has_error
        else None
    )

    result = FormulaExtensionResult(
        value=value,
        outcome=outcome,
        commit=commit,
        verification=verification,
        receipts=(),
        error=error,
    )

    assert result.outcome is outcome


@pytest.mark.parametrize(
    ("outcome", "commit", "verification", "value", "error", "match"),
    [
        (
            FormulaOutcome.SUCCEEDED,
            FormulaCommitState.NOT_STARTED,
            FormulaVerificationState.PASSED,
            "value",
            None,
            "illegal",
        ),
        (
            FormulaOutcome.SUCCEEDED,
            FormulaCommitState.COMMITTED,
            FormulaVerificationState.FAILED,
            "value",
            None,
            "illegal",
        ),
        (
            FormulaOutcome.REJECTED,
            FormulaCommitState.NOT_STARTED,
            FormulaVerificationState.SKIPPED,
            "value",
            None,
            "must not carry a value",
        ),
        (
            FormulaOutcome.FAILED,
            FormulaCommitState.NOT_COMMITTED,
            FormulaVerificationState.SKIPPED,
            None,
            None,
            "requires an error",
        ),
        (
            FormulaOutcome.UNKNOWN,
            FormulaCommitState.UNKNOWN,
            FormulaVerificationState.UNAVAILABLE,
            "value",
            FormulaExtensionErrorInfo(FormulaErrorCode.UNCERTAIN_MUTATION, "safe", {}),
            "must not carry a value",
        ),
    ],
)
def test_formula_extension_result_rejects_illegal_state_rows(
    outcome: FormulaOutcome,
    commit: FormulaCommitState,
    verification: FormulaVerificationState,
    value: object | None,
    error: FormulaExtensionErrorInfo | None,
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        FormulaExtensionResult(
            value=value,
            outcome=outcome,
            commit=commit,
            verification=verification,
            receipts=(),
            error=error,
        )


def test_formula_extension_error_info_is_safe_and_json_like() -> None:
    info = FormulaExtensionErrorInfo(
        code=FormulaErrorCode.INVALID_FORMULA,
        message="syntax rejected",
        safe_details={
            "target_kind": "grid",
            "token": "secret",
            "nested": {"credential": "hidden", "dialect": "google-sheets-a1"},
        },
    )

    assert info.safe_details == {"target_kind": "grid"}

    with pytest.raises(ValueError, match="exception objects"):
        FormulaExtensionErrorInfo(
            code=FormulaErrorCode.EXECUTION_FAILED,
            message="bad",
            safe_details={"provider_error": RuntimeError("boom")},
        )


def test_formula_extension_error_info_redacts_formula_only_details_and_preserves_safe_facts() -> None:
    info = FormulaExtensionErrorInfo(
        code=FormulaErrorCode.INVALID_FORMULA,
        message="formula was rejected",
        safe_details={
            "target_kind": "grid",
            "dialect": "google-sheets-a1",
            "provider_status_code": 400,
            "revision_hash": HASH_A,
            "formula": "=SUM(A1:A2)",
            "value": 42,
            "provider_diagnostic": "bad formula =SUM(A1:A2)",
            "detail": "https://provider.example/errors/123",
            "nested": {"expression": "=A1", "affected_count": 2},
        },
    )

    assert info.safe_details == {
        "target_kind": "grid",
        "dialect": "google-sheets-a1",
        "provider_status_code": 400,
        "revision_hash": HASH_A,
    }


def test_formula_bindings_capture_bound_target_capabilities_and_revision() -> None:
    grid_binding = GridFormulaBinding(
        target=BOUND_GRID,
        capabilities=FormulaCapabilitySet((GRID_READ,), GRID_DETAILS),
        observed_revision=HASH_A,
    )
    field_binding = FieldFormulaBinding(
        target=BOUND_FIELD,
        capabilities=FormulaCapabilitySet((FIELD_READ,), FIELD_DETAILS),
        observed_revision=HASH_B,
    )

    assert grid_binding.observed_revision == HASH_A
    assert field_binding.capabilities.details.target_kind == "field"


def test_composite_formula_extension_returns_typed_unsupported_for_missing_delegate() -> None:
    extension = CompositeFormulaConnectorExtension(grid=_GridDelegate(), field=None)

    result = extension.read_field(
        FieldFormulaReadRequest(
            target=BOUND_FIELD,
        )
    )

    assert result.outcome is FormulaOutcome.REJECTED
    assert result.error is not None
    assert result.error.code is FormulaErrorCode.UNSUPPORTED_CAPABILITY
    assert result.error.safe_details["target_kind"] == "field"


def test_composite_formula_extension_forwards_grid_calls() -> None:
    delegate = _GridDelegate()
    extension = CompositeFormulaConnectorExtension(grid=delegate, field=None)
    request = GridFormulaReadRequest(target=BOUND_GRID, cell_range="A1:B2")

    result = extension.read_grid(request)

    assert result.value == "grid-read"
    assert delegate.last_read_request == request


def test_formula_idempotency_ledger_replays_conflicts_and_preserves_unknown_entries() -> None:
    ledger = FormulaIdempotencyLedger(limit=1)

    first = ledger.begin(
        connector_id="google-sheets",
        capability="formula.grid.set/1.0",
        target_hash=HASH_A,
        selector_hash=HASH_B,
        idempotency_key="key-1",
        payload_hash=HASH_C,
    )
    assert first.disposition is FormulaIdempotencyDisposition.STARTED

    ledger.succeed(
        connector_id="google-sheets",
        target_hash=HASH_A,
        selector_hash=HASH_B,
        idempotency_key="key-1",
        payload_hash=HASH_C,
        operation_hash=HASH_A,
    )

    replay = ledger.begin(
        connector_id="google-sheets",
        capability="formula.grid.set/1.0",
        target_hash=HASH_A,
        selector_hash=HASH_B,
        idempotency_key="key-1",
        payload_hash=HASH_C,
    )
    assert replay.disposition is FormulaIdempotencyDisposition.REPLAY

    conflict = ledger.begin(
        connector_id="google-sheets",
        capability="formula.grid.set/1.0",
        target_hash=HASH_A,
        selector_hash=HASH_B,
        idempotency_key="key-1",
        payload_hash="sha256:" + "d" * 64,
    )
    assert conflict.disposition is FormulaIdempotencyDisposition.CONFLICT

    unknown_started = ledger.begin(
        connector_id="google-sheets",
        capability="formula.grid.set/1.0",
        target_hash="sha256:" + "e" * 64,
        selector_hash="sha256:" + "f" * 64,
        idempotency_key="key-2",
        payload_hash="sha256:" + "1" * 64,
    )
    assert unknown_started.disposition is FormulaIdempotencyDisposition.STARTED
    ledger.mark_unknown(
        connector_id="google-sheets",
        target_hash="sha256:" + "e" * 64,
        selector_hash="sha256:" + "f" * 64,
        idempotency_key="key-2",
        payload_hash="sha256:" + "1" * 64,
    )

    unknown_again = ledger.begin(
        connector_id="google-sheets",
        capability="formula.grid.set/1.0",
        target_hash="sha256:" + "e" * 64,
        selector_hash="sha256:" + "f" * 64,
        idempotency_key="key-2",
        payload_hash="sha256:" + "1" * 64,
    )
    assert unknown_again.disposition is FormulaIdempotencyDisposition.UNKNOWN


def test_formula_idempotency_ledger_rejects_missing_terminal_entries() -> None:
    ledger = FormulaIdempotencyLedger(limit=2)

    with pytest.raises(KeyError):
        ledger.succeed(
            connector_id="google-sheets",
            target_hash=HASH_A,
            selector_hash=HASH_B,
            idempotency_key="missing",
            payload_hash=HASH_C,
            operation_hash=HASH_A,
        )


def test_formula_idempotency_ledger_rejects_new_entries_when_only_protected_entries_remain() -> None:
    ledger = FormulaIdempotencyLedger(limit=1)
    ledger.begin(
        connector_id="google-sheets",
        capability="formula.grid.set/1.0",
        target_hash=HASH_A,
        selector_hash=HASH_B,
        idempotency_key="in-flight",
        payload_hash=HASH_C,
    )

    with pytest.raises(FormulaError, match="resource limit"):
        ledger.begin(
            connector_id="google-sheets",
            capability="formula.grid.set/1.0",
            target_hash="sha256:" + "d" * 64,
            selector_hash="sha256:" + "e" * 64,
            idempotency_key="new",
            payload_hash="sha256:" + "f" * 64,
        )

    assert (
        ledger.begin(
            connector_id="google-sheets",
            capability="formula.grid.set/1.0",
            target_hash=HASH_A,
            selector_hash=HASH_B,
            idempotency_key="in-flight",
            payload_hash=HASH_C,
        ).disposition
        is FormulaIdempotencyDisposition.IN_FLIGHT
    )


@dataclass
class _GridDelegate(GridFormulaConnectorExtension):
    last_read_request: GridFormulaReadRequest | None = None

    def bind_grid(self, request: object) -> FormulaExtensionResult[GridFormulaBinding]:
        return FormulaExtensionResult(
            value=GridFormulaBinding(
                target=BOUND_GRID,
                capabilities=FormulaCapabilitySet((GRID_READ,), GRID_DETAILS),
                observed_revision=HASH_A,
            ),
            outcome=FormulaOutcome.SUCCEEDED,
            commit=FormulaCommitState.NOT_APPLICABLE,
            verification=FormulaVerificationState.PASSED,
            receipts=(),
        )

    def read_grid(self, request: GridFormulaReadRequest) -> FormulaExtensionResult[str]:
        self.last_read_request = request
        return FormulaExtensionResult(
            value="grid-read",
            outcome=FormulaOutcome.SUCCEEDED,
            commit=FormulaCommitState.NOT_APPLICABLE,
            verification=FormulaVerificationState.PASSED,
            receipts=(),
        )

    def set_grid(self, request: GridFormulaSetRequest) -> FormulaExtensionResult[str]:
        raise NotImplementedError

    def read_grid_values(self, request: GridFormulaValueReadRequest) -> FormulaExtensionResult[str]:
        raise NotImplementedError

    def recalculate_grid(self, request: GridFormulaRecalculateRequest) -> FormulaExtensionResult[str]:
        raise NotImplementedError
