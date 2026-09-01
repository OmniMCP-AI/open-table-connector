from __future__ import annotations

import hashlib
import logging
import warnings
from collections.abc import Iterable
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import open_table_connector.formulas as otf
from open_table_connector.contract import CapabilityIdentity, TableURI

LOGGER = logging.getLogger(__name__)

HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
HASH_C = "sha256:" + "c" * 64
HASH_D = "sha256:" + "d" * 64
HASH_E = "sha256:" + "e" * 64
HASH_F = "sha256:" + "f" * 64

URL_MARKER = "https://secret.example/export.csv"
TOKEN_MARKER = "tok_live_formula_probe_123456789"
CREDENTIAL_MARKER = '"password=correct horse battery staple"'
WORKBOOK_PATH_MARKER = "/Users/demo/Finance/Workbook.xlsx"
SECURITY_MARKERS = (
    URL_MARKER,
    TOKEN_MARKER,
    CREDENTIAL_MARKER,
    WORKBOOK_PATH_MARKER,
)
SECURITY_EXPRESSION = otf.FormulaExpression(
    f'=HYPERLINK("{URL_MARKER}", "{TOKEN_MARKER}")&{CREDENTIAL_MARKER!r}&"{WORKBOOK_PATH_MARKER}"',
    otf.GOOGLE_SHEETS_A1,
)


def stable_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _copy_fill_formulas(source_expression: otf.FormulaExpression) -> tuple[otf.FormulaCell, ...]:
    return (
        otf.FormulaCell("A1", source_expression),
        otf.FormulaCell("B1", otf.FormulaExpression("=B1", source_expression.dialect)),
        otf.FormulaCell("A2", otf.FormulaExpression("=A2", source_expression.dialect)),
        otf.FormulaCell("B2", otf.FormulaExpression("=B2", source_expression.dialect)),
    )


def _broadcast_formulas(source_expression: otf.FormulaExpression) -> tuple[otf.FormulaCell, ...]:
    return tuple(
        otf.FormulaCell(address, source_expression)
        for address in ("A1", "B1", "A2", "B2")
    )


def make_grid_target() -> otf.GridFormulaTarget:
    return otf.GridFormulaTarget(
        "gridfake://warehouse/model",
        otf.WorksheetRef(name="Model"),
    )


@dataclass(frozen=True, slots=True)
class FakeTable:
    uri: TableURI


def make_field_target() -> otf.FieldFormulaTarget[FakeTable]:
    return otf.FieldFormulaTarget(
        FakeTable(TableURI("fieldfake://warehouse/orders")),
        otf.FieldRef(name="gross_margin"),
    )


@dataclass(frozen=True, slots=True)
class GridCaseData:
    formula_range: str
    literal_range: str
    set_expression: otf.FormulaExpression
    conflicting_expression: otf.FormulaExpression
    expected_after_set: otf.GridFormulaObservation
    expected_literal_read: otf.GridFormulaObservation
    expected_values: otf.GridFormulaValueObservation
    recalculation_scope: otf.GridRecalculationScope
    expected_recalculation: otf.RecalculationObservation


@dataclass(frozen=True, slots=True)
class FieldCaseData:
    set_expression: otf.FormulaExpression
    conflicting_expression: otf.FormulaExpression
    expected_after_set: otf.FieldFormulaObservation
    expected_values: otf.FieldFormulaValueObservation
    recalculation_scope: otf.FieldRecalculationScope
    expected_recalculation: otf.RecalculationObservation


@dataclass(frozen=True, slots=True)
class SecurityProbe:
    mutation: otf.FormulaMutation
    receipts: tuple[object, ...]
    warnings: tuple[str, ...]
    logs: tuple[str, ...]
    reprs: tuple[str, ...]
    operation_ids: tuple[str, ...]
    ledger_snapshots: tuple[object, ...]


