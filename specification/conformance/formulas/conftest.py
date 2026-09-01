from __future__ import annotations

import pytest

from .support import SECURITY_EXPRESSION, SECURITY_MARKERS


@pytest.fixture
def formula_security_markers() -> tuple[str, ...]:
    return SECURITY_MARKERS


@pytest.fixture
def formula_security_expression() -> object:
    return SECURITY_EXPRESSION
