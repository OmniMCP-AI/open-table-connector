"""Reusable formula conformance assertions."""

from __future__ import annotations

import logging
import re
import warnings
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from typing import Any

import open_table_connector.formulas as otf
from open_table_connector.contract import CapabilityIdentity

_FORMULA_CAPABILITIES = {capability.to_reference(): capability for capability in otf.ALL_CAPABILITIES}
_FORBIDDEN_KEYS = {
    "credential",
    "expression",
    "formula",
    "password",
    "secret",
    "token",
    "value",
    "values",
}


@dataclass(frozen=True, slots=True)
class GridFormulaCase:
    formula_range: str
    literal_range: str
    set_expression: otf.FormulaExpression
    conflicting_expression: otf.FormulaExpression
    expected_after_set: otf.GridFormulaObservation
    expected_literal_read: otf.GridFormulaObservation
    expected_values: otf.GridFormulaValueObservation | None
    recalculation_scope: otf.GridRecalculationScope | None
    expected_recalculation: otf.RecalculationObservation | None

    def __post_init__(self) -> None:
        if not isinstance(self.set_expression, otf.FormulaExpression):
            raise TypeError("set_expression must be a FormulaExpression")
        if self.conflicting_expression.dialect != self.set_expression.dialect:
            raise ValueError("conflicting_expression dialect must match set_expression")
        if self.expected_after_set.requested_range != self.formula_range:
            raise ValueError("expected_after_set range must match formula_range")
        if self.expected_literal_read.requested_range != self.literal_range:
            raise ValueError("expected_literal_read range must match literal_range")
        if self.expected_values is None and self.expected_recalculation is not None:
            raise ValueError("expected_values is required when expected_recalculation is provided")


@dataclass(frozen=True, slots=True)
class FieldFormulaCase:
    set_expression: otf.FormulaExpression
    conflicting_expression: otf.FormulaExpression
    expected_after_set: otf.FieldFormulaObservation
    expected_values: otf.FieldFormulaValueObservation | None
    recalculation_scope: otf.FieldRecalculationScope | None
    expected_recalculation: otf.RecalculationObservation | None

    def __post_init__(self) -> None:
        if not isinstance(self.set_expression, otf.FormulaExpression):
            raise TypeError("set_expression must be a FormulaExpression")
        if self.conflicting_expression.dialect != self.set_expression.dialect:
            raise ValueError("conflicting_expression dialect must match set_expression")
        if self.expected_values is None and self.expected_recalculation is not None:
            raise ValueError("expected_values is required when expected_recalculation is provided")


@dataclass(frozen=True, slots=True)
class FormulaProviderCase:
    provider_id: str
    target_kind: str
    dialect: str
    static_capabilities: tuple[CapabilityIdentity, ...]
    extension_factory: Callable[[], object]
    grid_target_factory: Callable[[], otf.GridFormulaTarget] | None = None
    field_target_factory: Callable[[], otf.FieldFormulaTarget[Any]] | None = None
    grid_case: GridFormulaCase | None = None
    field_case: FieldFormulaCase | None = None
    supports_independent_sessions: bool = True
    configured_live_evidence: str | None = None
    security_markers: tuple[str, ...] = ()
    security_expression: otf.FormulaExpression | None = None
    security_probe_values: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.provider_id, str) or not self.provider_id.strip():
            raise TypeError("provider_id must be a non-empty string")
        if self.target_kind not in {"grid", "field"}:
            raise ValueError("target_kind must be 'grid' or 'field'")
        if self.dialect not in otf.FORMULA_DIALECTS:
            raise ValueError("dialect must be a closed formula dialect")
        if not callable(self.extension_factory):
            raise TypeError("extension_factory must be callable")
        capabilities = tuple(
            capability
            if isinstance(capability, CapabilityIdentity)
            else CapabilityIdentity.from_wire(capability)
            for capability in self.static_capabilities
        )
        references = tuple(capability.to_reference() for capability in capabilities)
        if len(set(references)) != len(references):
            raise ValueError("static_capabilities must not contain duplicates")
        if any(reference not in _FORMULA_CAPABILITIES for reference in references):
            raise ValueError("static_capabilities must belong to the closed Formula capability set")
        prefix = f"formula.{self.target_kind}."
        if any(not capability.capability_id.startswith(prefix) for capability in capabilities):
            raise ValueError("static_capabilities must match target_kind")
        object.__setattr__(self, "static_capabilities", capabilities)
        if self.target_kind == "grid":
            if self.grid_target_factory is None or self.grid_case is None:
                raise ValueError("grid cases require grid_target_factory and grid_case")
            if self.field_target_factory is not None or self.field_case is not None:
                raise ValueError("grid cases must not define field targets")
            if self.grid_case.set_expression.dialect != self.dialect:
                raise ValueError("grid_case dialect must match FormulaProviderCase dialect")
        else:
            if self.field_target_factory is None or self.field_case is None:
                raise ValueError("field cases require field_target_factory and field_case")
            if self.grid_target_factory is not None or self.grid_case is not None:
                raise ValueError("field cases must not define grid targets")
            if self.field_case.set_expression.dialect != self.dialect:
                raise ValueError("field_case dialect must match FormulaProviderCase dialect")
        if self.configured_live_evidence is not None and not self.configured_live_evidence.strip():
            raise ValueError("configured_live_evidence must be non-empty when provided")
        if self.security_expression is not None and self.security_expression.dialect != self.dialect:
            raise ValueError("security_expression dialect must match FormulaProviderCase dialect")
        object.__setattr__(self, "security_markers", tuple(marker for marker in self.security_markers if marker))
        object.__setattr__(self, "security_probe_values", tuple(value for value in self.security_probe_values if value))