def grid_case_data(
    *, set_expression: otf.FormulaExpression | None = None
) -> GridCaseData:
    set_expression = set_expression or otf.FormulaExpression("=A1", otf.GOOGLE_SHEETS_A1)
    expected_after_set = otf.GridFormulaObservation(
        worksheet_id="ws-model",
        requested_range="A1:B2",
        formulas=_copy_fill_formulas(set_expression),
        observed_revision=HASH_B,
    )
    expected_values = otf.GridFormulaValueObservation(
        worksheet_id="ws-model",
        requested_range="A1:B2",
        values=(
            otf.FormulaValueCell("A1", otf.FormulaValue.from_python(1)),
            otf.FormulaValueCell("B1", otf.FormulaValue.from_python(2)),
            otf.FormulaValueCell("A2", otf.FormulaValue.from_python(3)),
            otf.FormulaValueCell("B2", otf.FormulaValue.from_python(4)),
        ),
        calculation_state=otf.CalculationState.PROVIDER_CURRENT,
        calculation_trigger=otf.CalculationTrigger.PROVIDER_READ,
        dependency_scope="provider_dynamic",
        observed_revision=HASH_C,
    )
    expected_recalculation = otf.RecalculationObservation(
        target_kind="grid",
        requested_scope=otf.GridRecalculationScope.RANGE.value,
        effective_scope=otf.GridRecalculationScope.RANGE.value,
        revision_before=HASH_B,
        revision_after=HASH_D,
        provider_status="completed",
        calculation_state=otf.CalculationState.PROVIDER_CURRENT,
        verification="passed",
        value_observation=otf.GridFormulaValueObservation(
            worksheet_id="ws-model",
            requested_range="A1:B2",
            values=expected_values.values,
            calculation_state=otf.CalculationState.PROVIDER_CURRENT,
            calculation_trigger=otf.CalculationTrigger.EXPLICIT_RECALCULATION,
            dependency_scope="provider_dynamic",
            observed_revision=HASH_D,
        ),
    )
    return GridCaseData(
        formula_range="A1:B2",
        literal_range="C3",
        set_expression=set_expression,
        conflicting_expression=otf.FormulaExpression("=Z9", otf.GOOGLE_SHEETS_A1),
        expected_after_set=expected_after_set,
        expected_literal_read=otf.GridFormulaObservation(
            worksheet_id="ws-model",
            requested_range="C3",
            formulas=(),
            observed_revision=HASH_A,
        ),
        expected_values=expected_values,
        recalculation_scope=otf.GridRecalculationScope.RANGE,
        expected_recalculation=expected_recalculation,
    )


def field_case_data() -> FieldCaseData:
    expected_after_set = otf.FieldFormulaObservation(
        table_uri=TableURI("fieldfake://warehouse/orders"),
        field_id="fld-gross_margin",
        field_name="gross_margin",
        expression=otf.FormulaExpression("revenue - cost", otf.MAYBE_BASE),
        result_type="number",
        observed_revision=HASH_B,
    )
    expected_values = otf.FieldFormulaValueObservation(
        table_uri=TableURI("fieldfake://warehouse/orders"),
        field_id="fld-gross_margin",
        field_name="gross_margin",
        values=(
            otf.FormulaRecordValue("rec-1", otf.FormulaValue.from_python(10)),
            otf.FormulaRecordValue("rec-2", otf.FormulaValue.from_python(12)),
        ),
        calculation_state=otf.CalculationState.PROVIDER_CURRENT,
        calculation_trigger=otf.CalculationTrigger.PROVIDER_READ,
        dependency_scope="provider_dynamic",
        observed_revision=HASH_C,
    )
    expected_recalculation = otf.RecalculationObservation(
        target_kind="field",
        requested_scope=otf.FieldRecalculationScope.FIELD.value,
        effective_scope=otf.FieldRecalculationScope.FIELD.value,
        revision_before=HASH_B,
        revision_after=HASH_D,
        provider_status="completed",
        calculation_state=otf.CalculationState.PROVIDER_CURRENT,
        verification="passed",
        value_observation=otf.FieldFormulaValueObservation(
            table_uri=TableURI("fieldfake://warehouse/orders"),
            field_id="fld-gross_margin",
            field_name="gross_margin",
            values=expected_values.values,
            calculation_state=otf.CalculationState.PROVIDER_CURRENT,
            calculation_trigger=otf.CalculationTrigger.EXPLICIT_RECALCULATION,
            dependency_scope="provider_dynamic",
            observed_revision=HASH_D,
        ),
    )
    return FieldCaseData(
        set_expression=otf.FormulaExpression("revenue - cost", otf.MAYBE_BASE),
        conflicting_expression=otf.FormulaExpression("revenue - tax", otf.MAYBE_BASE),
        expected_after_set=expected_after_set,
        expected_values=expected_values,
        recalculation_scope=otf.FieldRecalculationScope.FIELD,
        expected_recalculation=expected_recalculation,
    )


@dataclass
class FakeFormulaStore:
    grid_revision: str = HASH_A
    field_revision: str = HASH_A
    grid_formulas: tuple[otf.FormulaCell, ...] = field(default_factory=tuple)
    literal_text: str = "=literal-string"
    field_expression: otf.FormulaExpression = field(
        default_factory=lambda: otf.FormulaExpression("gross * 0.10", otf.MAYBE_BASE)
    )
    idempotency: otf.FormulaIdempotencyLedger = field(
        default_factory=lambda: otf.FormulaIdempotencyLedger(limit=16)
    )


