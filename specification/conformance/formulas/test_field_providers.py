from __future__ import annotations

from open_table_connector.conformance.formulas import load_formula_cases

from .field_cases import (
    EXPECTED_FIELD_CAPABILITIES,
    FIELD_PROVIDER_IDS,
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
