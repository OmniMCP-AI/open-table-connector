from __future__ import annotations

import polars as pl
import pytest

from open_connectors.contract import CapabilityIdentity, CapabilityManifest, TableMode

from specification.conformance.universal.cases import ConnectorCase, all_cases, case


@pytest.fixture
def connector_cases() -> tuple[ConnectorCase, ...]:
    return all_cases()


@pytest.fixture
def connector_case(request: pytest.FixtureRequest) -> ConnectorCase:
    name = getattr(request, "param", None)
    if name is None:
        raise RuntimeError("connector_case requires an indirect case-name parameter")
    return case(str(name))


@pytest.fixture
def invalid_credential_bearing_uris() -> tuple[str, ...]:
    return (
        "gsheets://user:fixture-token@spreadsheet/Orders",
        "feishu://fixture-app/orders?token=fixture-token",
        "postgres://fixture.local/analytics?password=fixture-secret",
        "https://www.maybe.ai/docs/spreadsheets/d/fixture-doc?access_token=fixture-token",
    )


@pytest.fixture
def write_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "id": ["write-1", "write-2"],
            "amount": ["3.50", "4.00"],
        }
    )


@pytest.fixture
def capability_manifest(connector_case: ConnectorCase) -> CapabilityManifest | None:
    return getattr(connector_case.connector, "manifest", None)


@pytest.fixture
def capability_identities(connector_case: ConnectorCase) -> tuple[CapabilityIdentity, ...]:
    manifest = getattr(connector_case.connector, "manifest", None)
    if manifest is not None:
        return tuple(manifest.capabilities)
    return tuple(
        CapabilityIdentity(binding.capability, "1.0")
        for binding in connector_case.capability_bindings.values()
    )


@pytest.fixture
def write_if_exists_by_case() -> dict[str, str]:
    return {
        "google_sheets": "replace",
        "feishu_bitable": "append",
        "maybesheet": "append",
        "sqlite": "replace",
        "postgres": "replace",
    }


@pytest.fixture
def expected_write_affected_rows_by_case() -> dict[str, int]:
    return {
        "google_sheets": 2,
        "feishu_bitable": 2,
        "maybesheet": 1,
        "sqlite": 2,
        "postgres": 2,
    }