@dataclass(frozen=True, slots=True)
class BrokenBehavior:
    broadcast_copy_fill: bool = False
    infer_formula_from_leading_equals: bool = False
    value_without_dependency_scope: bool = False
    field_conversion: bool = False
    receipt_leak: bool = False
    accept_stale_revision: bool = False
    allow_idempotency_reuse: bool = False
    unsupported_capabilities: tuple[str, ...] = ()
    security_leak_channel: str | None = None
    reject_grid_read: bool = False
    reject_field_read: bool = False


DEFAULT_BROKEN = BrokenBehavior()


def _receipt_target(
    target: str,
    *,
    expression: otf.FormulaExpression | None = None,
    broken: BrokenBehavior,
) -> str:
    if broken.receipt_leak and expression is not None:
        return f"{target}::{expression.text}"
    return target


def _unsupported_result(target_kind: str, capability: str) -> otf.FormulaExtensionResult[None]:
    return otf.FormulaExtensionResult(
        value=None,
        outcome=otf.FormulaOutcome.REJECTED,
        commit=otf.FormulaCommitState.NOT_STARTED,
        verification=otf.FormulaVerificationState.SKIPPED,
        receipts=(),
        error=otf.FormulaExtensionErrorInfo(
            code=otf.FormulaErrorCode.UNSUPPORTED_CAPABILITY,
            message="formula capability is not available for this target kind",
            safe_details={"target_kind": target_kind, "capability": capability},
        ),
    )


def _maybe_emit_security_leak(
    broken: BrokenBehavior,
    channel: str,
    marker: str,
    *,
    operation_ids: list[str],
    ledger_snapshots: list[object],
    reprs: list[str],
) -> None:
    if broken.security_leak_channel != channel:
        return
    if channel == "warning":
        warnings.warn(marker, stacklevel=2)
        return
    if channel == "log":
        LOGGER.warning(marker)
        return
    if channel == "operation_id":
        operation_ids.append(marker)
        return
    if channel == "ledger":
        ledger_snapshots.append({"payload_hash": marker})
        return
    if channel == "repr":
        reprs.append(marker)


def _grid_binding(
    capabilities: tuple[CapabilityIdentity, ...],
    details: otf.FormulaCapabilityDetails,
) -> otf.GridFormulaBinding:
    return otf.GridFormulaBinding(
        target=otf.BoundGridFormulaTarget(
            "gridfake://warehouse/model",
            otf.WorksheetRef(worksheet_id="ws-model"),
        ),
        capabilities=otf.FormulaCapabilitySet(capabilities, details),
        observed_revision=HASH_A,
    )


def _field_binding(
    capabilities: tuple[CapabilityIdentity, ...],
    details: otf.FormulaCapabilityDetails,
) -> otf.FieldFormulaBinding[FakeTable]:
    return otf.FieldFormulaBinding(
        target=otf.BoundFieldFormulaTarget(
            FakeTable(TableURI("fieldfake://warehouse/orders")),
            otf.FieldRef(field_id="fld-gross_margin"),
        ),
        capabilities=otf.FormulaCapabilitySet(capabilities, details),
        observed_revision=HASH_A,
    )


def _grid_details() -> otf.FormulaCapabilityDetails:
    return otf.FormulaCapabilityDetails(
        target_kind="grid",
        dialects=(otf.GOOGLE_SHEETS_A1,),
        max_cells_per_operation=64,
        max_expression_bytes=2048,
        recalculation_scopes=(otf.GridRecalculationScope.RANGE.value,),
        calculation_states=(otf.CalculationState.PROVIDER_CURRENT,),
        mutation_atomicity=otf.MutationAtomicity.ATOMIC,
        revision_enforcement=otf.RevisionEnforcement.CHECKED,
        idempotency_strength=otf.IdempotencyStrength.HOST_LEDGER,
    )


def _field_details() -> otf.FormulaCapabilityDetails:
    return otf.FormulaCapabilityDetails(
        target_kind="field",
        dialects=(otf.MAYBE_BASE,),
        max_cells_per_operation=None,
        max_expression_bytes=2048,
        recalculation_scopes=(otf.FieldRecalculationScope.FIELD.value,),
        calculation_states=(otf.CalculationState.PROVIDER_CURRENT,),
        mutation_atomicity=otf.MutationAtomicity.ATOMIC,
        revision_enforcement=otf.RevisionEnforcement.CHECKED,
        idempotency_strength=otf.IdempotencyStrength.HOST_LEDGER,
    )


