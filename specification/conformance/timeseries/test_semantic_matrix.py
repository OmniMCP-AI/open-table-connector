from __future__ import annotations

from open_table_connector.conformance import assert_temporal_semantics
def test_provider_matches_normalized_semantic_case(provider_semantic_case) -> None:
    _, executor, case = provider_semantic_case
    assert_temporal_semantics(executor, case)


def test_provider_support_matrix_is_explicit_and_scale_down() -> None:
    from open_table_connector.process import PORTABLE_PROVIDER_CAPABILITIES

    assert tuple(PORTABLE_PROVIDER_CAPABILITIES) == (
        "csv",
        "json",
        "jsonl",
        "sqlite",
        "postgres",
        "excel",
        "maybe_sheet",
    )
    for provider in ("csv", "json", "jsonl", "sqlite", "postgres", "excel"):
        assert "timeseries.scan.range" in PORTABLE_PROVIDER_CAPABILITIES[provider]
    assert "storage.stage" not in PORTABLE_PROVIDER_CAPABILITIES["maybe_sheet"]
    assert not any(
        capability.endswith("pushdown")
        for provider in ("csv", "json", "jsonl", "excel", "maybe_sheet")
        for capability in PORTABLE_PROVIDER_CAPABILITIES[provider]
    )
