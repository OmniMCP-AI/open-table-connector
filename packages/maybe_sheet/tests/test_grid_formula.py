from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import open_table_connector.formulas as otf
import pytest
from open_table_connector.contract import ConnectorError, ConnectorErrorCode
from open_table_connector.maybe_sheet import MaybeSheetCliAdapter
from open_table_connector.maybe_sheet.connector import MaybeSheetConnector

HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64


def envelope(operation: str, result: dict[str, Any], *, request_id: str = "request-1") -> dict[str, Any]:
    return {
        "contract_version": "1.0",
        "ok": True,
        "operation": operation,
        "target": {"kind": "sheet"},
        "warnings": [],
        "request_id": request_id,
        "result": result,
        "verification": {"status": "passed", "checks": ["provider"]},
        "trace": None,
    }


def worksheet_list(**result: Any) -> dict[str, Any]:
    return envelope(
        "worksheet.list",
        {
            "worksheets": [{"gid": "ws-model", "name": "Model", "type": "sheet"}],
            "revision": HASH_A,
            "recalculation_scopes": ["range", "worksheet", "workbook", "field"],
            "mutation_atomicity": "atomic",
            "revision_enforcement": "checked",
            "idempotency": "provider",
            **result,
        },
    )


def formula_matrix(
    formulas: list[list[str | None]],
    *,
    values: list[list[Any]] | None = None,
    revision: str = HASH_B,
    **result: Any,
) -> dict[str, Any]:
    return envelope(
        "formula.read",
        {
            "formulas": formulas,
            "cell_metadata": [
                [{"kind": "formula" if value is not None else "empty"} for value in row]
                for row in formulas
            ],
            "values": values if values is not None else formulas,
            "revision": revision,
            **result,
        },
    )


class RecordingProcess:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = [deepcopy(response) for response in responses]
        self.calls: list[tuple[tuple[str, ...], dict[str, Any]]] = []

    def run(self, argv, *, credentials=None, stdin=None, timeout=None):
        self.calls.append((tuple(argv), {"credentials": credentials, "stdin": stdin, "timeout": timeout}))
        if not self.responses:
            raise AssertionError("unexpected process call")
        return deepcopy(self.responses.pop(0))


def bound_target() -> otf.BoundGridFormulaTarget:
    return otf.BoundGridFormulaTarget("maybe://doc", otf.WorksheetRef(worksheet_id="ws-model"))


def test_bind_grid_uses_exact_worksheet_identity_and_provider_details() -> None:
    process = RecordingProcess([worksheet_list()])
    extension = _extension(process)

    result = extension.bind_grid(
        otf.GridFormulaBindRequest(
            otf.GridFormulaTarget("maybe://doc", otf.WorksheetRef(name="Model"))
        )
    )

    assert result.outcome is otf.FormulaOutcome.SUCCEEDED
    assert result.value is not None
    assert result.value.target == bound_target()
    assert result.value.capabilities.details.dialects == (otf.MAYBE_SHEET_A1,)
    assert result.value.capabilities.details.max_cells_per_operation == 10_000
    assert result.value.capabilities.details.max_expression_bytes == 64 * 1024
    assert result.value.capabilities.details.recalculation_scopes == ("range", "worksheet", "workbook")
    assert result.value.capabilities.details.mutation_atomicity is otf.MutationAtomicity.ATOMIC
    assert result.value.capabilities.details.revision_enforcement is otf.RevisionEnforcement.CHECKED
    assert result.value.capabilities.details.idempotency_strength is otf.IdempotencyStrength.PROVIDER
    assert process.calls[0] == (
        (
            "mbs",
            "worksheet",
            "list",
            "--uri",
            "https://www.maybe.ai/docs/spreadsheets/d/doc",
            "--output",
            "json",
        ),
        {"credentials": {"access_token": "token"}, "stdin": None, "timeout": 13},
    )


