from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def financial_layout_intent():
    path = Path(__file__).with_name("fixtures") / "financial-layout.json"
    return json.loads(path.read_text(encoding="utf-8"))