class FakeFormulaExtension:
    def __init__(
        self,
        *,
        store: FakeFormulaStore,
        broken: BrokenBehavior = DEFAULT_BROKEN,
        security_markers: Iterable[str] = (),
        grid_capabilities: tuple[CapabilityIdentity, ...] | None = None,
        field_capabilities: tuple[CapabilityIdentity, ...] | None = None,
        grid_data: GridCaseData | None = None,
    ) -> None:
        self.store = store
        self.broken = broken
        self.security_markers = tuple(security_markers)
        self.grid_data = grid_data or grid_case_data()
        self.field_data = field_case_data()
        self.grid_capabilities = grid_capabilities or (
            otf.GRID_READ,
            otf.GRID_SET,
            otf.GRID_VALUES_READ,
            otf.GRID_RECALCULATE,
        )
        self.field_capabilities = field_capabilities or (
            otf.FIELD_READ,
            otf.FIELD_SET,
            otf.FIELD_VALUES_READ,
            otf.FIELD_RECALCULATE,
        )
        self.grid_details = _grid_details()
        self.field_details = _field_details()
        self.operation_ids: list[str] = []
        self.ledger_snapshots: list[object] = []
        self.reprs: list[str] = []

    def bind_grid(
        self,
        request: otf.GridFormulaBindRequest,
    ) -> otf.FormulaExtensionResult[otf.GridFormulaBinding]:
        return otf.FormulaExtensionResult(
            value=_grid_binding(self.grid_capabilities, self.grid_details),
            outcome=otf.FormulaOutcome.SUCCEEDED,
            commit=otf.FormulaCommitState.NOT_APPLICABLE,
            verification=otf.FormulaVerificationState.PASSED,
            receipts=(),
        )

    def read_grid(
        self,
        request: otf.GridFormulaReadRequest,
    ) -> otf.FormulaExtensionResult[otf.GridFormulaObservation]:
        if self.broken.reject_grid_read:
            raise AssertionError("unadvertised grid read was called")
        if request.cell_range == self.grid_data.literal_range:
            formulas = ()
            if self.broken.infer_formula_from_leading_equals:
                formulas = (
                    otf.FormulaCell(
                        "C3",
                        otf.FormulaExpression(self.store.literal_text, otf.GOOGLE_SHEETS_A1),
                    ),
                )
            value = otf.GridFormulaObservation(
                worksheet_id="ws-model",
                requested_range=request.cell_range,
                formulas=formulas,
                observed_revision=self.store.grid_revision,
            )
        else:
            value = otf.GridFormulaObservation(
                worksheet_id="ws-model",
                requested_range=request.cell_range,
                formulas=self.store.grid_formulas,
                observed_revision=self.store.grid_revision,
            )
        receipt = otf.FormulaReceiptDetails.for_grid_read(
            target="gridfake://warehouse/model",
            selector=request.cell_range,
            capability=otf.GRID_READ.to_reference(),
            dialect=otf.GOOGLE_SHEETS_A1,
            observation_sha256=otf.formula_observation_hash(value),
            observed_count=len(value.formulas),
            revision_after=value.observed_revision,
        )
        return otf.FormulaExtensionResult(
            value=value,
            outcome=otf.FormulaOutcome.SUCCEEDED,
            commit=otf.FormulaCommitState.NOT_APPLICABLE,
            verification=otf.FormulaVerificationState.PASSED,
            receipts=(receipt,),
        )

    def set_grid(
        self,
        request: otf.GridFormulaSetRequest,
    ) -> otf.FormulaExtensionResult[otf.FormulaMutation]:
        if otf.GRID_SET.to_reference() in self.broken.unsupported_capabilities:
            return _unsupported_result(target_kind="grid", capability=otf.GRID_SET.to_reference())
        if (
            request.expected_revision is not None
            and request.expected_revision != self.store.grid_revision
            and not self.broken.accept_stale_revision
        ):
            return otf.FormulaExtensionResult(
                value=None,
                outcome=otf.FormulaOutcome.REJECTED,
                commit=otf.FormulaCommitState.NOT_STARTED,
                verification=otf.FormulaVerificationState.SKIPPED,
                receipts=(),
                error=otf.FormulaExtensionErrorInfo(
                    code=otf.FormulaErrorCode.STALE_REVISION,
                    message="revision changed",
                    safe_details={"revision_hash": self.store.grid_revision},
                ),
            )
        if request.idempotency_key is not None:
            decision = self.store.idempotency.begin(
                connector_id="gridfake",
                capability=otf.GRID_SET.to_reference(),
                target_hash=stable_hash("gridfake://warehouse/model"),
                selector_hash=stable_hash(request.cell_range),
                idempotency_key=request.idempotency_key,
                payload_hash=request.expression.sha256,
            )
            if (
                decision.disposition is otf.FormulaIdempotencyDisposition.CONFLICT
                and not self.broken.allow_idempotency_reuse
            ):
                return otf.FormulaExtensionResult(
                    value=None,
                    outcome=otf.FormulaOutcome.REJECTED,
                    commit=otf.FormulaCommitState.NOT_STARTED,
                    verification=otf.FormulaVerificationState.SKIPPED,
                    receipts=(),
                    error=otf.FormulaExtensionErrorInfo(
                        code=otf.FormulaErrorCode.IDEMPOTENCY_CONFLICT,
                        message="idempotency payload changed",
                        safe_details={
                            "operation_hash": decision.operation_hash,
                            "payload_hash": request.expression.sha256,
                        },
                    ),
                )
        self.store.grid_formulas = (
            _broadcast_formulas(request.expression)
            if self.broken.broadcast_copy_fill
            else _copy_fill_formulas(request.expression)
        )
        self.store.grid_revision = HASH_B if self.store.grid_revision == HASH_A else HASH_C
        observation = otf.GridFormulaObservation(
            worksheet_id="ws-model",
            requested_range=request.cell_range,
            formulas=self.store.grid_formulas,
            observed_revision=self.store.grid_revision,
        )
        mutation = otf.FormulaMutation(
            target_kind="grid",
            affected_count=len(observation.formulas),
            formula_observation=observation,
            revision_before=request.expected_revision or HASH_A,
            revision_after=observation.observed_revision,
        )
        receipt = otf.FormulaReceiptDetails.for_grid_set(
            target=_receipt_target(
                request.target.grid.value,
                expression=request.expression,
                broken=self.broken,
            ),
            selector=request.cell_range,
            capability=otf.GRID_SET.to_reference(),
            dialect=request.expression.dialect,
            expression_sha256=request.expression.sha256,
            observation_sha256=otf.formula_observation_hash(observation),
            affected_count=mutation.affected_count,
            revision_before=mutation.revision_before,
            revision_after=mutation.revision_after,
            mutation_atomicity=self.grid_details.mutation_atomicity.value,
            revision_enforcement=self.grid_details.revision_enforcement.value,
            verification="formula_text_readback",
        )
        if request.idempotency_key is not None and not (
            self.broken.allow_idempotency_reuse
            and decision.disposition is otf.FormulaIdempotencyDisposition.CONFLICT
        ):
            self.store.idempotency.succeed(
                connector_id="gridfake",
                target_hash=stable_hash("gridfake://warehouse/model"),
                selector_hash=stable_hash(request.cell_range),
                idempotency_key=request.idempotency_key,
                payload_hash=request.expression.sha256,
                operation_hash=stable_hash("grid-op"),
            )
        for marker in self.security_markers:
            _maybe_emit_security_leak(
                self.broken,
                self.broken.security_leak_channel or "",
                marker,
                operation_ids=self.operation_ids,
                ledger_snapshots=self.ledger_snapshots,
                reprs=self.reprs,
            )
        self.operation_ids.append(stable_hash("grid-op-id"))
        self.ledger_snapshots.append(
            {
                "entries": [
                    {
                        "payload_hash": request.expression.sha256,
                        "state": "succeeded",
                    }
                ]
            }
        )
        self.reprs.append(
            repr(
                {
                    "target_kind": mutation.target_kind,
                    "affected_count": mutation.affected_count,
                    "revision_after": mutation.revision_after,
                }
            )
        )
        if self.broken.security_leak_channel == "error":
            return otf.FormulaExtensionResult(
                value=None,
                outcome=otf.FormulaOutcome.FAILED,
                commit=otf.FormulaCommitState.COMMITTED,
                verification=otf.FormulaVerificationState.FAILED,
                receipts=(receipt,),
                error=otf.FormulaExtensionErrorInfo(
                    code=otf.FormulaErrorCode.EXECUTION_FAILED,
                    message=self.security_markers[0],
                    safe_details={"target_kind": "grid"},
                ),
            )
        return otf.FormulaExtensionResult(
            value=mutation,
            outcome=otf.FormulaOutcome.SUCCEEDED,
            commit=otf.FormulaCommitState.COMMITTED,
            verification=otf.FormulaVerificationState.PASSED,
            receipts=(receipt,),
        )

    def read_grid_values(
        self,
        request: otf.GridFormulaValueReadRequest,
    ) -> otf.FormulaExtensionResult[otf.GridFormulaValueObservation]:
        if otf.GRID_VALUES_READ.to_reference() in self.broken.unsupported_capabilities:
            return _unsupported_result(
                target_kind="grid",
                capability=otf.GRID_VALUES_READ.to_reference(),
            )
        if self.broken.value_without_dependency_scope:
            value = SimpleNamespace(
                worksheet_id="ws-model",
                requested_range=request.cell_range,
                values=self.grid_data.expected_values.values,
                calculation_state=otf.CalculationState.PROVIDER_CURRENT,
                calculation_trigger=otf.CalculationTrigger.PROVIDER_READ,
                dependency_scope=None,
                observed_revision=HASH_C,
            )
            return otf.FormulaExtensionResult(
                value=value,  # type: ignore[arg-type]
                outcome=otf.FormulaOutcome.SUCCEEDED,
                commit=otf.FormulaCommitState.NOT_APPLICABLE,
                verification=otf.FormulaVerificationState.PASSED,
                receipts=(),
            )
        value = self.grid_data.expected_values
        receipt = otf.FormulaReceiptDetails.for_grid_values_read(
            target="gridfake://warehouse/model",
            selector=request.cell_range,
            capability=otf.GRID_VALUES_READ.to_reference(),
            dialect=otf.GOOGLE_SHEETS_A1,
            observation_sha256=stable_hash("grid-formulas"),
            value_observation_sha256=otf.formula_observation_hash(value),
            observed_count=len(value.values),
            revision_after=value.observed_revision,
            calculation_state=value.calculation_state.value,
            calculation_trigger=value.calculation_trigger.value,
            dependency_scope=value.dependency_scope,
        )
        return otf.FormulaExtensionResult(
            value=value,
            outcome=otf.FormulaOutcome.SUCCEEDED,
            commit=otf.FormulaCommitState.NOT_APPLICABLE,
            verification=otf.FormulaVerificationState.PASSED,
            receipts=(receipt,),
        )

    def recalculate_grid(
        self,
        request: otf.GridFormulaRecalculateRequest,
    ) -> otf.FormulaExtensionResult[otf.RecalculationObservation]:
        value = self.grid_data.expected_recalculation
        return otf.FormulaExtensionResult(
            value=value,
            outcome=otf.FormulaOutcome.SUCCEEDED,
            commit=otf.FormulaCommitState.COMMITTED,
            verification=otf.FormulaVerificationState.PASSED,
            receipts=(),
        )

    def bind_field(
        self,
        request: otf.FieldFormulaBindRequest[FakeTable],
    ) -> otf.FormulaExtensionResult[otf.FieldFormulaBinding[FakeTable]]:
        return otf.FormulaExtensionResult(
            value=_field_binding(self.field_capabilities, self.field_details),
            outcome=otf.FormulaOutcome.SUCCEEDED,
            commit=otf.FormulaCommitState.NOT_APPLICABLE,
            verification=otf.FormulaVerificationState.PASSED,
            receipts=(),
        )

    def read_field(
        self,
        request: otf.FieldFormulaReadRequest[FakeTable],
    ) -> otf.FormulaExtensionResult[otf.FieldFormulaObservation]:
        if self.broken.reject_field_read:
            raise AssertionError("unadvertised field read was called")
        value = otf.FieldFormulaObservation(
            table_uri=request.target.table.uri,
            field_id=request.target.field.field_id or "fld-gross_margin",
            field_name="gross_margin",
            expression=self.store.field_expression,
            result_type="number",
            observed_revision=self.store.field_revision,
        )
        receipt = otf.FormulaReceiptDetails(
            target_kind="field",
            table_mode="base",
            target=request.target.table.uri.value,
            selector=value.field_id,
            capability=otf.FIELD_READ.to_reference(),
            dialect=value.expression.dialect,
            observation_sha256=otf.formula_observation_hash(value),
            observed_count=1,
            revision_after=value.observed_revision,
        )
        return otf.FormulaExtensionResult(
            value=value,
            outcome=otf.FormulaOutcome.SUCCEEDED,
            commit=otf.FormulaCommitState.NOT_APPLICABLE,
            verification=otf.FormulaVerificationState.PASSED,
            receipts=(receipt,),
        )

    def set_field(
        self,
        request: otf.FieldFormulaSetRequest[FakeTable],
    ) -> otf.FormulaExtensionResult[otf.FormulaMutation]:
        if request.expected_revision != self.store.field_revision and not self.broken.accept_stale_revision:
            return otf.FormulaExtensionResult(
                value=None,
                outcome=otf.FormulaOutcome.REJECTED,
                commit=otf.FormulaCommitState.NOT_STARTED,
                verification=otf.FormulaVerificationState.SKIPPED,
                receipts=(),
                error=otf.FormulaExtensionErrorInfo(
                    code=otf.FormulaErrorCode.STALE_REVISION,
                    message="revision changed",
                    safe_details={"revision_hash": self.store.field_revision},
                ),
            )
        if request.idempotency_key is not None:
            decision = self.store.idempotency.begin(
                connector_id="fieldfake",
                capability=otf.FIELD_SET.to_reference(),
                target_hash=stable_hash(request.target.table.uri.value),
                selector_hash=stable_hash(request.target.field.field_id or ""),
                idempotency_key=request.idempotency_key,
                payload_hash=request.expression.sha256,
            )
            if (
                decision.disposition is otf.FormulaIdempotencyDisposition.CONFLICT
                and not self.broken.allow_idempotency_reuse
            ):
                return otf.FormulaExtensionResult(
                    value=None,
                    outcome=otf.FormulaOutcome.REJECTED,
                    commit=otf.FormulaCommitState.NOT_STARTED,
                    verification=otf.FormulaVerificationState.SKIPPED,
                    receipts=(),
                    error=otf.FormulaExtensionErrorInfo(
                        code=otf.FormulaErrorCode.IDEMPOTENCY_CONFLICT,
                        message="idempotency payload changed",
                        safe_details={"payload_hash": request.expression.sha256},
                    ),
                )
        self.store.field_expression = request.expression
        self.store.field_revision = HASH_B if self.store.field_revision == HASH_A else HASH_C
        field_id = "fld-converted" if self.broken.field_conversion else "fld-gross_margin"
        observation = otf.FieldFormulaObservation(
            table_uri=request.target.table.uri,
            field_id=field_id,
            field_name="gross_margin",
            expression=request.expression,
            result_type="number",
            observed_revision=self.store.field_revision,
        )
        mutation = otf.FormulaMutation(
            target_kind="field",
            affected_count=1,
            formula_observation=observation,
            revision_before=request.expected_revision,
            revision_after=observation.observed_revision,
        )
        receipt = otf.FormulaReceiptDetails.for_field_set(
            target=_receipt_target(
                request.target.table.uri.value,
                expression=request.expression,
                broken=self.broken,
            ),
            selector=field_id,
            capability=otf.FIELD_SET.to_reference(),
            dialect=request.expression.dialect,
            expression_sha256=request.expression.sha256,
            observation_sha256=otf.formula_observation_hash(observation),
            affected_count=1,
            revision_before=request.expected_revision,
            revision_after=observation.observed_revision,
            mutation_atomicity=self.field_details.mutation_atomicity.value,
            revision_enforcement=self.field_details.revision_enforcement.value,
            verification="formula_text_readback",
        )
        if request.idempotency_key is not None and not (
            self.broken.allow_idempotency_reuse
            and decision.disposition is otf.FormulaIdempotencyDisposition.CONFLICT
        ):
            self.store.idempotency.succeed(
                connector_id="fieldfake",
                target_hash=stable_hash(request.target.table.uri.value),
                selector_hash=stable_hash(request.target.field.field_id or ""),
                idempotency_key=request.idempotency_key,
                payload_hash=request.expression.sha256,
                operation_hash=stable_hash("field-op"),
            )
        for marker in self.security_markers:
            _maybe_emit_security_leak(
                self.broken,
                self.broken.security_leak_channel or "",
                marker,
                operation_ids=self.operation_ids,
                ledger_snapshots=self.ledger_snapshots,
                reprs=self.reprs,
            )
        self.operation_ids.append(stable_hash("field-op-id"))
        self.ledger_snapshots.append(
            {
                "entries": [
                    {
                        "payload_hash": request.expression.sha256,
                        "state": "succeeded",
                    }
                ]
            }
        )
        self.reprs.append(
            repr(
                {
                    "target_kind": mutation.target_kind,
                    "affected_count": mutation.affected_count,
                    "revision_after": mutation.revision_after,
                }
            )
        )
        if self.broken.security_leak_channel == "error":
            return otf.FormulaExtensionResult(
                value=None,
                outcome=otf.FormulaOutcome.FAILED,
                commit=otf.FormulaCommitState.COMMITTED,
                verification=otf.FormulaVerificationState.FAILED,
                receipts=(receipt,),
                error=otf.FormulaExtensionErrorInfo(
                    code=otf.FormulaErrorCode.EXECUTION_FAILED,
                    message=self.security_markers[0],
                    safe_details={"target_kind": "field"},
                ),
            )
        return otf.FormulaExtensionResult(
            value=mutation,
            outcome=otf.FormulaOutcome.SUCCEEDED,
            commit=otf.FormulaCommitState.COMMITTED,
            verification=otf.FormulaVerificationState.PASSED,
            receipts=(receipt,),
        )

    def read_field_values(
        self,
        request: otf.FieldFormulaValueReadRequest[FakeTable],
    ) -> otf.FormulaExtensionResult[otf.FieldFormulaValueObservation]:
        if otf.FIELD_VALUES_READ.to_reference() in self.broken.unsupported_capabilities:
            return _unsupported_result(
                target_kind="field",
                capability=otf.FIELD_VALUES_READ.to_reference(),
            )
        value = self.field_data.expected_values
        receipt = otf.FormulaReceiptDetails.for_field_values_read(
            target=request.target.table.uri.value,
            selector=request.target.field.field_id or "fld-gross_margin",
            capability=otf.FIELD_VALUES_READ.to_reference(),
            dialect=value.values[0].value.kind if False else otf.MAYBE_BASE,
            observation_sha256=stable_hash("field-formulas"),
            value_observation_sha256=otf.formula_observation_hash(value),
            observed_count=len(value.values),
            revision_after=value.observed_revision,
            calculation_state=value.calculation_state.value,
            calculation_trigger=value.calculation_trigger.value,
            dependency_scope=value.dependency_scope,
        )
        return otf.FormulaExtensionResult(
            value=value,
            outcome=otf.FormulaOutcome.SUCCEEDED,
            commit=otf.FormulaCommitState.NOT_APPLICABLE,
            verification=otf.FormulaVerificationState.PASSED,
            receipts=(receipt,),
        )

    def recalculate_field(
        self,
        request: otf.FieldFormulaRecalculateRequest[FakeTable],
    ) -> otf.FormulaExtensionResult[otf.RecalculationObservation]:
        return otf.FormulaExtensionResult(
            value=self.field_data.expected_recalculation,
            outcome=otf.FormulaOutcome.SUCCEEDED,
            commit=otf.FormulaCommitState.COMMITTED,
            verification=otf.FormulaVerificationState.PASSED,
            receipts=(),
        )


