import json
from pathlib import Path


def _manifest():
    path = Path(__file__).parent / "fixtures" / "layout-protocol.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_layout_protocol_manifest_is_explicit_about_evidence():
    data = _manifest()
    assert data["version"] == "1.0"
    assert isinstance(data["provider_version"], str)
    assert "commands" in data and "responses" in data
    assert "supported_fields" in data and "gaps" in data
    for field, evidence in data["supported_fields"].items():
        assert evidence["read_response"] in data["responses"], field
        if evidence["write"]:
            assert evidence["write_command"] in data["commands"], field
            assert evidence["reopen_response"] in data["responses"], field


def test_unverified_layout_capabilities_are_not_advertised():
    data = _manifest()
    required = {
        "range.style.read",
        "worksheet.config.read",
        "alignment",
        "border",
        "number_format",
        "text_layout",
    }
    assert required - data["supported_fields"].keys() <= set(data["gaps"])
