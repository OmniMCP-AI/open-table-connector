from __future__ import annotations

import pytest
from open_table_connector.conformance.formulas import load_formula_cases

from .field_cases import (
    EXPECTED_FIELD_CAPABILITIES,
    FIELD_BINDING_CASES,
    FIELD_PROVIDER_IDS,
    field_record_scenario,
    load_field_provider_cases,
)


def test_field_provider_cases_exist_for_every_matrix_provider() -> None:
    cases = load_field_provider_cases()

    assert {case.provider_id for case in cases} == set(EXPECTED_FIELD_CAPABILITIES)


def test_field_provider_cases_match_the_exact_capability_matrix() -> None:
    cases = load_formula_cases(load_field_provider_cases())
    actual = {
        case.provider_id: {capability.to_reference() for capability in case.static_capabilities}
        for case in cases
    }

    assert actual == EXPECTED_FIELD_CAPABILITIES


def test_field_matrix_excludes_creation_conversion_and_feishu_recalculation() -> None:
    assert FIELD_PROVIDER_IDS == ("maybe_sheet", "feishu_bitable")
    assert all(
        not capability.startswith("formula.field.create")
        and not capability.startswith("formula.field.convert")
        for capabilities in EXPECTED_FIELD_CAPABILITIES.values()
        for capability in capabilities
    )
    assert "formula.field.recalculate/1.0" not in EXPECTED_FIELD_CAPABILITIES["feishu_bitable"]


def test_field_binding_cases_cover_exact_name_id_missing_ambiguous_and_non_formula() -> None:
    actual = {
        case.name: (
            case.selector.name,
            case.selector.field_id,
            None if case.expected_error is None else case.expected_error.value,
            case.expected_field_id,
        )
        for case in FIELD_BINDING_CASES
    }

    assert actual == {
        "exact_name": ("gross_margin", None, None, "fld-gross-margin"),
        "exact_id": (None, "fld-gross-margin", None, "fld-gross-margin"),
        "missing": ("does_not_exist", None, "target_not_found", None),
        "ambiguous": ("duplicate", None, "invalid_target", None),
        "non_formula": ("description", None, "invalid_target", None),
    }


def test_recording_field_provider_doubles_preserve_calls_and_failure_injection(
    recording_maybe_process,
    recording_feishu_transport,
) -> None:
    process = recording_maybe_process({"formula:read": {"metadata": {"revision": "r1"}}})
    payload = process.run(
        ("mbs", "formula", "read"),
        credentials={"access_token": "fixture-token"},
        timeout=3.5,
    )

    assert payload == {"metadata": {"revision": "r1"}}
    assert process.calls[0].timeout == 3.5
    assert process.calls[0].credentials == {"access_token": "fixture-token"}

    transport = recording_feishu_transport(
        {"GET": [{"code": 0, "data": {"has_more": True}}, {"code": 0, "data": {"has_more": False}}]},
    )
    first = transport.request("GET", "https://feishu.example/fields?page_token=p1", headers={}, timeout=4)
    first["data"]["mutated"] = True
    second = transport.request("GET", "https://feishu.example/fields?page_token=p2", headers={}, timeout=4)

    assert first["data"]["mutated"] is True
    assert "mutated" not in second["data"]
    assert [request.timeout for request in transport.requests] == [4, 4]


def test_recording_field_doubles_inject_failures_and_replay_paginated_metadata_and_records(
    recording_maybe_process,
    recording_feishu_transport,
) -> None:
    process = recording_maybe_process(
        {"formula:read": {"metadata": {"revision": "r1"}}},
        failures={"formula:read": TimeoutError("fixture timeout")},
    )
    with pytest.raises(TimeoutError, match="fixture timeout"):
        process.run(("mbs", "formula", "read"), timeout=2)
    assert len(process.calls) == 1

    scenario = field_record_scenario()
    pages = (*scenario.metadata_pages, *scenario.record_pages)
    responses = [
        {
            "code": 0,
            "data": {
                "items": list(page.items),
                "has_more": page.next_page_token is not None,
                **(
                    {"page_token": page.next_page_token}
                    if page.next_page_token is not None
                    else {}
                ),
            },
        }
        for page in pages
    ]
    transport = recording_feishu_transport(
        {"GET": responses},
        failures={"GET https://feishu.example/fields?page_token=broken": RuntimeError("transport down")},
    )

    observed_items: list[dict[str, object]] = []
    for index, _page in enumerate(scenario.metadata_pages):
        url = "https://feishu.example/fields"
        if index:
            url += f"?page_token=p{index + 1}"
        observed_items.extend(transport.request("GET", url, headers={}, timeout=4)["data"]["items"])
    for index, _page in enumerate(scenario.record_pages):
        url = "https://feishu.example/records"
        if index:
            url += f"?page_token=r{index + 1}"
        observed_items.extend(transport.request("GET", url, headers={}, timeout=4)["data"]["items"])

    assert len(observed_items) == scenario.total_rows + scenario.metadata_row_count
    assert sum(page.response_bytes for page in pages) == scenario.total_response_bytes
    assert sum(page.elapsed_ms for page in pages) == scenario.total_elapsed_ms
    assert scenario.total_rows <= scenario.bounds.max_records
    assert scenario.total_response_bytes <= scenario.bounds.max_response_bytes
    assert scenario.total_elapsed_ms <= scenario.bounds.max_elapsed_ms
    assert [request.timeout for request in transport.requests] == [4] * len(pages)

    with pytest.raises(RuntimeError, match="transport down"):
        transport.request(
            "GET",
            "https://feishu.example/fields?page_token=broken",
            headers={},
            timeout=4,
        )
