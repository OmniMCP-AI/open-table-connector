from __future__ import annotations

import importlib
from dataclasses import dataclass

import pytest
from open_table_connector.cli.model import parse_endpoint
from open_table_connector.cli.registry import build_default_registry
from open_table_connector.contract import (
    CapabilityIdentity,
    CapabilityManifest,
    ResourceLimits,
    TableMode,
)

from specification.conformance.universal import cases as cases_module
from specification.conformance.universal.assertions import (
    assert_capabilities_are_unique,
    assert_identity_round_trip,
)
from specification.conformance.universal.cases import ConnectorCase, all_cases, case

_CASE_NAMES = (
    "csv",
    "excel",
    "md",
    "local_files",
    "google_sheets",
    "feishu_bitable",
    "maybe_sheet",
    "sqlite",
    "postgres",
    "dbt",
)
_MANIFESTLESS_CASE_NAMES = ("maybe_sheet", "sqlite", "postgres", "dbt")


@dataclass(frozen=True)
class _ExpectedConnectorMetadata:
    connector_id: str
    connector_version: str
    contract_version: str
    capabilities: tuple[tuple[str, str], ...]
    modes: tuple[str, ...]
    schemes: tuple[str, ...]


_EXPECTED_METADATA = {
    "csv": _ExpectedConnectorMetadata(
        connector_id="csv",
        connector_version="0.1.0",
        contract_version="1.0",
        capabilities=(
            ("uri.resolve", "1.0"),
            ("table.inspect", "1.0"),
            ("table.read.arrow", "1.0"),
            ("table.read.polars", "1.0"),
        ),
        modes=("sheet",),
        schemes=("csv",),
    ),
    "excel": _ExpectedConnectorMetadata(
        connector_id="excel",
        connector_version="0.1.0",
        contract_version="1.0",
        capabilities=(
            ("uri.resolve", "1.0"),
            ("table.inspect", "1.0"),
            ("table.read.arrow", "1.0"),
            ("table.read.polars", "1.0"),
        ),
        modes=("sheet",),
        schemes=("excel",),
    ),
    "md": _ExpectedConnectorMetadata(
        connector_id="md",
        connector_version="0.1.0",
        contract_version="1.0",
        capabilities=(
            ("uri.resolve", "1.0"),
            ("table.inspect", "1.0"),
            ("table.read.arrow", "1.0"),
            ("table.read.polars", "1.0"),
        ),
        modes=("sheet",),
        schemes=("md",),
    ),
    "local_files": _ExpectedConnectorMetadata(
        connector_id="local_files",
        connector_version="0.1.0",
        contract_version="1.0",
        capabilities=(
            ("uri.resolve", "1.0"),
            ("table.inspect", "1.0"),
            ("table.read.arrow", "1.0"),
            ("table.read.polars", "1.0"),
        ),
        modes=("sheet",),
        schemes=("file", "json", "jsonl"),
    ),
    "google_sheets": _ExpectedConnectorMetadata(
        connector_id="google_sheets",
        connector_version="0.1.0",
        contract_version="1.0",
        capabilities=(
            ("uri.resolve", "1.0"),
            ("table.inspect", "1.0"),
            ("table.read.arrow", "1.0"),
            ("table.read.polars", "1.0"),
            ("table.write", "1.0"),
        ),
        modes=("sheet",),
        schemes=("gsheets", "https"),
    ),
    "feishu_bitable": _ExpectedConnectorMetadata(
        connector_id="feishu_bitable",
        connector_version="0.1.0",
        contract_version="1.0",
        capabilities=(
            ("uri.resolve", "1.0"),
            ("table.inspect", "1.0"),
            ("table.read.arrow", "1.0"),
            ("table.read.polars", "1.0"),
            ("table.write", "1.0"),
        ),
        modes=("base",),
        schemes=("feishu", "feishu_bitable"),
    ),
    "maybe_sheet": _ExpectedConnectorMetadata(
        connector_id="maybe_sheet",
        connector_version="0.1.0",
        contract_version="1.0",
        capabilities=(
            ("base.read", "1.0"),
            ("base.inspect", "1.0"),
            ("sheet.read", "1.0"),
            ("sheet.inspect", "1.0"),
            ("table.write", "1.0"),
        ),
        modes=("base", "sheet"),
        schemes=("https", "maybe"),
    ),
    "sqlite": _ExpectedConnectorMetadata(
        connector_id="sqlite",
        connector_version="0.1.0",
        contract_version="1.0",
        capabilities=(
            ("table.read.arrow", "1.0"),
            ("table.read.polars", "1.0"),
            ("table.inspect", "1.0"),
            ("table.execute", "1.0"),
            ("table.write", "1.0"),
        ),
        modes=("base",),
        schemes=("sqlite",),
    ),
    "postgres": _ExpectedConnectorMetadata(
        connector_id="postgres",
        connector_version="0.1.0",
        contract_version="1.0",
        capabilities=(
            ("table.read.arrow", "1.0"),
            ("table.read.polars", "1.0"),
            ("table.inspect", "1.0"),
            ("table.execute", "1.0"),
            ("table.write", "1.0"),
        ),
        modes=("base",),
        schemes=("postgres", "postgresql"),
    ),
    "dbt": _ExpectedConnectorMetadata(
        connector_id="dbt",
        connector_version="0.1.0",
        contract_version="1.0",
        capabilities=(
            ("dbt.compile", "1.0"),
            ("dbt.run", "1.0"),
            ("dbt.cancel", "1.0"),
            ("dbt.artifact.read", "1.0"),
        ),
        modes=(),
        schemes=("file",),
    ),
}


