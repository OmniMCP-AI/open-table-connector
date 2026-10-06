from __future__ import annotations


def test_unqualified_binary_rejected():
    from open_table_connector.officecli.capabilities import check_officecli

    assert check_officecli("/missing/officecli").supported is False
