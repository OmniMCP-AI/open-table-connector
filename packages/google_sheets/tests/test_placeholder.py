from __future__ import annotations

import json
from pathlib import Path


def test_google_sheets_is_an_explicit_placeholder() -> None:
    payload = json.loads((Path(__file__).parents[1] / "src/open_connectors/google_sheets/manifest.json").read_text())
    assert payload["status"] == "placeholder"
    assert payload["available_capabilities"] == []
    assert payload["unsupported_reason"] == "placeholder_not_implemented"
