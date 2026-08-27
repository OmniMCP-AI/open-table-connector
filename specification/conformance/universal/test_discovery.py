from __future__ import annotations

import pytest

from specification.conformance.universal.cases import all_cases, case


def test_all_current_connectors_have_named_cases() -> None:
    assert {item.name for item in all_cases()} == {
        "local_files",
        "google_sheets",
        "feishu_bitable",
        "maybesheet",
        "sqlite",
        "postgres",
        "dbt",
    }


def test_case_lookup_rejects_unknown_connector() -> None:
    with pytest.raises(KeyError, match="unknown connector case"):
        case("missing")