@pytest.mark.parametrize(
    "worksheets",
    [
        [],
        [{"gid": "ws-model", "name": "Model", "type": "table"}],
        [
            {"gid": "ws-model", "name": "Model", "type": "sheet"},
            {"gid": "ws-other", "name": "Model", "type": "sheet"},
        ],
    ],
)
def test_bind_grid_rejects_missing_ambiguous_or_non_sheet_targets(worksheets: list[dict[str, Any]]) -> None:
    process = RecordingProcess([worksheet_list(worksheets=worksheets)])
    result = _extension(process).bind_grid(
        otf.GridFormulaBindRequest(
            otf.GridFormulaTarget("maybe://doc", otf.WorksheetRef(name="Model"))
        )
    )

    assert result.outcome is otf.FormulaOutcome.REJECTED
    assert result.error is not None
    assert result.error.code is otf.FormulaErrorCode.TARGET_NOT_FOUND


def test_read_grid_parses_formula_matrix_and_native_metadata_without_table_read() -> None:
    process = RecordingProcess(
        [
            formula_matrix([["=B1+$C$1", None], [None, "='Quarter Plan'!$B$2"]]),
        ]
    )
    result = _extension(process).read_grid(otf.GridFormulaReadRequest(bound_target(), "A1:B2"))

    assert result.outcome is otf.FormulaOutcome.SUCCEEDED
    assert result.value is not None
    assert [(cell.address, cell.expression.text) for cell in result.value.formulas] == [
        ("A1", "=B1+$C$1"),
        ("B2", "='Quarter Plan'!$B$2"),
    ]
    assert process.calls[0][0] == (
        "mbs",
        "formula",
        "read",
        "--target",
        "https://www.maybe.ai/docs/spreadsheets/d/doc",
        "--gid",
        "ws-model",
        "--range",
        "A1:B2",
        "--output",
        "json",
    )


def test_read_grid_values_uses_formula_rendered_worksheet_and_marks_provider_dynamic() -> None:
    process = RecordingProcess(
        [
            envelope(
                "excel-worksheet.read",
                {
                    "values": [[7, "literal"], [None, {"error": {"code": "DIV0"}}]],
                    "cell_metadata": [
                        [{"kind": "formula"}, {"kind": "value"}],
                        [{"kind": "empty"}, {"kind": "formula"}],
                    ],
                    "calculation_state": "provider_current",
                    "revision": HASH_B,
                },
            )
        ]
    )
    result = _extension(process).read_grid_values(otf.GridFormulaValueReadRequest(bound_target(), "A1:B2"))

    assert result.outcome is otf.FormulaOutcome.SUCCEEDED
    assert result.value is not None
    assert [(cell.address, cell.value.to_wire()) for cell in result.value.values] == [
        ("A1", {"kind": "integer", "value": 7}),
        ("B2", {"kind": "provider_error", "error": {"code": "DIV0"}}),
    ]
    assert result.value.calculation_state is otf.CalculationState.PROVIDER_CURRENT
    assert result.value.calculation_trigger is otf.CalculationTrigger.PROVIDER_READ
    assert result.value.dependency_scope == "provider_dynamic"
    assert process.calls[0][0] == (
        "mbs",
        "excel-worksheet",
        "read",
        "--uri",
        "https://www.maybe.ai/docs/spreadsheets/d/doc",
        "--gid",
        "ws-model",
        "--range",
        "A1:B2",
        "--value-render-option",
        "UNFORMATTED_VALUE",
        "--output",
        "json",
    )


