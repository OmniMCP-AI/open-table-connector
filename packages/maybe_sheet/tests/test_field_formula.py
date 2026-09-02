from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import open_table_connector.formulas as otf
from open_table_connector.contract import TableMode, TableURI
from open_table_connector.maybe_sheet.field_formula import MaybeSheetFieldFormulaExtension

HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64


@dataclass
class BoundTable:
    _binding: Any


def table() -> BoundTable:
    return BoundTable(
        type(
            "Binding",
            (),
            {
                "uri": TableURI("maybe://workspace/R_orders"),
                "mode": TableMode.BASE,
            },
        )()
    )


def envelope(operation: str, result: dict[str, Any], *, target_kind: str = "base") -> dict[str, Any]:
    return {
        "contract_version": "1.0",
        "ok": True,
        "operation": operation,
        "target": {"kind": target_kind},
        "warnings": [],
        "request_id": "request-1",
        "result": result,
        "verification": {"status": "passed", "checks": ["provider"]},
        "trace": None,
    }


def metadata_result(
    *,
    expression: str = "price - cost",
    revision: str = HASH_A,
    target_kind: str = "base",
    field_type: str = "formula",
) -> dict[str, Any]:
    return {
        "target_kind": target_kind,
        "table_id": "tbl-orders",
        "fields": [
            {
                "id": "fld-gross-margin",
                "name": "gross_margin",
                "type": field_type,
                "result_type": "number",
                "property": {
                    "formula_expression": expression,
                    "format": "currency",
                    "precision": 2,
                },
                "required": False,
            }
        ],
        "revision": revision,
        "recalculation_scopes": ["field", "table"],
        "calculation_states": ["provider_current", "unknown"],
        "mutation_atomicity": "atomic",
        "revision_enforcement": "checked",
        "idempotency": "provider",
    }


class RecordingProcess:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[tuple[str, ...], dict[str, Any]]] = []

    def run(self, argv, *, credentials=None, stdin=None, timeout=None):
        self.calls.append(
            (
                tuple(argv),
                {"credentials": credentials, "stdin": stdin, "timeout": timeout},
            )
        )
        if not self.responses:
            raise AssertionError("unexpected process call")
        return self.responses.pop(0)


def _bind(extension: MaybeSheetFieldFormulaExtension, process: RecordingProcess):
    result = extension.bind_field(otf.FieldFormulaBindRequest(otf.FieldFormulaTarget(table(), otf.FieldRef(name="gross_margin"))))
    assert result.outcome is otf.FormulaOutcome.SUCCEEDED
    assert result.value is not None
    return result.value


def test_bind_field_uses_base_formula_command_and_stable_field_identity() -> None:
    process = RecordingProcess([envelope("formula.read", metadata_result())])
    extension = MaybeSheetFieldFormulaExtension(process, {"access_token": "token"}, timeout=13)

    binding = _bind(extension, process)

    assert binding.target.table is not None
    assert binding.target.field == otf.FieldRef(field_id="fld-gross-margin")
    assert binding.capabilities.details.dialects == (otf.MAYBE_BASE,)
    assert binding.capabilities.details.max_expression_bytes == 64 * 1024
    assert binding.capabilities.details.recalculation_scopes == ("field", "table")
    assert binding.capabilities.details.idempotency_strength is otf.IdempotencyStrength.PROVIDER
    assert process.calls[0] == (
        (
            "mbs",
            "formula",
            "read",
            "--target",
            "https://www.maybe.ai/docs/spreadsheets/d/workspace",
            "--field",
            "gross_margin",
            "--output",
            "json",
        ),
        {"credentials": {"access_token": "token"}, "stdin": None, "timeout": 13},
    )


def test_bind_field_rejects_non_base_and_non_formula_targets_before_mutation() -> None:
    process = RecordingProcess(
        [
            envelope("formula.read", metadata_result(target_kind="sheet"), target_kind="sheet"),
            envelope("formula.read", metadata_result(field_type="text")),
        ]
    )
    extension = MaybeSheetFieldFormulaExtension(process)

    mode_result = extension.bind_field(otf.FieldFormulaBindRequest(otf.FieldFormulaTarget(table(), otf.FieldRef(name="gross_margin"))))
    type_result = extension.bind_field(otf.FieldFormulaBindRequest(otf.FieldFormulaTarget(table(), otf.FieldRef(name="gross_margin"))))

    assert mode_result.error is not None
    assert mode_result.error.code is otf.FormulaErrorCode.UNSUPPORTED_MODE
    assert type_result.error is not None
    assert type_result.error.code is otf.FormulaErrorCode.INVALID_TARGET


def test_read_field_uses_stable_field_id_and_fresh_formula_metadata() -> None:
    process = RecordingProcess(
        [
            envelope("formula.read", metadata_result()),
            envelope("formula.read", metadata_result(expression="ROUND(price - cost, 2)")),
        ]
    )
    extension = MaybeSheetFieldFormulaExtension(process)
    binding = _bind(extension, process)

    result = extension.read_field(otf.FieldFormulaReadRequest(binding.target))

    assert result.outcome is otf.FormulaOutcome.SUCCEEDED
    assert result.value is not None
    assert result.value.expression == otf.FormulaExpression("ROUND(price - cost, 2)", otf.MAYBE_BASE)
    assert process.calls[1][0] == (
        "mbs",
        "formula",
        "read",
        "--target",
        "https://www.maybe.ai/docs/spreadsheets/d/workspace",
        "--field-id",
        "fld-gross-margin",
        "--output",
        "json",
    )