@dataclass(frozen=True, slots=True)
class FormulaSecurityProbe:
    result: otf.FormulaExtensionResult[Any]
    warnings: tuple[str, ...]
    logs: tuple[str, ...]
    reprs: tuple[object, ...]
    ledger_snapshots: tuple[object, ...]
    operation_ids: tuple[object, ...]

    @property
    def mutation(self) -> otf.FormulaMutation | None:
        return self.result.value if isinstance(self.result.value, otf.FormulaMutation) else None


def load_formula_cases(*groups: FormulaProviderCase | Iterable[FormulaProviderCase]) -> tuple[FormulaProviderCase, ...]:
    """Flatten and validate formula conformance cases."""

    loaded: list[FormulaProviderCase] = []
    seen: set[tuple[str, str, str]] = set()
    for group in groups:
        cases = (group,) if isinstance(group, FormulaProviderCase) else tuple(group)
        for case in cases:
            if not isinstance(case, FormulaProviderCase):
                raise TypeError("load_formula_cases expects FormulaProviderCase instances")
            key = (case.provider_id, case.target_kind, case.dialect)
            if key in seen:
                raise ValueError(
                    "duplicate formula provider case: "
                    f"{case.provider_id}[{case.target_kind}:{case.dialect}]"
                )
            seen.add(key)
            loaded.append(case)
    return tuple(loaded)


def grid_formula_case_params(
    cases: Iterable[FormulaProviderCase],
    *,
    capability: CapabilityIdentity | None = None,
    configured_live_only: bool = False,
) -> tuple[Any, ...]:
    """Build pytest params for grid cases, optionally filtered by capability or live evidence."""

    return _case_params(
        load_formula_cases(cases),
        target_kind="grid",
        capability=capability,
        configured_live_only=configured_live_only,
    )


def field_formula_case_params(
    cases: Iterable[FormulaProviderCase],
    *,
    capability: CapabilityIdentity | None = None,
    configured_live_only: bool = False,
) -> tuple[Any, ...]:
    """Build pytest params for field cases, optionally filtered by capability or live evidence."""

    return _case_params(
        load_formula_cases(cases),
        target_kind="field",
        capability=capability,
        configured_live_only=configured_live_only,
    )


def _case_params(
    cases: tuple[FormulaProviderCase, ...],
    *,
    target_kind: str,
    capability: CapabilityIdentity | None,
    configured_live_only: bool,
) -> tuple[Any, ...]:
    import pytest

    filtered: list[Any] = []
    for case in cases:
        if case.target_kind != target_kind:
            continue
        if configured_live_only and case.configured_live_evidence is None:
            continue
        if capability is not None and capability not in case.static_capabilities:
            continue
        filtered.append(pytest.param(case, id=f"{case.provider_id}[{target_kind}:{case.dialect}]"))
    return tuple(filtered)


