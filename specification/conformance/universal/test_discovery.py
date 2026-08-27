from __future__ import annotations

import importlib

import pytest

from open_connectors.contract import CapabilityIdentity, CapabilityManifest, ResourceLimits, TableMode

from specification.conformance.universal.assertions import (
    assert_capabilities_are_unique,
    assert_identity_round_trip,
)

from specification.conformance.universal import cases as cases_module
from specification.conformance.universal.cases import ConnectorCase, all_cases, case

_CASE_NAMES = tuple(item.name for item in all_cases())
_MANIFESTLESS_CASE_NAMES = tuple(
    item.name for item in all_cases() if getattr(item.connector, "manifest", None) is None
)


def test_all_current_connectors_have_named_cases() -> None:
    assert tuple(item.name for item in all_cases()) == (
        "local_files",
        "google_sheets",
        "feishu_bitable",
        "maybesheet",
        "sqlite",
        "postgres",
        "dbt",
    )


def test_case_lookup_rejects_unknown_connector() -> None:
    with pytest.raises(KeyError, match="unknown connector case"):
        case("missing")


def test_all_cases_bootstrap_fixtures_without_pytest_configure() -> None:
    reloaded = importlib.reload(cases_module)

    assert tuple(item.name for item in reloaded.all_cases()) == (
        "local_files",
        "google_sheets",
        "feishu_bitable",
        "maybesheet",
        "sqlite",
        "postgres",
        "dbt",
    )


@pytest.mark.parametrize("connector_case", _CASE_NAMES, ids=str, indirect=True)
def test_connector_identity_is_closed_and_stable(connector_case: ConnectorCase) -> None:
    assert_identity_round_trip(connector_case.identity)


@pytest.mark.parametrize("connector_case", _CASE_NAMES, ids=str, indirect=True)
def test_case_manifest_capabilities_modes_and_schemes_are_closed(
    connector_case: ConnectorCase,
    capability_identities: tuple[CapabilityIdentity, ...],
    capability_manifest: CapabilityManifest,
) -> None:
    assert_capabilities_are_unique(
        capability_identities,
        expected_connector=connector_case.identity,
        expected_capabilities=connector_case.capabilities,
        expected_modes=connector_case.modes,
        expected_schemes=connector_case.schemes,
        manifest=capability_manifest,
    )


@pytest.mark.parametrize("connector_case", _CASE_NAMES, ids=str, indirect=True)
def test_manifest_capability_wire_shape_is_closed(
    connector_case: ConnectorCase,
    capability_identities: tuple[CapabilityIdentity, ...],
) -> None:
    for capability in capability_identities:
        wire = capability.to_wire()

        assert CapabilityIdentity.from_wire(wire) == capability
        assert set(wire) == {"capability_id", "capability_version"}


@pytest.mark.parametrize(
    "connector_case", _MANIFESTLESS_CASE_NAMES, ids=str, indirect=True
)
def test_manifestless_capabilities_use_public_binding_identities(
    connector_case: ConnectorCase,
    capability_identities: tuple[CapabilityIdentity, ...],
) -> None:
    binding_identities = tuple(
        connector_case.capability_binding(capability).identity
        for capability in connector_case.capability_bindings
    )

    assert all(
        actual is declared
        for actual, declared in zip(
            capability_identities,
            binding_identities,
            strict=True,
        )
    )


def test_all_advertised_capabilities_have_case_bindings() -> None:
    for connector_case in all_cases():
        assert set(connector_case.capability_bindings) == connector_case.capabilities


@pytest.mark.parametrize("connector_case", _CASE_NAMES, ids=str, indirect=True)
def test_case_modes_are_closed_to_contract_values(
    connector_case: ConnectorCase,
    capability_manifest: CapabilityManifest | None,
) -> None:
    assert set(connector_case.modes).issubset(set(TableMode))
    if capability_manifest is None:
        if connector_case.name == "dbt":
            assert connector_case.modes == frozenset()
        return
    assert tuple(capability_manifest.modes) == tuple(dict.fromkeys(capability_manifest.modes))
    assert set(capability_manifest.modes) == set(connector_case.modes)


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