def test_all_current_connectors_have_named_cases() -> None:
    assert tuple(item.name for item in all_cases()) == (
        "csv",
        "excel",
        "md",
        "local_files",
        "google_sheets",
        "feishu_bitable",
        "maybe_sheet",
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
        "csv",
        "excel",
        "md",
        "local_files",
        "google_sheets",
        "feishu_bitable",
        "maybe_sheet",
        "sqlite",
        "postgres",
        "dbt",
    )


@pytest.mark.parametrize(
    ("raw", "expected_connector_id"),
    (
        ("csv:///tmp/orders.csv", "csv"),
        ("excel:///tmp/orders.xlsx", "excel"),
        ("md:///tmp/orders.md", "md"),
    ),
)
def test_universal_cli_fixture_routes_explicit_local_schemes(
    raw: str,
    expected_connector_id: str,
) -> None:
    adapter = build_default_registry().connector_for(parse_endpoint(raw))

    assert adapter.identity.connector_id == expected_connector_id


@pytest.mark.parametrize("connector_case", _CASE_NAMES, ids=str, indirect=True)
def test_connector_identity_is_closed_and_stable(connector_case: ConnectorCase) -> None:
    assert_identity_round_trip(connector_case.identity)


@pytest.mark.parametrize(
    ("case_name", "expected"),
    tuple(
        pytest.param(case_name, expected, id=case_name)
        for case_name, expected in _EXPECTED_METADATA.items()
    ),
)
def test_public_identity_and_manifest_match_literal_expectations(
    case_name: str,
    expected: _ExpectedConnectorMetadata,
) -> None:
    connector_case = case(case_name)
    public_identity = connector_case.connector.identity

    assert public_identity.connector_id == expected.connector_id
    assert public_identity.connector_version == expected.connector_version
    assert public_identity.contract_version == expected.contract_version
    assert connector_case.identity == public_identity

    manifest = getattr(connector_case.connector, "manifest", None)
    if manifest is not None:
        public_capabilities = tuple(
            (item.capability_id, item.capability_version)
            for item in manifest.capabilities
        )
        public_modes = tuple(mode.value for mode in manifest.modes)
        public_schemes = tuple(manifest.uri_schemes)
        assert manifest.connector == public_identity
    else:
        public_capabilities = tuple(
            (
                binding.identity.capability_id,
                binding.identity.capability_version,
            )
            for binding in connector_case.capability_bindings.values()
            if binding.identity is not None
        )
        public_modes = tuple(sorted(mode.value for mode in connector_case.modes))
        public_schemes = tuple(sorted(connector_case.schemes))

    assert public_capabilities == expected.capabilities
    assert public_modes == expected.modes
    assert public_schemes == expected.schemes
    assert connector_case.capabilities == frozenset(
        capability_id for capability_id, _version in expected.capabilities
    )
    assert connector_case.modes == frozenset(TableMode(mode) for mode in expected.modes)
    assert connector_case.schemes == frozenset(expected.schemes)


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


def _assert_formula_capabilities_are_disabled(
    advertised: set[str],
    *,
    connector_name: str,
) -> None:
    formula_capabilities = sorted(
        capability_id
        for capability_id in advertised
        if capability_id.startswith("formula.")
    )
    assert not formula_capabilities, (
        f"{connector_name} advertises disabled formula capabilities: "
        f"{', '.join(formula_capabilities)}"
    )


def test_current_descriptors_do_not_advertise_formula_capabilities() -> None:
    for connector_case in all_cases():
        advertised = set(connector_case.capabilities)
        manifest = getattr(connector_case.connector, "manifest", None)
        if manifest is not None:
            advertised.update(item.capability_id for item in manifest.capabilities)
        advertised.update(
            binding.identity.capability_id
            for binding in connector_case.capability_bindings.values()
            if binding.identity is not None
        )

        _assert_formula_capabilities_are_disabled(
            advertised,
            connector_name=connector_case.name,
        )


def test_unknown_formula_capability_is_rejected_by_disabled_discovery_checkpoint() -> None:
    with pytest.raises(
        AssertionError,
        match=r"fixture advertises disabled formula capabilities: formula\.future\.calculate",
    ):
        _assert_formula_capabilities_are_disabled(
            {"formula.future.calculate"},
            connector_name="fixture",
        )


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


def test_cases_with_sheet_read_returns_mode_specific_maybe_sheet_binding() -> None:
    maybe_case = cases_module.cases_with("sheet.read")[0]
    binding = maybe_case.capability_binding("sheet.read")
    request = binding.make_request(ResourceLimits())
    result = binding.read_arrow(ResourceLimits())

    assert maybe_case.name == "maybe_sheet"
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