def test_set_field_changes_only_expression_and_performs_fresh_readback() -> None:
    process = RecordingProcess(
        [
            envelope("formula.read", metadata_result()),
            envelope("formula.read", metadata_result()),
            envelope("formula.set", {"table_id": "tbl-orders", "field_id": "fld-gross-margin", "revision": HASH_B}),
            envelope("formula.read", metadata_result(expression="ROUND(price - cost, 2)", revision=HASH_B)),
        ]
    )
    extension = MaybeSheetFieldFormulaExtension(process, {"access_token": "token"})
    binding = _bind(extension, process)

    result = extension.set_field(
        otf.FieldFormulaSetRequest(
            binding.target,
            otf.FormulaExpression("ROUND(price - cost, 2)", otf.MAYBE_BASE),
            expected_revision=HASH_A,
            idempotency_key="key-1",
        )
    )

    assert result.outcome is otf.FormulaOutcome.SUCCEEDED
    assert result.value is not None
    assert result.value.affected_count == 1
    assert result.value.formula_observation.field_id == "fld-gross-margin"
    assert process.calls[2][0] == (
        "mbs",
        "formula",
        "set",
        "--target",
        "https://www.maybe.ai/docs/spreadsheets/d/workspace",
        "--field-id",
        "fld-gross-margin",
        "--expression",
        "ROUND(price - cost, 2)",
        "--language",
        "base",
        "--idempotency-key",
        "key-1",
        "--verify",
        "--expected-revision",
        HASH_A,
        "--output",
        "json",
    )


def test_set_field_replays_before_fresh_revision_preflight() -> None:
    process = RecordingProcess(
        [
            envelope("formula.read", metadata_result()),
            envelope("formula.read", metadata_result()),
            envelope("formula.set", {"table_id": "tbl-orders", "field_id": "fld-gross-margin", "revision": HASH_B}),
            envelope("formula.read", metadata_result(expression="ROUND(price - cost, 2)", revision=HASH_B)),
        ]
    )
    extension = MaybeSheetFieldFormulaExtension(process)
    binding = _bind(extension, process)
    request = otf.FieldFormulaSetRequest(
        binding.target,
        otf.FormulaExpression("ROUND(price - cost, 2)", otf.MAYBE_BASE),
        expected_revision=HASH_A,
        idempotency_key="replay-key",
    )

    first = extension.set_field(request)
    replay = extension.set_field(request)
    conflict = extension.set_field(
        otf.FieldFormulaSetRequest(
            binding.target,
            otf.FormulaExpression("price + cost", otf.MAYBE_BASE),
            expected_revision=HASH_A,
            idempotency_key="replay-key",
        )
    )

    assert first.outcome is otf.FormulaOutcome.SUCCEEDED
    assert replay == first
    assert conflict.error is not None
    assert conflict.error.code is otf.FormulaErrorCode.IDEMPOTENCY_CONFLICT
    assert len(process.calls) == 4


def test_read_field_values_uses_stable_record_ids_and_limits_every_page() -> None:
    process = RecordingProcess(
        [
            envelope("formula.read", metadata_result()),
            envelope(
                "base-table.read",
                {
                    "table_id": "tbl-orders",
                    "records": [{"id": "rec-1", "fields": {"fld-gross-margin": 12.5}}],
                    "has_more": True,
                    "next_offset": 1,
                    "calculation_state": "unknown",
                    "revision": HASH_A,
                },
            ),
            envelope(
                "base-table.read",
                {
                    "table_id": "tbl-orders",
                    "records": [{"record_id": "rec-2", "fields": {"fld-gross-margin": None}}],
                    "has_more": False,
                    "calculation_state": "unknown",
                    "revision": HASH_A,
                },
            ),
        ]
    )
    extension = MaybeSheetFieldFormulaExtension(process)
    binding = _bind(extension, process)

    result = extension.read_field_values(
        otf.FieldFormulaValueReadRequest(
            binding.target,
            limits=otf.FormulaResourceLimits(max_records=2, max_response_bytes=1024),
        )
    )

    assert result.outcome is otf.FormulaOutcome.SUCCEEDED
    assert result.value is not None
    assert [item.record_id for item in result.value.values] == ["rec-1", "rec-2"]
    assert result.value.calculation_state is otf.CalculationState.UNKNOWN
    assert process.calls[1][0][-6:] == ("--limit", "2", "--offset", "0", "--output", "json")
    assert process.calls[2][0][-6:] == ("--limit", "2", "--offset", "1", "--output", "json")


def test_recalculate_field_requires_evidence_for_passed_verification() -> None:
    process = RecordingProcess(
        [
            envelope("formula.read", metadata_result()),
            envelope("formula.recalculate", {"field_id": "fld-gross-margin", "status": "completed", "revision": HASH_B}),
        ]
    )
    extension = MaybeSheetFieldFormulaExtension(process)
    binding = _bind(extension, process)

    result = extension.recalculate_field(
        otf.FieldFormulaRecalculateRequest(
            binding.target,
            otf.FieldRecalculationScope.FIELD,
            expected_revision=HASH_A,
            idempotency_key="recalc-1",
        )
    )

    assert result.outcome is otf.FormulaOutcome.SUCCEEDED
    assert result.value is not None
    assert result.value.verification == "unavailable"
    assert result.verification is otf.FormulaVerificationState.UNAVAILABLE
