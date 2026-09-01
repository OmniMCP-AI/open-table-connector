from __future__ import annotations

from dataclasses import replace

import open_table_connector.formulas as otf
import pytest
from open_table_connector.conformance.formulas import (
    FormulaProviderCase,
    assert_field_formula_conformance,
    assert_formula_receipt_safe,
    assert_grid_formula_conformance,
    field_formula_case_params,
    grid_formula_case_params,
    load_formula_cases,
)

from specification.conformance.formulas.support import (
    BrokenBehavior,
    field_case_kwargs,
    grid_case_data,
    grid_case_kwargs,
)


def test_load_formula_cases_rejects_duplicate_provider_target_dialect_keys() -> None:
    duplicate = FormulaProviderCase(**grid_case_kwargs())

    with pytest.raises(ValueError, match="duplicate"):
        load_formula_cases((FormulaProviderCase(**grid_case_kwargs()), duplicate))


def test_load_formula_cases_and_params_allow_and_identify_distinct_dialects() -> None:
    base_kwargs = grid_case_kwargs()
    base_case = FormulaProviderCase(**base_kwargs)
    alternate_case = FormulaProviderCase(
        **{
            **base_kwargs,
            "dialect": otf.MAYBE_SHEET_A1,
            "grid_case": replace(
                grid_case_data(),
                set_expression=otf.FormulaExpression("=A1", otf.MAYBE_SHEET_A1),
                conflicting_expression=otf.FormulaExpression("=Z9", otf.MAYBE_SHEET_A1),
            ),
            "security_expression": otf.FormulaExpression(
                "=HYPERLINK(\"https://secret.example\", \"token\")",
                otf.MAYBE_SHEET_A1,
            ),
        }
    )

    cases = load_formula_cases(base_case, alternate_case)

    assert [param.id for param in grid_formula_case_params(cases)] == [
        "gridfake[grid:google-sheets-a1]",
        "gridfake[grid:maybe-sheet-a1]",
    ]


def test_grid_formula_conformance_accepts_a_capability_complete_provider_case() -> None:
    assert_grid_formula_conformance(FormulaProviderCase(**grid_case_kwargs()))


def test_field_formula_conformance_accepts_a_capability_complete_provider_case() -> None:
    assert_field_formula_conformance(FormulaProviderCase(**field_case_kwargs()))


@pytest.mark.parametrize(
    ("broken", "pattern"),
    [
        (BrokenBehavior(broadcast_copy_fill=True), "copy-fill|top_left|top-left"),
        (BrokenBehavior(infer_formula_from_leading_equals=True), "leading `=`|leading =|literal"),
        (BrokenBehavior(value_without_dependency_scope=True), "dependency_scope"),
        (BrokenBehavior(receipt_leak=True), "receipt|marker|expression"),
        (BrokenBehavior(accept_stale_revision=True), "stale revision|STALE_REVISION"),
        (BrokenBehavior(allow_idempotency_reuse=True), "idempotency|conflict"),
        (
            BrokenBehavior(unsupported_capabilities=(otf.GRID_SET.to_reference(),)),
            "unsupported advertised capability|UNSUPPORTED_CAPABILITY",
        ),
    ],
)
def test_grid_formula_conformance_rejects_broken_provider_behaviors(
    broken: BrokenBehavior,
    pattern: str,
) -> None:
    with pytest.raises(AssertionError, match=pattern):
        assert_grid_formula_conformance(FormulaProviderCase(**grid_case_kwargs(broken=broken)))


def test_field_formula_conformance_rejects_formula_field_conversion() -> None:
    with pytest.raises(AssertionError, match="field_id|conversion|stable"):
        assert_field_formula_conformance(
            FormulaProviderCase(**field_case_kwargs(broken=BrokenBehavior(field_conversion=True)))
        )


def test_case_param_helpers_filter_by_target_capability_and_live_evidence() -> None:
    cases = load_formula_cases(
        (
            FormulaProviderCase(**grid_case_kwargs()),
            FormulaProviderCase(**field_case_kwargs()),
        )
    )

    grid_params = grid_formula_case_params(cases, capability=otf.GRID_SET)
    field_params = field_formula_case_params(
        cases,
        capability=otf.FIELD_SET,
        configured_live_only=True,
    )

    assert [param.id for param in grid_params] == ["gridfake[grid:google-sheets-a1]"]
    assert [param.id for param in field_params] == ["fieldfake[field:maybe-base]"]


def test_formula_receipt_safety_accepts_one_typed_receipt() -> None:
    case = FormulaProviderCase(**grid_case_kwargs())
    receipt = case.extension_factory().read_grid(
        otf.GridFormulaReadRequest(case.grid_target_factory(), case.grid_case.literal_range)
    ).receipts[0]

    assert_formula_receipt_safe(receipt)


def test_grid_set_only_conformance_does_not_call_unadvertised_grid_read() -> None:
    case = FormulaProviderCase(
        **grid_case_kwargs(
            static_capabilities=(otf.GRID_SET,),
            broken=BrokenBehavior(reject_grid_read=True),
        )
    )

    assert_grid_formula_conformance(case)


def test_field_set_only_conformance_does_not_call_unadvertised_field_read() -> None:
    case = FormulaProviderCase(
        **field_case_kwargs(
            static_capabilities=(otf.FIELD_SET,),
            broken=BrokenBehavior(reject_field_read=True),
        )
    )

    assert_field_formula_conformance(case)


def test_field_conformance_derives_forbidden_text_from_submitted_expression() -> None:
    with pytest.raises(AssertionError, match="forbidden|expression|receipt"):
        assert_field_formula_conformance(
            FormulaProviderCase(**field_case_kwargs(broken=BrokenBehavior(receipt_leak=True)))
        )


def test_grid_conformance_uses_the_submitted_source_expression_for_copy_fill() -> None:
    source_expression = otf.FormulaExpression("=SUM(A1:A2)", otf.GOOGLE_SHEETS_A1)
    case_kwargs = grid_case_kwargs(set_expression=source_expression)

    assert_grid_formula_conformance(FormulaProviderCase(**case_kwargs))
