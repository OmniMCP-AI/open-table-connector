from __future__ import annotations

import open_table_connector.formulas as otf
import pytest
from open_table_connector.conformance.formulas import (
    FormulaProviderCase,
    assert_field_formula_conformance,
    assert_grid_formula_conformance,
    field_formula_case_params,
    grid_formula_case_params,
    load_formula_cases,
)

from specification.conformance.formulas.support import (
    BrokenBehavior,
    field_case_kwargs,
    grid_case_kwargs,
)


def test_load_formula_cases_rejects_duplicate_provider_target_pairs() -> None:
    duplicate = FormulaProviderCase(**grid_case_kwargs())

    with pytest.raises(ValueError, match="duplicate"):
        load_formula_cases((FormulaProviderCase(**grid_case_kwargs()), duplicate))


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

    assert [param.id for param in grid_params] == ["gridfake[grid]"]
    assert [param.id for param in field_params] == ["fieldfake[field]"]
