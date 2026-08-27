from __future__ import annotations

import importlib

import pytest

from open_connectors.contract import ResourceLimits, TableMode

from specification.conformance.universal import cases as cases_module
from specification.conformance.universal.cases import all_cases, case


def test_all_current_connectors_have_named_cases() -> None:
    assert {item.name for item in all_cases()} == {
        "local_files",
        "google_sheets",
        "feishu_bitable",
        "maybesheet",
        "sqlite",
        "postgres",
        "dbt",
    }


def test_case_lookup_rejects_unknown_connector() -> None:
    with pytest.raises(KeyError, match="unknown connector case"):
        case("missing")


def test_all_cases_bootstrap_fixtures_without_pytest_configure() -> None:
    reloaded = importlib.reload(cases_module)

    assert {item.name for item in reloaded.all_cases()} == {
        "local_files",
        "google_sheets",
        "feishu_bitable",
        "maybesheet",
        "sqlite",
        "postgres",
        "dbt",
    }


def test_all_advertised_capabilities_have_case_bindings() -> None:
    for connector_case in all_cases():
        assert set(connector_case.capability_bindings) == connector_case.capabilities


def test_cases_with_sheet_read_returns_mode_specific_maybesheet_binding() -> None:
    maybe_case = cases_module.cases_with("sheet.read")[0]
    binding = maybe_case.capability_binding("sheet.read")
    request = binding.make_request(ResourceLimits())
    result = binding.read_arrow(ResourceLimits())

    assert maybe_case.name == "maybesheet"
    assert request.mode is TableMode.SHEET
    assert request.target == "Orders"
    assert result.receipt.capability.capability_id == "sheet.read"
    assert result.receipt.mode is TableMode.SHEET


def test_dbt_capabilities_expose_fixture_backed_operations() -> None:
    dbt_case = case("dbt")

    compile_operation = dbt_case.capability_binding("dbt.compile").invoke()
    run_result = dbt_case.capability_binding("dbt.run").invoke()
    cancel_result = dbt_case.capability_binding("dbt.cancel").invoke()
    artifact = dbt_case.capability_binding("dbt.artifact.read").invoke()

    assert compile_operation.manifest_ref == "manifest.json"
    assert run_result.status == "success"
    assert cancel_result.status == "cancelled"
    assert artifact == b'{"nodes":{"model.fixture.orders":{}}}'
