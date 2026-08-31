from __future__ import annotations

import open_table_connector.sdk as otc
import pytest


def test_all_rows_is_an_explicit_escape_hatch() -> None:
    predicate = otc.all_rows()

    assert predicate.to_wire() == {"kind": "all_rows"}
    assert otc.PortablePredicate.from_wire(predicate.to_wire()) == predicate


def test_sql_predicate_requires_an_expression() -> None:
    predicate = otc.PortablePredicate(
        expression="status = :status AND created_at < :cutoff",
        parameters={"status": "cancelled", "cutoff": "2026-08-31T00:00:00Z"},
    )

    assert predicate.to_wire() == {
        "kind": "sql",
        "expression": "status = :status AND created_at < :cutoff",
        "parameters": {"status": "cancelled", "cutoff": "2026-08-31T00:00:00Z"},
    }

    with pytest.raises(ValueError, match="expression"):
        otc.PortablePredicate(expression="  ")
