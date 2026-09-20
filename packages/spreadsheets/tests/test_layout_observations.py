from copy import deepcopy
import hashlib
import json

import pytest


def _observation():
    return {
        "kind": "spreadsheet.range.style.observation/1.0",
        "target": {"provider": "excel", "resource": "book.xlsx", "worksheet_id": "7"},
        "coverage": {
            "range": "A1:B1",
            "fields": ["bold", "number_format"],
            "complete": True,
        },
        "physical": {
            "sources": {
                "s1": {"kind": "explicit", "origin": "cellXf:3"},
                "s2": {"kind": "default", "origin": "worksheet"},
            },
            "cells": [
                {
                    "row": 1,
                    "column": 1,
                    "fields": {
                        "bold": {"source": "explicit", "source_ref": "s1", "stored": True, "effective": True},
                        "number_format": {"source": "default", "source_ref": "s2", "stored": None, "effective": {"code": "General"}},
                    },
                },
                {
                    "row": 1,
                    "column": 2,
                    "fields": {
                        "bold": {"source": "default", "source_ref": "s2", "stored": None, "effective": False},
                        "number_format": {"source": "explicit", "source_ref": "s1", "stored": {"code": "#,##0.00", "storage_kind": "custom"}, "effective": {"code": "#,##0.00", "storage_kind": "custom"}},
                    },
                },
            ],
        },
        "provenance": {"provider_version": "test", "request_id": "request-1"},
    }


def test_request_metadata_does_not_affect_physical_hash():
    from open_table_connector.spreadsheets.observations import physical_hash

    observation = _observation()
    payload = {k: observation[k] for k in ("kind", "target", "coverage", "physical")}
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    expected = "sha256:" + hashlib.sha256(encoded).hexdigest()
    altered = deepcopy(observation)
    altered["provenance"]["request_id"] = "new-request"
    assert physical_hash(observation) == physical_hash(altered) == expected


def test_decode_rejects_bad_hash_and_dangling_sources():
    from open_table_connector.spreadsheets.observations import decode_observation

    bad_hash = {**_observation(), "physical_hash": "sha256:" + "0" * 64}
    with pytest.raises(ValueError, match="physical_hash"):
        decode_observation(bad_hash)
    dangling = deepcopy(_observation())
    dangling["physical"]["cells"][0]["fields"]["bold"]["source_ref"] = "missing"
    with pytest.raises(ValueError, match="source_ref"):
        decode_observation(dangling)


def test_compare_layout_requires_same_target_and_reports_field_diff():
    from open_table_connector.spreadsheets.observations import compare_layout

    actual = _observation()
    expected = {
        "kind": "spreadsheet.financial-layout.expectation/1.0",
        "target": actual["target"],
        "coverage": actual["coverage"],
        "required_fields": ["bold"],
        "physical": {"cells": [{"row": 1, "column": 1, "fields": {"bold": True}}]},
    }
    assert compare_layout(expected, actual) == ()
    changed = deepcopy(actual)
    changed["physical"]["cells"][0]["fields"]["bold"]["effective"] = False
    differences = compare_layout(expected, changed)
    assert differences[0]["field"] == "bold"
    other_target = deepcopy(expected)
    other_target["target"] = {"provider": "excel", "resource": "other.xlsx", "worksheet_id": "7"}
    with pytest.raises(ValueError, match="target"):
        compare_layout(other_target, actual)


def test_aggregate_rejects_duplicate_coverage_and_marks_unversioned():
    from open_table_connector.spreadsheets.observations import aggregate_observations

    first = _observation()
    second = deepcopy(first)
    second["provenance"]["revision"] = "r2"
    with pytest.raises(ValueError, match="duplicate"):
        aggregate_observations([first, second])
    second["coverage"] = {"range": "C1:D1", "fields": ["bold", "number_format"], "complete": True}
    result = aggregate_observations([first, second])
    assert result["consistency"] == "sequential_unversioned"
    assert len(result["observations"]) == 2

