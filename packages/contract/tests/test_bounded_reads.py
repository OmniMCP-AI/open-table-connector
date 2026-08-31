from __future__ import annotations

import pytest
from open_table_connector.contract import (
    BaseConvention,
    BoundedTableReadRequest,
    ConnectorIdentity,
    NeutralReceipt,
    ReadExtent,
    TableMode,
    TableURI,
)
from open_table_connector.contract.bounded_reads import BoundedReadReceipt


def test_bounded_request_requires_positive_output_limit() -> None:
    with pytest.raises(ValueError):
        BoundedTableReadRequest(TableURI("file:///tmp/data.csv"), max_output_rows=0)


def test_truncated_receipt_is_not_a_neutral_v1_receipt() -> None:
    receipt = BoundedReadReceipt(
        connector=ConnectorIdentity("local_files", "0.1.0", "1.0"),
        safe_uri=TableURI("file:///tmp/data.csv"),
        mode=TableMode.BASE,
        source_snapshot_reference=None,
        schema_fingerprint="a" * 64,
        emitted_content_fingerprint="b" * 64,
        coordinate_convention=BaseConvention(ordinal_snapshot_id="snapshot"),
        rows_emitted=2,
        batches_emitted=1,
        extent=ReadExtent.TRUNCATED,
    )
    with pytest.raises(ValueError):
        NeutralReceipt.from_wire(receipt.to_wire())
