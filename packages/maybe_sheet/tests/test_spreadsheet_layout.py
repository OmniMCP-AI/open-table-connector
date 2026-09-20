from __future__ import annotations

import pytest

from open_table_connector.maybe_sheet.spreadsheet_observe import decode_maybe_layout


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