def assert_formula_receipt_safe(
    receipts: otf.FormulaReceiptDetails | Sequence[object],
    *,
    forbidden_texts: Iterable[str] = (),
) -> None:
    """Assert that safe receipt evidence does not leak raw formulas or marker strings."""

    forbidden = tuple(text for text in forbidden_texts if text)
    values = (receipts,) if isinstance(receipts, otf.FormulaReceiptDetails) else tuple(receipts)
    for receipt in values:
        payload = _materialize(receipt)
        _assert_safe_surface(payload, forbidden, context="receipt payload")
        _assert_safe_surface(repr(receipt), forbidden, context="receipt repr")
        if isinstance(receipt, otf.FormulaReceiptDetails):
            assert otf.FormulaReceiptDetails.from_wire(receipt.to_wire()) == receipt


def assert_formula_security_safe(case: FormulaProviderCase) -> FormulaSecurityProbe:
    """Probe one provider case and reject formula text in every safe evidence channel."""

    if case.security_expression is None:
        raise ValueError(f"{case.provider_id}: security_expression is required for a security probe")
    set_capability = otf.GRID_SET if case.target_kind == "grid" else otf.FIELD_SET
    if set_capability not in case.static_capabilities:
        raise ValueError(
            f"{case.provider_id}: security probe requires advertised "
            f"{set_capability.to_reference()} capability"
        )
    extension = case.extension_factory()
    target_factory = case.grid_target_factory if case.target_kind == "grid" else case.field_target_factory
    if target_factory is None:
        raise AssertionError(f"{case.provider_id}: security probe target factory is missing")
    target = target_factory()
    forbidden_texts = _case_forbidden_texts(case)
    if case.target_kind == "grid":
        binding_result = extension.bind_grid(otf.GridFormulaBindRequest(target))
    else:
        binding_result = extension.bind_field(otf.FieldFormulaBindRequest(target))
    binding = _require_success(
        binding_result,
        otf.GridFormulaBinding if case.target_kind == "grid" else otf.FieldFormulaBinding,
        context=f"{case.provider_id}: security bind",
        forbidden_texts=forbidden_texts,
    )

    log_capture = _LogCapture()
    root_logger = logging.getLogger()
    root_logger.addHandler(log_capture)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            if case.target_kind == "grid":
                assert case.grid_case is not None
                result = extension.set_grid(
                    otf.GridFormulaSetRequest(
                        target=binding.target,
                        cell_range=case.grid_case.formula_range,
                        expression=case.security_expression,
                        expected_revision=binding.observed_revision,
                        idempotency_key=f"formula-security-{case.provider_id}-{case.dialect}",
                    )
                )
            else:
                result = extension.set_field(
                    otf.FieldFormulaSetRequest(
                        target=binding.target,
                        expression=case.security_expression,
                        expected_revision=binding.observed_revision,
                        idempotency_key=f"formula-security-{case.provider_id}-{case.dialect}",
                    )
                )
            warning_texts = tuple(str(item.message) for item in caught)
    finally:
        root_logger.removeHandler(log_capture)

    normalized = _require_result(
        result,
        context=f"{case.provider_id}: security probe",
        forbidden_texts=forbidden_texts,
    )
    _assert_security_result_safe(
        normalized,
        forbidden_texts=forbidden_texts,
        context=f"{case.provider_id}: security probe",
    )
    probe = FormulaSecurityProbe(
        result=normalized,
        warnings=warning_texts,
        logs=tuple(log_capture.messages),
        reprs=tuple(getattr(extension, "reprs", ())),
        ledger_snapshots=tuple(getattr(extension, "ledger_snapshots", ())),
        operation_ids=tuple(getattr(extension, "operation_ids", ())),
    )
    _assert_safe_surface(probe.warnings, forbidden_texts, context="security warnings")
    _assert_safe_surface(probe.logs, forbidden_texts, context="security logs")
    _assert_safe_surface(probe.reprs, forbidden_texts, context="security reprs")
    _assert_safe_surface(probe.ledger_snapshots, forbidden_texts, context="security ledger")
    _assert_safe_surface(probe.operation_ids, forbidden_texts, context="security operation ids")
    return probe


