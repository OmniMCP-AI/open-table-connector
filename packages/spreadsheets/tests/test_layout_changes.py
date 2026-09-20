from __future__ import annotations

import pytest

from open_table_connector.spreadsheets import Change
from open_table_connector.spreadsheets._layout import (
    LayoutCapabilityError,
    normalize_config,
    normalize_style,
    prepare_layout,
    validate_descriptor,
)
from open_table_connector.spreadsheets.capabilities import SPREADSHEET_RANGE_STYLE


@pytest.fixture
def excel_descriptor():
    return {
        "target": "excel",
        "dialect": "ooxml/strict",
        "limits": {"cells": 250000},
        "operations": {
            "range.style": {
                field: {
                    "read": True,
                    "write": True,
                    "persist": True,
                    "values": values,
                    "units": units,
                    "defaults_source": "excel",
                }
                for field, values, units in (
                    ("bold", None, None),
                    ("italic", None, None),
                    ("font_size", None, ("points",)),
                    ("foreground", None, None),
                    ("fill", None, None),
                    ("number_format", None, None),
                    ("horizontal", ("left", "center", "right"), None),
                    ("vertical", ("top", "center", "bottom"), None),
                    ("text_layout", ("no_wrap", "wrap", "shrink_to_fit"), None),
                    ("wrap_text", None, None),
                    ("shrink_to_fit", None, None),
                    ("border", ("none", "thin", "medium", "thick", "dashed", "dotted", "double"), None),
                )
            },
            "worksheet.config": {
                "row_heights": {"write": True, "read": True, "persist": True, "units": ["points"]},
                "column_sizes": {
                    "write": True,
                    "read": True,
                    "persist": True,
                    "units": ["excel_character"],
                },
                "gridlines": {"write": True, "read": True, "persist": True},
                "view": {"write": True, "read": True, "persist": True},
            },
        },
    }


def test_descriptor_rejects_non_boolean_capability_flags(excel_descriptor):
    excel_descriptor["operations"]["range.style"]["bold"]["read"] = 1
    with pytest.raises(ValueError, match="boolean"):
        validate_descriptor(excel_descriptor)


def test_switching_to_wrap_clears_shrink(excel_descriptor):
    patch = normalize_style(
        {"text_layout": "wrap"},
        descriptor=excel_descriptor,
        baseline={"wrap_text": False, "shrink_to_fit": True},
    )
    assert patch["wrap_text"] is True
    assert patch["shrink_to_fit"] is False


def test_text_modes_and_raw_flags_are_exclusive(excel_descriptor):
    with pytest.raises(ValueError, match="conflict"):
        normalize_style(
            {"text_layout": "wrap", "wrap_text": True}, descriptor=excel_descriptor
        )
    with pytest.raises(ValueError, match="both"):
        normalize_style(
            {"wrap_text": True, "shrink_to_fit": True}, descriptor=excel_descriptor
        )
    with pytest.raises(LayoutCapabilityError, match="clip"):
        normalize_style({"text_layout": "clip"}, descriptor=excel_descriptor)


def test_border_is_a_partial_patch_and_none_clears(excel_descriptor):
    patch = normalize_style(
        {
            "border": {
                "top": {"style": "thin"},
                "bottom": {"style": "none"},
            }
        },
        descriptor=excel_descriptor,
    )
    assert patch["border"] == {"top": {"style": "thin"}, "bottom": {"style": "none"}}
    with pytest.raises(ValueError, match="style"):
        normalize_style({"border": {"left": {"color": "#000000"}}}, descriptor=excel_descriptor)


def test_column_sizes_require_native_units_and_conflicts_are_rejected(excel_descriptor):
    config = normalize_config(
        {"row_heights": {1: 24}, "column_sizes": {"A": {"value": 18, "unit": "excel_character"}}},
        descriptor=excel_descriptor,
    )
    assert config["row_heights"] == {1: 24}
    assert config["column_sizes"]["A"] == {"value": 18, "unit": "excel_character"}
    with pytest.raises(ValueError, match="conflict"):
        normalize_config(
            {"column_sizes": {"A": {"value": 18, "unit": "excel_character"}}, "column_widths": {"A": 20}},
            descriptor=excel_descriptor,
        )
    with pytest.raises(LayoutCapabilityError, match="px"):
        normalize_config(
            {"column_sizes": {"A": {"value": 180, "unit": "px"}}}, descriptor=excel_descriptor
        )


def test_prepare_layout_preserves_baseline_and_order(excel_descriptor):
    changes = [
        Change("one", SPREADSHEET_RANGE_STYLE, "Report", {"bold": True}),
        Change("two", SPREADSHEET_RANGE_STYLE, "Report", {"italic": False}),
    ]
    prepared = prepare_layout(
        changes,
        baseline={"style": {"bold": False, "fill": "#FFFFFF"}},
        descriptor=excel_descriptor,
    )
    assert [item["operation_id"] for item in prepared["changes"]] == ["one", "two"]
    assert prepared["expected"]["style"] == {"bold": True, "fill": "#FFFFFF", "italic": False}
    assert prepared["coverage"]["style"] == ["bold", "fill", "italic"]


def test_unknown_parameter_is_rejected(excel_descriptor):
    with pytest.raises(ValueError, match="unknown"):
        normalize_style({"font_colour": "#000000"}, descriptor=excel_descriptor)
