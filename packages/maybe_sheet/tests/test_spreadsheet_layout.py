from __future__ import annotations

import pytest

from open_table_connector.maybe_sheet.spreadsheet_observe import (
    LAYOUT_DESCRIPTOR,
    config_observation,
    decode_maybe_layout,
    style_observation,
)
from open_table_connector.spreadsheets import validate_descriptor


TARGET = {"provider": "maybe", "resource": "doc", "worksheet_id": "7"}
DESCRIPTOR = {"operations": {"range.style": {"bold": {"values": [True, False]}}}}


def _observation():
    return {
        "kind": "spreadsheet.range.style.observation/1.0",
        "target": TARGET,
        "coverage": {"complete": True, "range": "A1", "fields": ["bold"]},
        "physical": {
            "cells": [{"row": 1, "column": 1, "fields": {"bold": {"effective": True, "source_ref": "s"}}}],
            "sources": {"s": {"kind": "explicit"}},
        },
    }


def test_decode_maybe_layout_validates_physical_readback():
    value = decode_maybe_layout(
        _observation(),
        target=TARGET,
        selector={"operation": "range.style.read", "fields": ["bold"]},
        descriptor=DESCRIPTOR,
    )
    assert value["physical_hash"].startswith("sha256:")


def test_decode_maybe_layout_rejects_acknowledgement_without_evidence():
    with pytest.raises(ValueError, match="observation"):
        decode_maybe_layout(
            {"success": True, "result": {"status": "committed"}},
            target=TARGET,
            selector={"operation": "range.style.read"},
            descriptor=DESCRIPTOR,
        )


def test_decode_maybe_layout_rejects_target_or_coverage_mismatch():
    payload = _observation()
    payload["target"] = {**TARGET, "worksheet_id": "8"}
    with pytest.raises(ValueError, match="target"):
        decode_maybe_layout(payload, target=TARGET, selector={}, descriptor=DESCRIPTOR)


def test_style_observation_carries_complete_per_field_provenance():
    observation = style_observation(
        target={"provider": "maybe_sheet", "resource": "doc", "worksheet_id": "7"},
        address="A1:B1",
        start=(1, 1),
        end=(1, 2),
        fields=["bold", "fill"],
        result={
            "styles": [[1, 2]],
            "style_map": {"1": {"font": 1, "alignment": 1}, "2": {"fill": 2}},
            "fonts": {"1": {"bold": True}},
            "fills": {"2": {"color": ["1F2329"], "pattern": 1}},
            "alignments": {"1": {"horizontal": "center"}},
        },
    )
    assert observation["coverage"] == {
        "complete": True,
        "range": "A1:B1",
        "fields": ["bold", "fill"],
    }
    first, second = observation["physical"]["cells"]
    assert first["fields"]["bold"]["effective"] is True
    assert first["fields"]["bold"]["source_ref"] in observation["physical"]["sources"]
    assert second["fields"]["fill"]["effective"] == {"type": "rgb", "value": "#1F2329"}
    # A style index with no fill entry reads as an unstyled default cell.
    assert second["fields"]["bold"]["effective"] is False
    assert second["fields"]["bold"]["source_ref"] in observation["physical"]["sources"]


def test_style_observation_rejects_a_matrix_that_misses_the_range():
    with pytest.raises(ValueError, match="cover"):
        style_observation(
            target={"provider": "maybe_sheet", "resource": "doc", "worksheet_id": "7"},
            address="A1:B1",
            start=(1, 1),
            end=(1, 2),
            fields=["bold"],
            result={"styles": [[1]]},
        )


def test_config_observation_marks_unset_dimensions_as_default():
    observation = config_observation(
        target={"provider": "maybe_sheet", "resource": "doc", "worksheet_id": "7"},
        rows=[1, 2],
        columns=["A", "B"],
        result={
            "formatting": {
                "column_widths": {"A": 16},
                "row_heights": {"1": 32},
                "show_gridlines": True,
                "default_row_height": 15,
            }
        },
    )
    sources = observation["physical"]["sources"]
    assert sources[observation["physical"]["columns"]["A"]["source_ref"]]["kind"] == "explicit"
    assert sources[observation["physical"]["columns"]["B"]["source_ref"]]["kind"] == "default"
    assert sources[observation["physical"]["rows"]["2"]["source_ref"]]["kind"] == "default"
    # 32 provider pixels are reported as the facade's 24 points.
    assert observation["physical"]["rows"]["1"]["height"] == 24
    assert observation["physical"]["rows"]["2"]["height"] is None


def test_layout_descriptor_is_a_valid_field_capability_descriptor():
    descriptor = validate_descriptor(LAYOUT_DESCRIPTOR)
    assert descriptor["operations"]["range.style"]["fill"]["read"] is True
    assert descriptor["operations"]["worksheet.config"]["row_heights"]["write"] is True