def assert_grid_formula_conformance(case: FormulaProviderCase) -> None:
    """Run the shared grid-formula conformance assertions for one provider case."""

    _require_target_kind(case, "grid")
    extension = case.extension_factory()
    target = case.grid_target_factory()
    forbidden_texts = _case_forbidden_texts(case)
    bind = _require_success(
        extension.bind_grid(otf.GridFormulaBindRequest(target)),
        otf.GridFormulaBinding,
        context=f"{case.provider_id}: bind_grid",
        forbidden_texts=forbidden_texts,
    )
    _assert_capability_set(case, bind.capabilities)
    assert case.grid_case is not None
    if otf.GRID_READ in case.static_capabilities:
        literal = _require_success(
            extension.read_grid(
                otf.GridFormulaReadRequest(bind.target, case.grid_case.literal_range)
            ),
            otf.GridFormulaObservation,
            context=f"{case.provider_id}: read_grid literal",
            forbidden_texts=forbidden_texts,
        )
        assert literal == case.grid_case.expected_literal_read, (
            f"{case.provider_id}: literal strings beginning with leading = must not be inferred "
            "as formulas"
        )
    if otf.GRID_SET in case.static_capabilities:
        set_result = _require_result(
            extension.set_grid(
                otf.GridFormulaSetRequest(
                    target=bind.target,
                    cell_range=case.grid_case.formula_range,
                    expression=case.grid_case.set_expression,
                    expected_revision=bind.observed_revision,
                    idempotency_key="formula-conformance-grid",
                )
            ),
            context=f"{case.provider_id}: set_grid",
            forbidden_texts=forbidden_texts,
        )
        mutation = _require_success(
            set_result,
            otf.FormulaMutation,
            context=f"{case.provider_id}: set_grid",
            forbidden_texts=forbidden_texts,
        )
        assert mutation.formula_observation == case.grid_case.expected_after_set, (
            f"{case.provider_id}: grid set must follow top-left copy-fill semantics instead of "
            "exact-text broadcast"
        )
        assert mutation.revision_after == mutation.formula_observation.observed_revision, (
            f"{case.provider_id}: grid mutation revision_after must match formula observation"
        )
        if bind.observed_revision is not None:
            assert mutation.revision_before == bind.observed_revision, (
                f"{case.provider_id}: grid mutation revision_before must reflect the bound revision"
            )
        _assert_grid_set_receipts(
            mutation,
            case,
            _receipts_with_capability(
                set_result.receipts,
                otf.GRID_SET.to_reference(),
            ),
        )
        if otf.GRID_READ in case.static_capabilities:
            readback_extension = case.extension_factory() if case.supports_independent_sessions else extension
            readback_binding = bind
            if case.supports_independent_sessions:
                readback_binding = _require_success(
                    readback_extension.bind_grid(otf.GridFormulaBindRequest(case.grid_target_factory())),
                    otf.GridFormulaBinding,
                    context=f"{case.provider_id}: bind_grid readback",
                    forbidden_texts=forbidden_texts,
                )
            readback = _require_success(
                readback_extension.read_grid(
                    otf.GridFormulaReadRequest(readback_binding.target, case.grid_case.formula_range)
                ),
                otf.GridFormulaObservation,
                context=f"{case.provider_id}: read_grid readback",
                forbidden_texts=forbidden_texts,
            )
            assert readback == mutation.formula_observation, (
                f"{case.provider_id}: independent readback must match the committed formula text"
            )
        if bind.capabilities.details.revision_enforcement is not otf.RevisionEnforcement.UNAVAILABLE:
            stale = _require_result(
                extension.set_grid(
                    otf.GridFormulaSetRequest(
                        target=bind.target,
                        cell_range=case.grid_case.formula_range,
                        expression=case.grid_case.conflicting_expression,
                        expected_revision=bind.observed_revision,
                        idempotency_key="formula-conformance-grid-stale",
                    )
                ),
                context=f"{case.provider_id}: stale grid revision probe",
                forbidden_texts=forbidden_texts,
            )
            _assert_error_code(
                stale,
                otf.FormulaErrorCode.STALE_REVISION,
                context=f"{case.provider_id}: stale revision was accepted",
            )
        if bind.capabilities.details.idempotency_strength in {
            otf.IdempotencyStrength.PROVIDER,
            otf.IdempotencyStrength.HOST_LEDGER,
            otf.IdempotencyStrength.RECONCILED,
        }:
            conflict = _require_result(
                extension.set_grid(
                    otf.GridFormulaSetRequest(
                        target=bind.target,
                        cell_range=case.grid_case.formula_range,
                        expression=case.grid_case.conflicting_expression,
                        expected_revision=mutation.revision_after,
                        idempotency_key="formula-conformance-grid",
                    )
                ),
                context=f"{case.provider_id}: grid idempotency conflict probe",
                forbidden_texts=forbidden_texts,
            )
            _assert_error_code(
                conflict,
                otf.FormulaErrorCode.IDEMPOTENCY_CONFLICT,
                context=f"{case.provider_id}: idempotency conflict must reject same-key different-payload reuse",
            )
    if otf.GRID_VALUES_READ in case.static_capabilities:
        value_result = _require_result(
            extension.read_grid_values(
                otf.GridFormulaValueReadRequest(bind.target, case.grid_case.formula_range)
            ),
            context=f"{case.provider_id}: read_grid_values",
            forbidden_texts=forbidden_texts,
        )
        if not isinstance(value_result.value, otf.GridFormulaValueObservation):
            dependency_scope = getattr(value_result.value, "dependency_scope", None)
            raise AssertionError(
                f"{case.provider_id}: grid value observations must declare "
                f"dependency_scope=provider_dynamic, got {dependency_scope!r}"
            )
        values = _require_success(
            value_result,
            otf.GridFormulaValueObservation,
            context=f"{case.provider_id}: read_grid_values",
            forbidden_texts=forbidden_texts,
        )
        assert values == case.grid_case.expected_values, (
            f"{case.provider_id}: grid value observations must keep dependency_scope=provider_dynamic"
        )
        _assert_value_receipts(
            value_result.receipts,
            expected_capability=otf.GRID_VALUES_READ.to_reference(),
        )
    if otf.GRID_RECALCULATE in case.static_capabilities:
        recalculation = _require_success(
            extension.recalculate_grid(
                otf.GridFormulaRecalculateRequest(
                    target=bind.target,
                    scope=case.grid_case.recalculation_scope,
                    cell_range=case.grid_case.formula_range,
                    expected_revision=case.grid_case.expected_after_set.observed_revision,
                    idempotency_key="formula-conformance-grid-recalculate",
                )
            ),
            otf.RecalculationObservation,
            context=f"{case.provider_id}: recalculate_grid",
            forbidden_texts=forbidden_texts,
        )
        assert recalculation == case.grid_case.expected_recalculation


