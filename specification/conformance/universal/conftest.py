from __future__ import annotations

import os
from pathlib import Path

import polars as pl
import pytest

from open_table_connector.contract import CapabilityIdentity, CapabilityManifest, TableMode

from specification.conformance.universal.cases import (
    ConnectorCase,
    all_cases,
    case,
    configure_fixture_bundle,
)
from specification.conformance.universal.fixtures import (
    UniversalFixtureBundle,
    build_fixture_bundle,
)


_PROVIDER_CREDENTIAL_ENVIRONMENT_VARIABLES = frozenset(
    {
        "FEISHU_TENANT_ACCESS_TOKEN",
        "GOOGLE_SHEETS_ACCESS_TOKEN",
        "MAYBESHEET_ACCESS_TOKEN",
    }
)


@pytest.fixture(autouse=True)
def isolated_universal_fixture_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> UniversalFixtureBundle:
    for variable in _PROVIDER_CREDENTIAL_ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    bundle = build_fixture_bundle(tmp_path)
    configure_fixture_bundle(bundle)
    return bundle


@pytest.fixture
def sanitized_subprocess_env() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if key not in _PROVIDER_CREDENTIAL_ENVIRONMENT_VARIABLES
    }


@pytest.fixture
def connector_cases() -> tuple[ConnectorCase, ...]:
    return all_cases()


@pytest.fixture
def connector_case(request: pytest.FixtureRequest) -> ConnectorCase:
    name = getattr(request, "param", None)
    if name is None:
        raise RuntimeError("connector_case requires an indirect case-name parameter")
    return case(str(name))


@pytest.fixture(
    params=(
        pytest.param(
            "gsheets://user:fixture-token@spreadsheet/Orders",
            id="google-sheets-userinfo",
        ),
        pytest.param(
            "feishu://fixture-app/orders?token=fixture-token",
            id="feishu-token-query",
        ),
        pytest.param(
            "postgres://fixture.local/analytics?password=fixture-secret",
            id="postgres-password-query",
        ),
        pytest.param(
            "https://www.maybe.ai/docs/spreadsheets/d/fixture-doc?access_token=fixture-token",
            id="maybesheet-access-token-query",
        ),
    )
)
def invalid_credential_bearing_uri(request: pytest.FixtureRequest) -> str:
    return str(request.param)


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
    identities: list[CapabilityIdentity] = []
    for binding in connector_case.capability_bindings.values():
        if binding.identity is None:
            raise AssertionError(
                f"{connector_case.name}:{binding.capability} has no public capability identity"
            )
        identities.append(binding.identity)
    return tuple(identities)


@pytest.fixture
def write_if_exists_by_case() -> dict[str, str]:
    return {
        "google_sheets": "replace",
        "feishu_bitable": "append",
        "maybesheet": "append",
        "sqlite": "replace",
        "postgres": "replace",
    }
