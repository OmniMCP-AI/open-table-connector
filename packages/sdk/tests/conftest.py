from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

import open_table_connector.formulas as otf
import open_table_connector.sdk as otc
import polars as pl
import pyarrow as pa
import pytest
from open_table_connector.contract import (
    ArrowReadResult,
    BaseConvention,
    CapabilityIdentity,
    ConnectorErrorCode,
    ConnectorIdentity,
    ExecutionRequest,
    ExecutionResult,
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
from open_table_connector.sdk.connector import ArrowTableCarrier
from open_table_connector.timeseries import (
    AbortDisposition as LegacyAbortDisposition,
)
from open_table_connector.timeseries import (
    ManagedAbortReceipt,
    ManagedCommitReceipt,
    ManagedCurrentResult,
    ManagedReadbackReceipt,
    ManagedReadbackResult,
    ManagedStageReceipt,
    OrderDirection,
    OrderKey,
    PolarsTemporalExecutor,
    ResourceBounds,
    TemporalExtensionError,
    TemporalReceipt,
    VisibilityGuarantee,
    temporal_descriptor_hash,
)

from packages.timeseries.tests.fixtures import (
    MemoryTemporalSource,
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


def _utc(timestamp: str) -> str:
    return timestamp


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _stage_id(seed: str) -> str:
    return "stage:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _frame_arrow_bytes(frame: pl.DataFrame) -> bytes:
    table = frame.to_arrow()
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return sink.getvalue().to_pybytes()


def _formula_hash(seed: str) -> str:
    return _sha256(seed.encode("utf-8"))


def _grid_formula_details(
    *,
    dialects: tuple[str, ...] = (otf.GOOGLE_SHEETS_A1,),
    recalculation_scopes: tuple[str, ...] = (
        otf.GridRecalculationScope.RANGE.value,
        otf.GridRecalculationScope.WORKSHEET.value,
    ),
) -> otf.FormulaCapabilityDetails:
    return otf.FormulaCapabilityDetails(
        target_kind="grid",
        dialects=dialects,
        max_cells_per_operation=128,
        max_expression_bytes=1024,
        recalculation_scopes=recalculation_scopes,
        calculation_states=(
            otf.CalculationState.PROVIDER_CURRENT,
            otf.CalculationState.CACHED,
        ),
        mutation_atomicity=otf.MutationAtomicity.ATOMIC,
        revision_enforcement=otf.RevisionEnforcement.CHECKED,
        idempotency_strength=otf.IdempotencyStrength.HOST_LEDGER,
    )


def _field_formula_details(
    *,
    dialects: tuple[str, ...] = (otf.MAYBE_BASE,),
    recalculation_scopes: tuple[str, ...] = (otf.FieldRecalculationScope.FIELD.value,),
) -> otf.FormulaCapabilityDetails:
    return otf.FormulaCapabilityDetails(
        target_kind="field",
        dialects=dialects,
        max_cells_per_operation=None,
        max_expression_bytes=1024,
        recalculation_scopes=recalculation_scopes,
        calculation_states=(
            otf.CalculationState.PROVIDER_CURRENT,
            otf.CalculationState.UNKNOWN,
        ),
        mutation_atomicity=otf.MutationAtomicity.ATOMIC,
        revision_enforcement=otf.RevisionEnforcement.CHECKED,
        idempotency_strength=otf.IdempotencyStrength.RECONCILED,
    )


def _temporal_receipt(
    *,
    operation: str,
    descriptor_hash: str,
    row_count: int,
    returned_bytes: int,
    target: str,
    snapshot_reference: str | None = None,
) -> TemporalReceipt:
    return TemporalReceipt(
        schema_version="otc.temporal-receipt/v1",
        neutral_receipt=NeutralReceipt(
            connector=ConnectorIdentity("fake", "0.1.0", "1.0"),
            capability=CapabilityIdentity(operation, "1.0"),
            operation_id=f"{operation}-1",
            safe_uri=TableURI(target),
            mode=LegacyTableMode.BASE,
            source_revision="rev-temporal",
            schema_fingerprint="schema-temporal",
            content_fingerprint="content-temporal",
            coordinate_convention=BaseConvention(key_fields=("symbol", "ts")),
            row_count=row_count,
            batch_count=1,
        ),
        descriptor_hash=descriptor_hash,
        requested_range=None,
        observed_range=None,
        output_order=(OrderKey("symbol", OrderDirection.ASC), OrderKey("ts", OrderDirection.ASC)),
        execution_location="connector",
        resource_bounds=ResourceBounds(100_000, 128 * 1024 * 1024, 30_000),
        examined_rows=row_count,
        examined_bytes=returned_bytes,
        returned_rows=row_count,
        returned_bytes=returned_bytes,
        elapsed_ms=1,
        snapshot_reference=snapshot_reference,
        plan_schema_version="otc.portable-temporal-plan/v1",
        portable_plan_hash=_sha256(operation.encode("utf-8")),
    )


@dataclass
class FakeTemporalExtension:
    target_uri: str = "fake://warehouse/orders"
    source: MemoryTemporalSource = field(default_factory=MemoryTemporalSource)
    current_time_text: str = "2026-08-29T00:30:00.000000000Z"
    ambiguous_commit: bool = False
    append_calls: list[tuple[str, int]] = field(default_factory=list)
    upsert_calls: list[tuple[str, int]] = field(default_factory=list)
    staged_frames: dict[str, pl.DataFrame] = field(default_factory=dict)
    committed_frames: dict[str, pl.DataFrame] = field(default_factory=dict)
    committed_stage_ids: set[str] = field(default_factory=set)

    def descriptor_hash_for(self, _binding, descriptor) -> str:
        return temporal_descriptor_hash(descriptor, self.source.table.schema)

    def executor_for(self, _binding, descriptor):
        self.source.descriptor = descriptor
        return PolarsTemporalExecutor(
            self.source,
            connector_identity=ConnectorIdentity("fake", "0.1.0", "1.0"),
        )

    def append_rows(self, _binding, descriptor, frame: pl.DataFrame, *, idempotency_key: str):
        self.source.descriptor = descriptor
        self.append_calls.append((idempotency_key, frame.height))
        return otc.OperationResult(
            value=frame.height,
            outcome=otc.Outcome.SUCCEEDED,
            commit=otc.CommitState.COMMITTED,
            verification=otc.VerificationState.PASSED,
            receipts=(
                make_receipt("timeseries.append", uri=self.target_uri, row_count=frame.height),
            ),
        )

    def upsert_rows(self, _binding, descriptor, frame: pl.DataFrame, *, idempotency_key: str):
        self.source.descriptor = descriptor
        self.upsert_calls.append((idempotency_key, frame.height))
        return otc.OperationResult(
            value=frame.height,
            outcome=otc.Outcome.SUCCEEDED,
            commit=otc.CommitState.COMMITTED,
            verification=otc.VerificationState.PASSED,
            receipts=(
                make_receipt("timeseries.upsert", uri=self.target_uri, row_count=frame.height),
            ),
        )

    def stage_rows(self, _binding, descriptor, frame: pl.DataFrame, *, idempotency_key: str):
        self.source.descriptor = descriptor
        stage_id = _stage_id(idempotency_key)
        self.staged_frames[stage_id] = frame.clone()
        arrow_bytes = _frame_arrow_bytes(frame)
        return ManagedStageReceipt(
            schema_version="otc.managed-stage-receipt/v1",
            operation_id=f"stage-{idempotency_key}",
            logical_target=TableURI(self.target_uri),
            physical_target=TableURI(self.target_uri),
            stage_id=stage_id,
            idempotency_key=idempotency_key,
            artifact_hash=_sha256(arrow_bytes),
            descriptor_hash=self.descriptor_hash_for(_binding, descriptor),
            staged_at=_utc("2026-08-29T00:20:00.000000000Z"),
            visible=False,
        )

    def commit_stage(self, _binding, _descriptor, stage):
        if self.ambiguous_commit:
            raise TemporalExtensionError(
                ConnectorErrorCode.VISIBILITY_INCOMPLETE,
                "commit outcome is uncertain",
                {"stage_id": stage.stage_id},
            )
        frame = self.staged_frames[stage.stage_id]
        snapshot_id = _sha256(stage.stage_id.encode("utf-8"))
        self.committed_frames[snapshot_id] = frame
        self.committed_stage_ids.add(stage.stage_id)
        return ManagedCommitReceipt(
            schema_version="otc.managed-commit-receipt/v1",
            operation_id=f"commit-{stage.stage_id}",
            logical_target=stage.logical_target,
            stage_id=stage.stage_id,
            idempotency_key=stage.idempotency_key,
            snapshot_id=snapshot_id,
            snapshot_reference=f"snapshots/{stage.idempotency_key}.arrow",
            committed_at=_utc("2026-08-29T00:21:00.000000000Z"),
            visibility=VisibilityGuarantee.ATOMIC,
        )

    def readback_snapshot(self, _binding, _descriptor, snapshot):
        frame = self.committed_frames[snapshot.snapshot_id]
        table = frame.to_arrow()
        return ManagedReadbackResult(
            table=table,
            artifact=None,
            receipt=ManagedReadbackReceipt(
                schema_version="otc.managed-readback-receipt/v1",
                operation_id=f"readback-{snapshot.snapshot_id}",
                snapshot_id=snapshot.snapshot_id,
                observed_at=_utc("2026-08-29T00:22:00.000000000Z"),
                observed_schema_hash=_sha256(table.schema.serialize().to_pybytes()),
                observed_content_hash=_sha256(_frame_arrow_bytes(frame)),
                observed_rows=table.num_rows,
                observed_bytes=len(_frame_arrow_bytes(frame)),
                observed_range=None,
            ),
        )

    def current_snapshot(self, _binding, descriptor):
        if not self.committed_frames:
            return None
        snapshot_id, frame = next(reversed(self.committed_frames.items()))
        return ManagedCurrentResult(
            snapshot_id=snapshot_id,
            snapshot_reference="snapshots/current.arrow",
            committed_at=_utc("2026-08-29T00:22:00.000000000Z"),
            descriptor_hash=self.descriptor_hash_for(_binding, descriptor),
            schema=frame.to_arrow().schema,
        )

    def abort_stage(self, _binding, _descriptor, stage):
        disposition = (
            LegacyAbortDisposition.ALREADY_COMMITTED
            if stage.stage_id in self.committed_stage_ids
            else LegacyAbortDisposition.ALREADY_ABSENT
        )
        return ManagedAbortReceipt(
            schema_version="otc.managed-abort-receipt/v1",
            operation_id=f"abort-{stage.stage_id}",
            logical_target=stage.logical_target,
            stage_id=stage.stage_id,
            disposition=disposition,
            aborted_at=_utc("2026-08-29T00:23:00.000000000Z"),
        )


@dataclass
class FakeFormulaExtension:
    calls: list[tuple[str, object]] = field(default_factory=list)
    overrides: dict[str, otf.FormulaExtensionResult[object]] = field(default_factory=dict)
    grid_capabilities: tuple[CapabilityIdentity, ...] = (
        otf.GRID_READ,
        otf.GRID_SET,
        otf.GRID_VALUES_READ,
        otf.GRID_RECALCULATE,
    )
    field_capabilities: tuple[CapabilityIdentity, ...] = (
        otf.FIELD_READ,
        otf.FIELD_SET,
        otf.FIELD_VALUES_READ,
        otf.FIELD_RECALCULATE,
    )
    grid_details: otf.FormulaCapabilityDetails = field(default_factory=_grid_formula_details)
    field_details: otf.FormulaCapabilityDetails = field(default_factory=_field_formula_details)

    def _result(
        self,
        method: str,
        default: otf.FormulaExtensionResult[object],
    ) -> otf.FormulaExtensionResult[object]:
        return self.overrides.get(method, default)

    def _grid_binding(self, target: otf.GridFormulaTarget) -> otf.GridFormulaBinding:
        worksheet_id = target.worksheet.worksheet_id or "ws-model"
        return otf.GridFormulaBinding(
            target=otf.BoundGridFormulaTarget(
                grid=target.grid.value,
                worksheet=otf.WorksheetRef(worksheet_id=worksheet_id),
            ),
            capabilities=otf.FormulaCapabilitySet(self.grid_capabilities, self.grid_details),
            observed_revision=_formula_hash("grid-bound"),
        )

    def _field_binding(self, target: otf.FieldFormulaTarget[otc.Table]) -> otf.FieldFormulaBinding[otc.Table]:
        field_id = target.field.field_id or "fld-gross_margin"
        return otf.FieldFormulaBinding(
            target=otf.BoundFieldFormulaTarget(
                table=target.table,
                field=otf.FieldRef(field_id=field_id),
            ),
            capabilities=otf.FormulaCapabilitySet(self.field_capabilities, self.field_details),
            observed_revision=_formula_hash("field-bound"),
        )

    def _grid_observation(
        self,
        request: otf.GridFormulaReadRequest | otf.GridFormulaSetRequest,
        *,
        expression: otf.FormulaExpression | None = None,
        revision: str = "",
    ) -> otf.GridFormulaObservation:
        resolved_expression = expression or otf.FormulaExpression("=SUM(A1:A2)", self.grid_details.dialects[0])
        observed_revision = revision or _formula_hash("grid-observation")
        return otf.GridFormulaObservation(
            worksheet_id=request.target.worksheet.worksheet_id or "ws-model",
            requested_range=request.cell_range,
            formulas=(otf.FormulaCell("A1", resolved_expression),),
            observed_revision=observed_revision,
        )

    def _field_observation(
        self,
        request: otf.FieldFormulaReadRequest[otc.Table] | otf.FieldFormulaSetRequest[otc.Table],
        *,
        expression: otf.FormulaExpression | None = None,
        revision: str = "",
    ) -> otf.FieldFormulaObservation:
        resolved_expression = expression or otf.FormulaExpression("gross * 0.2", self.field_details.dialects[0])
        observed_revision = revision or _formula_hash("field-observation")
        return otf.FieldFormulaObservation(
            table_uri=request.target.table.uri,
            field_id=request.target.field.field_id or "fld-gross_margin",
            field_name="gross_margin",
            expression=resolved_expression,
            result_type="number",
            observed_revision=observed_revision,
        )

    def bind_grid(
        self,
        request: otf.GridFormulaBindRequest,
    ) -> otf.FormulaExtensionResult[otf.GridFormulaBinding]:
        self.calls.append(("bind_grid", request))
        default = otf.FormulaExtensionResult(
            value=self._grid_binding(request.target),
            outcome=otf.FormulaOutcome.SUCCEEDED,
            commit=otf.FormulaCommitState.NOT_APPLICABLE,
            verification=otf.FormulaVerificationState.PASSED,
            receipts=(),
        )
        return self._result("bind_grid", default)  # type: ignore[return-value]

    def read_grid(
        self,
        request: otf.GridFormulaReadRequest,
    ) -> otf.FormulaExtensionResult[otf.GridFormulaObservation]:
        self.calls.append(("read_grid", request))
        observation = self._grid_observation(request)
        default = otf.FormulaExtensionResult(
            value=observation,
            outcome=otf.FormulaOutcome.SUCCEEDED,
            commit=otf.FormulaCommitState.NOT_APPLICABLE,
            verification=otf.FormulaVerificationState.PASSED,
            receipts=(
                otf.FormulaReceiptDetails.for_grid_read(
                    target=request.target.grid.value,
                    selector=request.cell_range,
                    capability=otf.GRID_READ.to_reference(),
                    dialect=observation.formulas[0].expression.dialect,
                    observation_sha256=otf.formula_observation_hash(observation),
                    observed_count=len(observation.formulas),
                    revision_after=observation.observed_revision,
                ),
            ),
        )
        return self._result("read_grid", default)  # type: ignore[return-value]

    def set_grid(
        self,
        request: otf.GridFormulaSetRequest,
    ) -> otf.FormulaExtensionResult[otf.FormulaMutation]:
        self.calls.append(("set_grid", request))
        observation = self._grid_observation(
            request,
            expression=request.expression,
            revision=_formula_hash("grid-set"),
        )
        mutation = otf.FormulaMutation(
            target_kind="grid",
            affected_count=1,
            formula_observation=observation,
            revision_before=request.expected_revision,
            revision_after=_formula_hash("grid-set-result"),
        )
        default = otf.FormulaExtensionResult(
            value=mutation,
            outcome=otf.FormulaOutcome.SUCCEEDED,
            commit=otf.FormulaCommitState.COMMITTED,
            verification=otf.FormulaVerificationState.PASSED,
            receipts=(
                otf.FormulaReceiptDetails.for_grid_set(
                    target=request.target.grid.value,
                    selector=request.cell_range,
                    capability=otf.GRID_SET.to_reference(),
                    dialect=request.expression.dialect,
                    expression_sha256=request.expression.sha256,
                    observation_sha256=otf.formula_observation_hash(observation),
                    affected_count=mutation.affected_count,
                    revision_before=request.expected_revision,
                    revision_after=mutation.revision_after,
                    mutation_atomicity=self.grid_details.mutation_atomicity.value,
                    revision_enforcement=self.grid_details.revision_enforcement.value,
                    verification="formula_text_readback",
                ),
            ),
        )
        return self._result("set_grid", default)  # type: ignore[return-value]

    def read_grid_values(
        self,
        request: otf.GridFormulaValueReadRequest,
    ) -> otf.FormulaExtensionResult[otf.GridFormulaValueObservation]:
        self.calls.append(("read_grid_values", request))
        observation = otf.GridFormulaValueObservation(
            worksheet_id=request.target.worksheet.worksheet_id or "ws-model",
            requested_range=request.cell_range,
            values=(
                otf.FormulaValueCell("A1", otf.FormulaValue.from_python("computed-secret")),
            ),
            calculation_state=otf.CalculationState.PROVIDER_CURRENT,
            calculation_trigger=otf.CalculationTrigger.PROVIDER_READ,
            dependency_scope="provider_dynamic",
            observed_revision=_formula_hash("grid-values"),
        )
        formula_observation = self._grid_observation(
            otf.GridFormulaReadRequest(target=request.target, cell_range=request.cell_range),
            expression=otf.FormulaExpression("=HYPERLINK(\"https://secret.example\", \"x\")", self.grid_details.dialects[0]),
            revision=observation.observed_revision,
        )
        default = otf.FormulaExtensionResult(
            value=observation,
            outcome=otf.FormulaOutcome.SUCCEEDED,
            commit=otf.FormulaCommitState.NOT_APPLICABLE,
            verification=otf.FormulaVerificationState.PASSED,
            receipts=(
                otf.FormulaReceiptDetails.for_grid_values_read(
                    target=request.target.grid.value,
                    selector=request.cell_range,
                    capability=otf.GRID_VALUES_READ.to_reference(),
                    dialect=formula_observation.formulas[0].expression.dialect,
                    observation_sha256=otf.formula_observation_hash(formula_observation),
                    value_observation_sha256=otf.formula_observation_hash(observation),
                    observed_count=len(observation.values),
                    revision_after=observation.observed_revision,
                    calculation_state=observation.calculation_state.value,
                    calculation_trigger=observation.calculation_trigger.value,
                    dependency_scope=observation.dependency_scope,
                ),
            ),
        )
        return self._result("read_grid_values", default)  # type: ignore[return-value]

    def recalculate_grid(
        self,
        request: otf.GridFormulaRecalculateRequest,
    ) -> otf.FormulaExtensionResult[otf.RecalculationObservation]:
        self.calls.append(("recalculate_grid", request))
        value_observation = otf.GridFormulaValueObservation(
            worksheet_id=request.target.worksheet.worksheet_id or "ws-model",
            requested_range=request.cell_range or "A1",
            values=(otf.FormulaValueCell("A1", otf.FormulaValue.from_python(21)),),
            calculation_state=otf.CalculationState.PROVIDER_CURRENT,
            calculation_trigger=otf.CalculationTrigger.EXPLICIT_RECALCULATION,
            dependency_scope="provider_dynamic",
            observed_revision=_formula_hash("grid-recalculate-values"),
        )
        default = otf.FormulaExtensionResult(
            value=otf.RecalculationObservation(
                target_kind="grid",
                requested_scope=request.scope.value,
                effective_scope=request.scope.value,
                revision_before=request.expected_revision,
                revision_after=_formula_hash("grid-recalculate"),
                provider_status="completed",
                calculation_state=otf.CalculationState.PROVIDER_CURRENT,
                verification="passed",
                value_observation=value_observation,
            ),
            outcome=otf.FormulaOutcome.SUCCEEDED,
            commit=otf.FormulaCommitState.COMMITTED,
            verification=otf.FormulaVerificationState.PASSED,
            receipts=(
                otf.FormulaReceiptDetails.for_grid_values_read(
                    target=request.target.grid.value,
                    selector=request.cell_range or request.scope.value,
                    capability=otf.GRID_RECALCULATE.to_reference(),
                    dialect=self.grid_details.dialects[0],
                    observation_sha256=_formula_hash("grid-recalculate-observation"),
                    value_observation_sha256=otf.formula_observation_hash(value_observation),
                    observed_count=len(value_observation.values),
                    revision_after=value_observation.observed_revision,
                    calculation_state=value_observation.calculation_state.value,
                    calculation_trigger=value_observation.calculation_trigger.value,
                    dependency_scope=value_observation.dependency_scope,
                ),
            ),
        )
        return self._result("recalculate_grid", default)  # type: ignore[return-value]

    def bind_field(
        self,
        request: otf.FieldFormulaBindRequest[otc.Table],
    ) -> otf.FormulaExtensionResult[otf.FieldFormulaBinding[otc.Table]]:
        self.calls.append(("bind_field", request))
        default = otf.FormulaExtensionResult(
            value=self._field_binding(request.target),
            outcome=otf.FormulaOutcome.SUCCEEDED,
            commit=otf.FormulaCommitState.NOT_APPLICABLE,
            verification=otf.FormulaVerificationState.PASSED,
            receipts=(),
        )
        return self._result("bind_field", default)  # type: ignore[return-value]

    def read_field(
        self,
        request: otf.FieldFormulaReadRequest[otc.Table],
    ) -> otf.FormulaExtensionResult[otf.FieldFormulaObservation]:
        self.calls.append(("read_field", request))
        observation = self._field_observation(request)
        default = otf.FormulaExtensionResult(
            value=observation,
            outcome=otf.FormulaOutcome.SUCCEEDED,
            commit=otf.FormulaCommitState.NOT_APPLICABLE,
            verification=otf.FormulaVerificationState.PASSED,
            receipts=(
                otf.FormulaReceiptDetails(
                    target_kind="field",
                    table_mode="base",
                    target=request.target.table.uri.value,
                    selector=request.target.field.field_id or "fld-gross_margin",
                    capability=otf.FIELD_READ.to_reference(),
                    dialect=observation.expression.dialect,
                    observation_sha256=otf.formula_observation_hash(observation),
                    observed_count=1,
                    revision_after=observation.observed_revision,
                ),
            ),
        )
        return self._result("read_field", default)  # type: ignore[return-value]

    def set_field(
        self,
        request: otf.FieldFormulaSetRequest[otc.Table],
    ) -> otf.FormulaExtensionResult[otf.FormulaMutation]:
        self.calls.append(("set_field", request))
        observation = self._field_observation(
            request,
            expression=request.expression,
            revision=_formula_hash("field-set"),
        )
        mutation = otf.FormulaMutation(
            target_kind="field",
            affected_count=1,
            formula_observation=observation,
            revision_before=request.expected_revision,
            revision_after=_formula_hash("field-set-result"),
        )
        default = otf.FormulaExtensionResult(
            value=mutation,
            outcome=otf.FormulaOutcome.SUCCEEDED,
            commit=otf.FormulaCommitState.COMMITTED,
            verification=otf.FormulaVerificationState.PASSED,
            receipts=(
                otf.FormulaReceiptDetails.for_field_set(
                    target=request.target.table.uri.value,
                    selector=request.target.field.field_id or "fld-gross_margin",
                    capability=otf.FIELD_SET.to_reference(),
                    dialect=request.expression.dialect,
                    expression_sha256=request.expression.sha256,
                    observation_sha256=otf.formula_observation_hash(observation),
                    affected_count=1,
                    revision_before=request.expected_revision,
                    revision_after=mutation.revision_after,
                    mutation_atomicity=self.field_details.mutation_atomicity.value,
                    revision_enforcement=self.field_details.revision_enforcement.value,
                    verification="formula_text_readback",
                ),
            ),
        )
        return self._result("set_field", default)  # type: ignore[return-value]

    def read_field_values(
        self,
        request: otf.FieldFormulaValueReadRequest[otc.Table],
    ) -> otf.FormulaExtensionResult[otf.FieldFormulaValueObservation]:
        self.calls.append(("read_field_values", request))
        observation = otf.FieldFormulaValueObservation(
            table_uri=request.target.table.uri,
            field_id=request.target.field.field_id or "fld-gross_margin",
            field_name="gross_margin",
            values=(otf.FormulaRecordValue("rec-1", otf.FormulaValue.from_python(42)),),
            calculation_state=otf.CalculationState.PROVIDER_CURRENT,
            calculation_trigger=otf.CalculationTrigger.PROVIDER_READ,
            dependency_scope="provider_dynamic",
            observed_revision=_formula_hash("field-values"),
        )
        formula_observation = self._field_observation(
            otf.FieldFormulaReadRequest(target=request.target),
            revision=observation.observed_revision,
        )
        default = otf.FormulaExtensionResult(
            value=observation,
            outcome=otf.FormulaOutcome.SUCCEEDED,
            commit=otf.FormulaCommitState.NOT_APPLICABLE,
            verification=otf.FormulaVerificationState.PASSED,
            receipts=(
                otf.FormulaReceiptDetails.for_field_values_read(
                    target=request.target.table.uri.value,
                    selector=request.target.field.field_id or "fld-gross_margin",
                    capability=otf.FIELD_VALUES_READ.to_reference(),
                    dialect=formula_observation.expression.dialect,
                    observation_sha256=otf.formula_observation_hash(formula_observation),
                    value_observation_sha256=otf.formula_observation_hash(observation),
                    observed_count=len(observation.values),
                    revision_after=observation.observed_revision,
                    calculation_state=observation.calculation_state.value,
                    calculation_trigger=observation.calculation_trigger.value,
                    dependency_scope=observation.dependency_scope,
                ),
            ),
        )
        return self._result("read_field_values", default)  # type: ignore[return-value]

    def recalculate_field(
        self,
        request: otf.FieldFormulaRecalculateRequest[otc.Table],
    ) -> otf.FormulaExtensionResult[otf.RecalculationObservation]:
        self.calls.append(("recalculate_field", request))
        value_observation = otf.FieldFormulaValueObservation(
            table_uri=request.target.table.uri,
            field_id=request.target.field.field_id or "fld-gross_margin",
            field_name="gross_margin",
            values=(otf.FormulaRecordValue("rec-1", otf.FormulaValue.from_python(84)),),
            calculation_state=otf.CalculationState.PROVIDER_CURRENT,
            calculation_trigger=otf.CalculationTrigger.EXPLICIT_RECALCULATION,
            dependency_scope="provider_dynamic",
            observed_revision=_formula_hash("field-recalculate-values"),
        )
        default = otf.FormulaExtensionResult(
            value=otf.RecalculationObservation(
                target_kind="field",
                requested_scope=request.scope.value,
                effective_scope=request.scope.value,
                revision_before=request.expected_revision,
                revision_after=_formula_hash("field-recalculate"),
                provider_status="completed",
                calculation_state=otf.CalculationState.PROVIDER_CURRENT,
                verification="passed",
                value_observation=value_observation,
            ),
            outcome=otf.FormulaOutcome.SUCCEEDED,
            commit=otf.FormulaCommitState.COMMITTED,
            verification=otf.FormulaVerificationState.PASSED,
            receipts=(
                otf.FormulaReceiptDetails.for_field_values_read(
                    target=request.target.table.uri.value,
                    selector=request.target.field.field_id or "fld-gross_margin",
                    capability=otf.FIELD_RECALCULATE.to_reference(),
                    dialect=self.field_details.dialects[0],
                    observation_sha256=_formula_hash("field-recalculate-observation"),
                    value_observation_sha256=otf.formula_observation_hash(value_observation),
                    observed_count=len(value_observation.values),
                    revision_after=value_observation.observed_revision,
                    calculation_state=value_observation.calculation_state.value,
                    calculation_trigger=value_observation.calculation_trigger.value,
                    dependency_scope=value_observation.dependency_scope,
                ),
            ),
        )
        return self._result("recalculate_field", default)  # type: ignore[return-value]


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
    temporal_extension: FakeTemporalExtension = field(default_factory=FakeTemporalExtension)
    formula_extension: FakeFormulaExtension = field(default_factory=FakeFormulaExtension)
    open_mode: otc.TableMode = otc.TableMode.BASE_MODE

    def read_native_sql(self, request: ExecutionRequest) -> ArrowReadResult:
        self.calls.append(("read_native_sql", request.statement))
        table = self.frame.to_arrow()
        return ArrowReadResult(
            table=table,
            receipt=NeutralReceipt(
                connector=self.identity,
                capability=CapabilityIdentity("native.sql.query", "1.0"),
                operation_id="native-query-1",
                safe_uri=request.uri,
                mode=LegacyTableMode.BASE,
                source_revision="native-query-rev-1",
                schema_fingerprint="native-query-schema-1",
                content_fingerprint="native-query-content-1",
                coordinate_convention=BaseConvention(key_fields=("order_id",)),
                row_count=table.num_rows,
                batch_count=1,
            ),
        )

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.calls.append(("execute_sql", request.statement))
        return ExecutionResult(
            operation_id="native-execute-1",
            status="completed",
            affected_rows=2,
        )

    def open_table(self, address: object) -> otc.OperationResult[otc.TableBinding]:
        self.calls.append(("open_table", address))
        return otc.OperationResult(
            value=otc.TableBinding(
                uri=TableURI(self.table_uri),
                mode=self.open_mode,
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
    ) -> otc.OperationResult[ArrowTableCarrier]:
        self.calls.append(("read_table", {"limit": limit, "continuation": continuation}))
        frame = self.frame if limit is None else self.frame.head(limit)
        next_token = None
        if limit is not None and limit < self.frame.height and continuation is None:
            next_token = "page-2"
        return otc.OperationResult(
            value=ArrowTableCarrier(frame.to_arrow()),
            outcome=otc.Outcome.SUCCEEDED,
            commit=otc.CommitState.NOT_APPLICABLE,
            verification=otc.VerificationState.PASSED,
            receipts=(make_receipt("table.read", row_count=frame.height),),
            continuation=next_token,
        )

    def bind_sheet_range(
        self, source: otc.SheetRangeSource
    ) -> otc.OperationResult[otc.SheetRangeSource]:
        return otc.OperationResult(
            value=otc.SheetRangeSource(
                grid=source.grid,
                cell_range=source.cell_range,
                header=source.header,
                schema=source.schema or self.frame.schema,
                schema_policy=otc.SchemaPolicy.VALIDATE_DECLARED,
                observed_revision="range-rev-1",
            ),
            outcome=otc.Outcome.SUCCEEDED,
            commit=otc.CommitState.NOT_APPLICABLE,
            verification=otc.VerificationState.PASSED,
            receipts=(make_receipt("table.range.bind"),),
        )

    def read_sheet_range(
        self, source: otc.SheetRangeSource
    ) -> otc.OperationResult[ArrowTableCarrier]:
        del source
        return otc.OperationResult(
            value=ArrowTableCarrier(self.frame.to_arrow()),
            outcome=otc.Outcome.SUCCEEDED,
            commit=otc.CommitState.NOT_APPLICABLE,
            verification=otc.VerificationState.PASSED,
            receipts=(make_receipt("table.range.read", row_count=self.frame.height),),
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
                mode=self.open_mode,
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

    def temporal_extension_for(self, binding: otc.TableBinding, descriptor):
        self.calls.append(("temporal_extension_for", binding.uri.value))
        self.temporal_extension.target_uri = binding.uri.value
        self.temporal_extension.source.descriptor = descriptor
        return self.temporal_extension

    def formula_extension_for(self):
        self.calls.append(("formula_extension_for", self.table_uri))
        return self.formula_extension


class FakeLegacyAdapter:
    identity = ConnectorIdentity("legacy", "0.1.0", "1.0")
    schemes = ("legacy",)
    hosts: tuple[str, ...] = ()
    capabilities = (CapabilityIdentity("table.write", "1.0"),)
    modes = (LegacyTableMode.BASE,)

    def __init__(self) -> None:
        self.formula_extension = FakeFormulaExtension()

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

    def formula_extension_for(self):
        return self.formula_extension


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