def assert_field_formula_conformance(case: FormulaProviderCase) -> None:
    """Run the shared field-formula conformance assertions for one provider case."""

    _require_target_kind(case, "field")
    extension = case.extension_factory()
    target = case.field_target_factory()
    forbidden_texts = _case_forbidden_texts(case)
    bind = _require_success(
        extension.bind_field(otf.FieldFormulaBindRequest(target)),
        otf.FieldFormulaBinding,
        context=f"{case.provider_id}: bind_field",
        forbidden_texts=forbidden_texts,
    )
    _assert_capability_set(case, bind.capabilities)
    assert case.field_case is not None
    if otf.FIELD_READ in case.static_capabilities:
        initial = _require_success(
            extension.read_field(otf.FieldFormulaReadRequest(bind.target)),
            otf.FieldFormulaObservation,
            context=f"{case.provider_id}: read_field",
            forbidden_texts=forbidden_texts,
        )
        assert initial.field_id == bind.target.field.field_id, (
            f"{case.provider_id}: field read must resolve to the stable bound field id"
        )
    if otf.FIELD_SET in case.static_capabilities:
        mutation = _require_success(
            extension.set_field(
                otf.FieldFormulaSetRequest(
                    target=bind.target,
                    expression=case.field_case.set_expression,
                    expected_revision=bind.observed_revision,
                    idempotency_key="formula-conformance-field",
                )
            ),
            otf.FormulaMutation,
            context=f"{case.provider_id}: set_field",
            forbidden_texts=forbidden_texts,
        )
        assert mutation.formula_observation == case.field_case.expected_after_set, (
            f"{case.provider_id}: field set must preserve the stable field_id instead of converting "
            "the field"
        )
        assert mutation.formula_observation.field_id == bind.target.field.field_id, (
            f"{case.provider_id}: field mutations must preserve the stable field_id"
        )
        assert mutation.revision_after == mutation.formula_observation.observed_revision
        if otf.FIELD_READ in case.static_capabilities:
            readback_extension = case.extension_factory() if case.supports_independent_sessions else extension
            readback_binding = bind
            if case.supports_independent_sessions:
                readback_binding = _require_success(
                    readback_extension.bind_field(otf.FieldFormulaBindRequest(case.field_target_factory())),
                    otf.FieldFormulaBinding,
                    context=f"{case.provider_id}: bind_field readback",
                    forbidden_texts=forbidden_texts,
                )
            readback = _require_success(
                readback_extension.read_field(otf.FieldFormulaReadRequest(readback_binding.target)),
                otf.FieldFormulaObservation,
                context=f"{case.provider_id}: read_field readback",
                forbidden_texts=forbidden_texts,
            )
            assert readback == mutation.formula_observation, (
                f"{case.provider_id}: independent field readback must match the committed formula"
            )
        if bind.capabilities.details.revision_enforcement is not otf.RevisionEnforcement.UNAVAILABLE:
            stale = _require_result(
                extension.set_field(
                    otf.FieldFormulaSetRequest(
                        target=bind.target,
                        expression=case.field_case.conflicting_expression,
                        expected_revision=bind.observed_revision,
                        idempotency_key="formula-conformance-field-stale",
                    )
                ),
                context=f"{case.provider_id}: stale field revision probe",
                forbidden_texts=forbidden_texts,
            )
            _assert_error_code(
                stale,
                otf.FormulaErrorCode.STALE_REVISION,
                context=f"{case.provider_id}: stale revision was accepted",
            )
        if bind.capabilities.details.idempotency_strength in {
            otf.IdempotencyStrength.PROVIDER,
            otf.IdempotencyStrength.HOST_LEDGER,
            otf.IdempotencyStrength.RECONCILED,
        }:
            conflict = _require_result(
                extension.set_field(
                    otf.FieldFormulaSetRequest(
                        target=bind.target,
                        expression=case.field_case.conflicting_expression,
                        expected_revision=mutation.revision_after,
                        idempotency_key="formula-conformance-field",
                    )
                ),
                context=f"{case.provider_id}: field idempotency conflict probe",
                forbidden_texts=forbidden_texts,
            )
            _assert_error_code(
                conflict,
                otf.FormulaErrorCode.IDEMPOTENCY_CONFLICT,
                context=f"{case.provider_id}: idempotency conflict must reject same-key different-payload reuse",
            )
    if otf.FIELD_VALUES_READ in case.static_capabilities:
        values = _require_success(
            extension.read_field_values(otf.FieldFormulaValueReadRequest(bind.target)),
            otf.FieldFormulaValueObservation,
            context=f"{case.provider_id}: read_field_values",
            forbidden_texts=forbidden_texts,
        )
        assert values == case.field_case.expected_values
    if otf.FIELD_RECALCULATE in case.static_capabilities:
        recalculation = _require_success(
            extension.recalculate_field(
                otf.FieldFormulaRecalculateRequest(
                    target=bind.target,
                    scope=case.field_case.recalculation_scope,
                    expected_revision=case.field_case.expected_after_set.observed_revision,
                    idempotency_key="formula-conformance-field-recalculate",
                )
            ),
            otf.RecalculationObservation,
            context=f"{case.provider_id}: recalculate_field",
            forbidden_texts=forbidden_texts,
        )
        assert recalculation == case.field_case.expected_recalculation


