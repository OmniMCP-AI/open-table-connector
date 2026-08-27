from __future__ import annotations

from pathlib import Path

from _pytest.tmpdir import TempPathFactory
import pytest

from specification.conformance.universal.cases import (
    all_cases,
    case,
    configure_fixture_bundle,
)
from specification.conformance.universal.fixtures import build_fixture_bundle


def pytest_configure(config: pytest.Config) -> None:
    factory = TempPathFactory.from_config(config, _ispytest=True)
    root = factory.mktemp("universal-conformance")
    configure_fixture_bundle(build_fixture_bundle(Path(root)))


@pytest.fixture
def connector_cases() -> tuple:
    return all_cases()


@pytest.fixture
def connector_case(request: pytest.FixtureRequest):
    name = getattr(request, "param", None)
    if name is None:
        raise RuntimeError("connector_case requires an indirect case-name parameter")
    return case(str(name))