def test_set_uses_verify_then_independent_formula_readback_and_top_left_copy_fill() -> None:
    process = RecordingProcess(
        [
            envelope("formula.set", {"revision": HASH_B, "verification": {"status": "passed"}}),
            formula_matrix([["=B1+$C$1", "=C1+$C$1"], ["=B2+$C$1", "=C2+$C$1"]]),
        ]
    )
    result = _extension(process).set_grid(
        otf.GridFormulaSetRequest(
            bound_target(),
            "A1:B2",
            otf.FormulaExpression("=B1+$C$1", otf.MAYBE_SHEET_A1),
            expected_revision=HASH_A,
            idempotency_key="request-key",
        )
    )

    assert result.outcome is otf.FormulaOutcome.SUCCEEDED
    assert result.commit is otf.FormulaCommitState.COMMITTED
    assert result.verification is otf.FormulaVerificationState.PASSED
    assert result.value is not None
    assert result.value.affected_count == 4
    assert [call[0] for call in process.calls] == [
        (
            "mbs",
            "formula",
            "set",
            "--target",
            "https://www.maybe.ai/docs/spreadsheets/d/doc",
            "--gid",
            "ws-model",
            "--range",
            "A1:B2",
            "--expression",
            "=B1+$C$1",
            "--language",
            "excel",
            "--idempotency-key",
            "request-key",
            "--verify",
            "--expected-revision",
            HASH_A,
            "--output",
            "json",
        ),
        (
            "mbs",
            "formula",
            "read",
            "--target",
            "https://www.maybe.ai/docs/spreadsheets/d/doc",
            "--gid",
            "ws-model",
            "--range",
            "A1:B2",
            "--output",
            "json",
        ),
    ]


def test_cross_mode_reference_is_opaque_and_never_binds_base_target() -> None:
    expression = "='R_Revenue Base'!$C2*0.8"
    process = RecordingProcess(
        [
            envelope("formula.set", {"revision": HASH_B, "verification": {"status": "passed"}}),
            formula_matrix([[expression]], values=[[12.5]]),
            envelope(
                "excel-worksheet.read",
                {
                    "values": [[12.5]],
                    "cell_metadata": [[{"kind": "formula"}]],
                    "calculation_state": "provider_current",
                    "revision": HASH_B,
                },
            ),
        ]
    )
    extension = _extension(process)
    result = extension.set_grid(
        otf.GridFormulaSetRequest(
            bound_target(), "A1", otf.FormulaExpression(expression, otf.MAYBE_SHEET_A1)
        )
    )
    values = extension.read_grid_values(otf.GridFormulaValueReadRequest(bound_target(), "A1"))

    assert result.outcome is otf.FormulaOutcome.SUCCEEDED
    assert result.value is not None
    assert result.value.formula_observation.formulas[0].expression.text == expression
    assert values.value is not None
    assert values.value.dependency_scope == "provider_dynamic"
    assert all("db-table" not in " ".join(call[0]) for call in process.calls)


@pytest.mark.parametrize(
    ("scope", "cell_range", "expected"),
    [
        (otf.GridRecalculationScope.RANGE, "A1:B2", ("--range", "A1:B2")),
        (otf.GridRecalculationScope.WORKSHEET, None, ()),
        (otf.GridRecalculationScope.WORKBOOK, None, ()),
    ],
)
def test_recalculate_only_sends_explicit_supported_scope_and_preserves_effective_scope(
    scope: otf.GridRecalculationScope,
    cell_range: str | None,
    expected: tuple[str, ...],
) -> None:
    process = RecordingProcess(
        [
            envelope(
                "formula.recalculate",
                {
                    "requested_scope": scope.value,
                    "effective_scope": scope.value,
                    "provider_status": "completed",
                    "calculation_state": "provider_current",
                    "revision_before": HASH_A,
                    "revision_after": HASH_B,
                    "value_observation": None,
                },
            )
        ]
    )
    request = otf.GridFormulaRecalculateRequest(bound_target(), scope, cell_range)
    result = _extension(process).recalculate_grid(request)

    assert result.outcome is otf.FormulaOutcome.SUCCEEDED
    assert result.value is not None
    assert result.value.requested_scope == scope.value
    assert result.value.effective_scope == scope.value
    assert process.calls[0][0] == (
        "mbs",
        "formula",
        "recalculate",
        "--target",
        "https://www.maybe.ai/docs/spreadsheets/d/doc",
        "--gid",
        "ws-model",
        *expected,
        "--verify",
        "--output",
        "json",
    )