class _LogCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.NOTSET)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def _case_forbidden_texts(case: FormulaProviderCase) -> tuple[str, ...]:
    texts: list[str] = [*case.security_markers, *case.security_probe_values]
    if case.security_expression is not None:
        texts.append(case.security_expression.text)
    if case.grid_case is not None:
        texts.extend(
            (
                case.grid_case.set_expression.text,
                case.grid_case.conflicting_expression.text,
            )
        )
    if case.field_case is not None:
        texts.extend(
            (
                case.field_case.set_expression.text,
                case.field_case.conflicting_expression.text,
            )
        )
    return tuple(dict.fromkeys(text for text in texts if text))


def _require_target_kind(case: FormulaProviderCase, expected: str) -> None:
    if case.target_kind != expected:
        raise TypeError(f"expected a {expected} FormulaProviderCase")


def _assert_capability_set(
    case: FormulaProviderCase,
    capabilities: otf.FormulaCapabilitySet,
) -> None:
    actual = {capability.to_reference() for capability in capabilities.capabilities}
    expected = {capability.to_reference() for capability in case.static_capabilities}
    unexpected = actual.difference(expected)
    if unexpected:
        unexpected_text = ", ".join(sorted(unexpected))
        raise AssertionError(
            f"{case.provider_id}: effective capability details add an identity: {unexpected_text}"
        )
    missing = expected.difference(actual)
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise AssertionError(
            f"{case.provider_id}: bound capability set is missing advertised identities: {missing_text}"
        )
    assert capabilities.details.target_kind == case.target_kind
    assert case.dialect in capabilities.details.dialects


