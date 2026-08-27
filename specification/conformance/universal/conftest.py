from __future__ import annotations

import pytest

from specification.conformance.universal.cases import all_cases, case


@pytest.fixture
def connector_cases() -> tuple:
    return all_cases()


@pytest.fixture
def connector_case(request: pytest.FixtureRequest):
    name = getattr(request, "param", None)
    if name is None:
        raise RuntimeError("connector_case requires an indirect case-name parameter")
    return case(str(name))
