from __future__ import annotations

import os

import pytest


def test_maybe_financial_layout_live_gate():
    if os.environ.get("OTC_TEST_MBS_LAYOUT_ENABLED") != "1":
        pytest.skip("authenticated MaybeSheet layout gate is disabled")
    pytest.fail("live MaybeSheet layout fixture is not configured in this environment")


def test_excel_financial_layout_render_gate():
    if os.environ.get("OTC_TEST_EXCEL_LAYOUT_RENDER_ENABLED") != "1":
        pytest.skip("Excel application render gate is disabled")
    pytest.fail("Excel application render fixture is not configured in this environment")