def _require_result(
    result: object,
    *,
    context: str,
    forbidden_texts: Iterable[str],
) -> otf.FormulaExtensionResult[Any]:
    if not isinstance(result, otf.FormulaExtensionResult):
        raise AssertionError(f"{context}: provider returned {type(result).__name__}, not FormulaExtensionResult")
    if result.error is not None:
        _assert_safe_surface(result.error.to_wire(), tuple(forbidden_texts), context=f"{context} error")
        _assert_safe_surface(repr(result.error), tuple(forbidden_texts), context=f"{context} error repr")
    assert_formula_receipt_safe(result.receipts, forbidden_texts=forbidden_texts)
    return result


def _assert_security_result_safe(
    result: otf.FormulaExtensionResult[Any],
    *,
    forbidden_texts: Iterable[str],
    context: str,
) -> None:
    forbidden = tuple(forbidden_texts)
    value = result.value
    result_repr = repr(result)
    if value is None:
        _assert_safe_surface(result_repr, forbidden, context=f"{context} result repr")
        return

    value_repr = repr(value)
    result_without_value = result_repr.replace(value_repr, "<typed formula value>", 1)
    _assert_safe_surface(result_without_value, forbidden, context=f"{context} result repr")
    allowed_formula_texts = _typed_formula_texts(value)
    for formula_text in allowed_formula_texts:
        value_repr = value_repr.replace(repr(formula_text), "<typed formula text>")
        value_repr = value_repr.replace(formula_text, "<typed formula text>")
    _assert_safe_surface(value_repr, forbidden, context=f"{context} value repr")


def _typed_formula_texts(value: object) -> tuple[str, ...]:
    if isinstance(value, otf.FormulaMutation):
        value = value.formula_observation
    if isinstance(value, otf.GridFormulaObservation):
        return tuple(cell.expression.text for cell in value.formulas)
    if isinstance(value, otf.FieldFormulaObservation):
        return (value.expression.text,)
    return ()


def _require_success(
    result: object,
    expected_type: type[Any],
    *,
    context: str,
    forbidden_texts: Iterable[str],
) -> Any:
    normalized = _require_result(result, context=context, forbidden_texts=forbidden_texts)
    if normalized.error is not None and normalized.error.code is otf.FormulaErrorCode.UNSUPPORTED_CAPABILITY:
        raise AssertionError(f"{context}: unsupported advertised capability returned UNSUPPORTED_CAPABILITY")
    if normalized.error is not None:
        raise AssertionError(f"{context}: unexpected formula error {normalized.error.code.value}")
    if normalized.value is None:
        raise AssertionError(f"{context}: missing operation value")
    if not isinstance(normalized.value, expected_type):
        raise AssertionError(
            f"{context}: expected {expected_type.__name__}, got {type(normalized.value).__name__}"
        )
    return normalized.value


