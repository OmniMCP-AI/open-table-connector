from __future__ import annotations

from open_table_connector.conformance.formulas import load_formula_cases

from .grid_cases import (
    EXPECTED_GRID_CAPABILITIES,
    GRID_PROVIDER_IDS,
    load_grid_provider_cases,
)
from .support import (
    RecordingProcessClient,
    RecordingSheetsTransport,
    RecordingWorkbookFactory,
)


def test_grid_provider_cases_match_the_capability_selected_matrix() -> None:
    cases = load_formula_cases(load_grid_provider_cases())
    actual = {
        case.provider_id: {capability.to_reference() for capability in case.static_capabilities}
        for case in cases
    }

    assert actual == EXPECTED_GRID_CAPABILITIES


def test_capability_matrix_is_exactly_the_planned_grid_surface() -> None:
    assert GRID_PROVIDER_IDS == ("google_sheets", "maybe_sheet", "excel")
    assert {
        "google_sheets": {
            "formula.grid.read/1.0",
            "formula.grid.set/1.0",
            "formula.grid.values.read/1.0",
        },
        "maybe_sheet": {
            "formula.grid.read/1.0",
            "formula.grid.set/1.0",
            "formula.grid.values.read/1.0",
            "formula.grid.recalculate/1.0",
        },
        "excel": {
            "formula.grid.read/1.0",
            "formula.grid.set/1.0",
        },
    } == EXPECTED_GRID_CAPABILITIES


def test_recording_provider_doubles_preserve_calls_and_return_copied_payloads() -> None:
    sheets = RecordingSheetsTransport({"GET": [{"cells": [1]}, {"cells": [1]}]})
    first = sheets.request("GET", "https://sheets.example/grid", headers={}, timeout=7)
    first["cells"].append(2)
    second = sheets.request("GET", "https://sheets.example/grid", headers={}, timeout=7)

    assert first == {"cells": [1, 2]}
    assert second == {"cells": [1]}
    assert sheets.requests[0].method == "GET"
    assert sheets.requests[0].timeout == 7

    process = RecordingProcessClient({"formula:read": {"result": {"ok": True}}})
    payload = process.run(
        ("mbs", "formula", "read"),
        credentials={"access_token": "fixture-token"},
        timeout=3.5,
    )
    assert payload == {"result": {"ok": True}}
    assert process.calls[0].argv == ("mbs", "formula", "read")
    assert process.calls[0].credentials == {"access_token": "fixture-token"}
    assert process.calls[0].timeout == 3.5

    workbook = object()
    factory = RecordingWorkbookFactory(workbook)
    assert factory("/tmp/fixture.xlsx", data_only=False) is workbook
    assert factory.opens[0].path == "/tmp/fixture.xlsx"
    assert factory.opens[0].options == {"data_only": False}