def test_process_arguments_and_envelopes_never_expose_credentials_and_extra_keys_fail_closed() -> None:
    process = RecordingProcess([worksheet_list()])
    extension = _extension(process, token="super-secret")
    extension.bind_grid(
        otf.GridFormulaBindRequest(
            otf.GridFormulaTarget("maybe://doc", otf.WorksheetRef(name="Model"))
        )
    )
    assert "super-secret" not in repr([call[0] for call in process.calls])
    assert "super-secret" not in repr([call[1]["stdin"] for call in process.calls])
    assert "super-secret" not in repr(extension)
    assert "super-secret" not in json.dumps([call[0] for call in process.calls])

    malformed = RecordingProcess([dict(worksheet_list(), extra="not-allowed")])
    result = _extension(malformed).bind_grid(
        otf.GridFormulaBindRequest(
            otf.GridFormulaTarget("maybe://doc", otf.WorksheetRef(name="Model"))
        )
    )
    assert result.outcome is otf.FormulaOutcome.FAILED
    assert result.error is not None
    assert result.error.code is otf.FormulaErrorCode.PROTOCOL_FAILURE


def test_formula_reads_apply_caller_response_limit_before_parsing() -> None:
    process = RecordingProcess([formula_matrix([["=A1"]], padding="x" * 200)])
    result = _extension(process).read_grid(
        otf.GridFormulaReadRequest(
            bound_target(), "A1", limits=otf.FormulaResourceLimits(max_response_bytes=100)
        )
    )

    assert result.outcome is otf.FormulaOutcome.REJECTED
    assert result.error is not None
    assert result.error.code is otf.FormulaErrorCode.RESOURCE_LIMIT


def test_pre_dispatch_timeout_is_retriable_but_lost_acknowledgement_is_terminal() -> None:
    class TimeoutProcess(RecordingProcess):
        def run(self, argv, *, credentials=None, stdin=None, timeout=None):
            self.calls.append((tuple(argv), {"credentials": credentials, "stdin": stdin, "timeout": timeout}))
            raise ConnectorError(
                ConnectorErrorCode.TIMEOUT,
                "timed out",
                {"before_dispatch": True},
            )

    request = otf.GridFormulaSetRequest(
        bound_target(), "A1", otf.FormulaExpression("=1", otf.MAYBE_SHEET_A1), idempotency_key="retry"
    )
    process = TimeoutProcess([])
    extension = _extension(process)
    first = extension.set_grid(request)
    second = extension.set_grid(request)
    assert first.error is not None and first.error.code is otf.FormulaErrorCode.TIMEOUT
    assert second.error is not None and second.error.code is otf.FormulaErrorCode.TIMEOUT
    assert len(process.calls) == 2

    class LostAckProcess(RecordingProcess):
        def run(self, argv, *, credentials=None, stdin=None, timeout=None):
            self.calls.append((tuple(argv), {"credentials": credentials, "stdin": stdin, "timeout": timeout}))
            raise ConnectorError(ConnectorErrorCode.TIMEOUT, "timed out", {})

    process = LostAckProcess([])
    extension = _extension(process)
    first = extension.set_grid(request)
    second = extension.set_grid(request)
    assert first.outcome is otf.FormulaOutcome.UNKNOWN
    assert second.outcome is otf.FormulaOutcome.UNKNOWN
    assert len(process.calls) == 1


def test_adapter_composes_grid_delegate_and_optional_field_delegate() -> None:
    process = RecordingProcess([])
    adapter = MaybeSheetCliAdapter(MaybeSheetConnector(process), {"access_token": "token"}, 13)

    extension = adapter.formula_extension_for()
    assert isinstance(extension, otf.CompositeFormulaConnectorExtension)
    assert extension.grid.__class__.__name__ == "MaybeSheetGridFormulaExtension"
    assert extension.field is None


def _extension(process: RecordingProcess, *, token: str = "token"):
    from open_table_connector.maybe_sheet.grid_formula import MaybeSheetGridFormulaExtension

    return MaybeSheetGridFormulaExtension(MaybeSheetConnector(process), {"access_token": token}, 13)