def grid_case_kwargs(
    *,
    broken: BrokenBehavior = DEFAULT_BROKEN,
    static_capabilities: tuple[CapabilityIdentity, ...] | None = None,
    provider_id: str = "gridfake",
    set_expression: otf.FormulaExpression | None = None,
) -> dict[str, Any]:
    store = FakeFormulaStore()
    case_data = grid_case_data(set_expression=set_expression)
    capabilities = static_capabilities or (
        otf.GRID_READ,
        otf.GRID_SET,
        otf.GRID_VALUES_READ,
        otf.GRID_RECALCULATE,
    )

    def extension_factory() -> FakeFormulaExtension:
        return FakeFormulaExtension(
            store=store,
            broken=broken,
            security_markers=SECURITY_MARKERS,
            grid_capabilities=capabilities,
            grid_data=case_data,
        )

    return {
        "provider_id": provider_id,
        "target_kind": "grid",
        "dialect": otf.GOOGLE_SHEETS_A1,
        "static_capabilities": capabilities,
        "extension_factory": extension_factory,
        "grid_target_factory": make_grid_target,
        "field_target_factory": None,
        "grid_case": case_data,
        "field_case": None,
        "supports_independent_sessions": True,
        "configured_live_evidence": None,
        "security_markers": (),
        "security_expression": SECURITY_EXPRESSION,
        "security_probe_values": SECURITY_MARKERS,
    }