def _assert_error_code(
    result: otf.FormulaExtensionResult[Any],
    expected_code: otf.FormulaErrorCode,
    *,
    context: str,
) -> None:
    if result.error is None:
        raise AssertionError(f"{context}: expected {expected_code.value}, but the operation succeeded")
    if result.error.code is not expected_code:
        raise AssertionError(
            f"{context}: expected {expected_code.value}, got {result.error.code.value}"
        )


def _receipts_with_capability(
    receipts: Sequence[object],
    capability: str,
) -> tuple[otf.FormulaReceiptDetails, ...]:
    return tuple(
        receipt
        for receipt in receipts
        if isinstance(receipt, otf.FormulaReceiptDetails) and receipt.capability == capability
    )


def _assert_grid_set_receipts(
    mutation: otf.FormulaMutation,
    case: FormulaProviderCase,
    receipts: Sequence[otf.FormulaReceiptDetails],
) -> None:
    if not receipts:
        raise AssertionError(f"{case.provider_id}: grid set must emit a FormulaReceiptDetails receipt")
    for receipt in receipts:
        assert receipt.copy_fill_policy == "top_left", (
            f"{case.provider_id}: grid set receipts must declare top_left copy-fill"
        )
        assert receipt.affected_count == mutation.affected_count
        assert receipt.revision_after == mutation.revision_after
        assert receipt.verification == "formula_text_readback"
        assert receipt.value_observation_sha256 is None
        assert receipt.calculation_state is None
        assert receipt.calculation_trigger is None
        assert receipt.dependency_scope is None


def _assert_value_receipts(
    receipts: Sequence[object],
    *,
    expected_capability: str,
) -> None:
    typed = _receipts_with_capability(receipts, expected_capability)
    if not typed:
        raise AssertionError("formula value reads must emit a typed receipt")
    for receipt in typed:
        assert receipt.calculation_state is not None
        assert receipt.calculation_trigger is not None
        assert receipt.dependency_scope == "provider_dynamic"


def _materialize(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return {str(key): _materialize(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not _is_scalar(value):
        return [_materialize(item) for item in value]
    if isinstance(value, otf.FormulaReceiptDetails):
        return value.to_wire()
    if hasattr(value, "to_wire") and callable(value.to_wire):
        return _materialize(value.to_wire())
    if is_dataclass(value):
        return {field.name: _materialize(getattr(value, field.name)) for field in fields(value)}
    if hasattr(value, "__dict__"):
        return {name: _materialize(item) for name, item in vars(value).items()}
    return value


def _assert_safe_surface(
    value: object,
    forbidden_texts: Sequence[str],
    *,
    context: str,
) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            if key_text.casefold() in _FORBIDDEN_KEYS:
                raise AssertionError(f"{context}: forbidden field name {key_text!r}")
            _assert_safe_surface(item, forbidden_texts, context=f"{context}.{key_text}")
        return
    if isinstance(value, Sequence) and not _is_scalar(value):
        for index, item in enumerate(value):
            _assert_safe_surface(item, forbidden_texts, context=f"{context}[{index}]")
        return
    if isinstance(value, str):
        if value.lstrip().startswith("="):
            raise AssertionError(f"{context}: raw formula text leaked into a safe surface")
        casefold = value.casefold()
        if "http://" in casefold or "https://" in casefold:
            raise AssertionError(f"{context}: URL marker leaked into a safe surface")
        for marker in forbidden_texts:
            normalized_value = re.sub(r"\s+", "", casefold)
            normalized_marker = re.sub(r"\s+", "", marker.casefold())
            if marker in value or marker.casefold() in casefold or normalized_marker in normalized_value:
                raise AssertionError(f"{context}: receipt contains forbidden formula marker")
        return
    materialized = _materialize(value)
    if materialized is not value:
        _assert_safe_surface(materialized, forbidden_texts, context=context)


def _is_scalar(value: object) -> bool:
    return isinstance(value, (str, bytes, bytearray))


__all__ = [
    "FieldFormulaCase",
    "FormulaSecurityProbe",
    "FormulaProviderCase",
    "GridFormulaCase",
    "assert_field_formula_conformance",
    "assert_formula_receipt_safe",
    "assert_formula_security_safe",
    "assert_grid_formula_conformance",
    "field_formula_case_params",
    "grid_formula_case_params",
    "load_formula_cases",
]
