from __future__ import annotations

import copy

import pytest

from open_table_connector.spreadsheets._layout import LayoutCapabilityError, normalize_config, normalize_style, validate_descriptor
from open_table_connector.spreadsheets.observations import decode_observation, physical_hash


@pytest.fixture
def descriptor():
    return {
        "target": "excel",
        "dialect": "ooxml/strict",
        "limits": {"max_changes": 32, "max_cells": 250000},
        "operations": {
            "range.style": {name: {"read": True, "write": True, "persist": True} for name in ("bold", "italic", "font_size", "foreground", "fill", "number_format", "horizontal", "vertical", "wrap_text", "shrink_to_fit", "border", "text_layout")},
            "worksheet.config": {
                "row_heights": {"read": True, "write": True, "persist": True, "units": ["points"]},
                "column_sizes": {"read": True, "write": True, "persist": True, "units": ["excel_character"]},
                "gridlines": {"read": True, "write": True, "persist": True},
                "view": {"read": True, "write": True, "persist": True},
            },
        },
    }


def test_f1_fixture_covers_financial_report(financial_layout_intent):
    assert financial_layout_intent["range"] == "A1:F40"
    assert set(financial_layout_intent["intent"]) >= {"title", "header", "body", "amounts", "total", "footnote"}


def test_f2_descriptor_is_detached_and_strict(descriptor):
    original = copy.deepcopy(descriptor)
    result = validate_descriptor(descriptor)
    result["limits"]["max_changes"] = 1
    assert descriptor == original


def test_f3_mixed_style_fields(descriptor):
    result = normalize_style({"bold": False, "italic": True, "font_size": 10, "horizontal": "right"}, descriptor=descriptor)
    assert result == {"bold": False, "italic": True, "font_size": 10, "horizontal": "right"}


def test_f4_border_partial_patch(descriptor):
    result = normalize_style({"border": {"top": {"style": "thin"}}}, descriptor=descriptor)
    assert result["border"]["top"]["style"] == "thin"


def test_f5_text_modes_are_mutually_exclusive(descriptor):
    result = normalize_style({"text_layout": "wrap"}, descriptor=descriptor)
    assert result["wrap_text"] is True and result["shrink_to_fit"] is False
    with pytest.raises(ValueError):
        normalize_style({"wrap_text": True, "shrink_to_fit": True}, descriptor=descriptor)


def test_f6_native_dimensions(descriptor, financial_layout_intent):
    result = normalize_config({"row_heights": {1: 28}, "column_sizes": financial_layout_intent["dimensions"]["columns"], "gridlines": False}, descriptor=descriptor)
    assert result["column_sizes"]["A"]["unit"] == "excel_character"


def test_f7_unsupported_units_are_explicit(descriptor):
    with pytest.raises(LayoutCapabilityError):
        normalize_config({"column_sizes": {"A": {"value": 180, "unit": "px"}}}, descriptor=descriptor)


def test_f8_complete_observation_has_recomputable_hash():
    payload = {"kind": "spreadsheet.range.style.observation/1.0", "target": {"provider": "excel", "resource": "book", "worksheet_id": "1"}, "coverage": {"complete": True, "range": "A1", "fields": ["bold"]}, "physical": {"cells": [{"row": 1, "column": 1, "fields": {"bold": {"effective": True, "source_ref": "s"}}}], "sources": {"s": {"kind": "explicit"}}}}
    assert decode_observation(payload)["physical_hash"] == physical_hash(payload)


def test_f9_hash_ignores_provenance():
    payload = {"kind": "spreadsheet.range.style.observation/1.0", "target": {"provider": "excel", "resource": "book", "worksheet_id": "1"}, "coverage": {"complete": True, "range": "A1", "fields": ["bold"]}, "physical": {"cells": [{"row": 1, "column": 1, "fields": {"bold": {"effective": True, "source_ref": "s"}}}], "sources": {"s": {"kind": "explicit"}}}}
    first = decode_observation({**payload, "provenance": {"revision": "one"}})
    second = decode_observation({**payload, "provenance": {"revision": "two"}})
    assert first["physical_hash"] == second["physical_hash"]


@pytest.mark.parametrize("mode", ["no_wrap", "wrap", "shrink_to_fit"])
def test_f10_text_mode_roundtrip(descriptor, mode):
    assert normalize_style({"text_layout": mode}, descriptor=descriptor)


def test_f11_false_is_not_omitted(descriptor):
    assert normalize_style({"bold": False}, descriptor=descriptor)["bold"] is False


def test_f12_view_config_is_preserved(descriptor):
    assert normalize_config({"view": {"zoom_percent": 90, "frozen_rows": 3}}, descriptor=descriptor)["view"]["zoom_percent"] == 90


def test_f13_explicit_clip_rejected(descriptor):
    with pytest.raises(LayoutCapabilityError):
        normalize_style({"text_layout": "clip"}, descriptor=descriptor)


def test_f14_format_code_is_exact(descriptor):
    code = '#,##0.00;[Red](#,##0.00);"-";@'
    assert normalize_style({"number_format": code}, descriptor=descriptor)["number_format"]["code"] == code


def test_f15_fixture_has_no_generated_expected_values(financial_layout_intent):
    assert "expected" not in financial_layout_intent