def field_case_kwargs(
    *,
    broken: BrokenBehavior = DEFAULT_BROKEN,
    static_capabilities: tuple[CapabilityIdentity, ...] | None = None,
    provider_id: str = "fieldfake",
) -> dict[str, Any]:
    store = FakeFormulaStore()
    capabilities = static_capabilities or (
        otf.FIELD_READ,
        otf.FIELD_SET,
        otf.FIELD_VALUES_READ,
        otf.FIELD_RECALCULATE,
    )

    def extension_factory() -> FakeFormulaExtension:
        return FakeFormulaExtension(
            store=store,
            broken=broken,
            security_markers=SECURITY_MARKERS,
            field_capabilities=capabilities,
        )

    return {
        "provider_id": provider_id,
        "target_kind": "field",
        "dialect": otf.MAYBE_BASE,
        "static_capabilities": capabilities,
        "extension_factory": extension_factory,
        "grid_target_factory": None,
        "field_target_factory": make_field_target,
        "grid_case": None,
        "field_case": field_case_data(),
        "supports_independent_sessions": True,
        "configured_live_evidence": "configured-live:tenant-a",
        "security_markers": (),
        "security_expression": otf.FormulaExpression(SECURITY_EXPRESSION.text, otf.MAYBE_BASE),
        "security_probe_values": SECURITY_MARKERS,
    }


def collect_security_probe(*, leak_channel: str | None = None) -> SecurityProbe:
    store = FakeFormulaStore()
    broken = BrokenBehavior(security_leak_channel=leak_channel)
    extension = FakeFormulaExtension(store=store, broken=broken, security_markers=SECURITY_MARKERS)
    binding = extension.bind_grid(otf.GridFormulaBindRequest(make_grid_target())).value
    assert binding is not None
    warnings_seen: list[str] = []

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = extension.set_grid(
            otf.GridFormulaSetRequest(
                target=binding.target,
                cell_range="A1:B2",
                expression=SECURITY_EXPRESSION,
                expected_revision=HASH_A,
                idempotency_key="security-probe",
            )
        )
        warnings_seen.extend(str(item.message) for item in caught)

    mutation = result.value
    assert mutation is not None
    logs = tuple()
    if leak_channel == "log":
        logs = tuple(SECURITY_MARKERS)
    return SecurityProbe(
        mutation=mutation,
        receipts=result.receipts,
        warnings=tuple(warnings_seen),
        logs=logs,
        reprs=tuple(extension.reprs),
        operation_ids=tuple(extension.operation_ids),
        ledger_snapshots=tuple(extension.ledger_snapshots),
    )
