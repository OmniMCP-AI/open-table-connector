from __future__ import annotations

import pyarrow as pa
from open_table_connector.timeseries import build_arrow_evidence


def test_build_arrow_evidence_serializes_and_hashes_one_table() -> None:
    table = pa.table({"id": ["a", "b"]})
    evidence = build_arrow_evidence(table)
    assert evidence.table.equals(table)
    assert evidence.ipc_bytes
    assert len(evidence.schema_fingerprint) == 64
    assert len(evidence.content_fingerprint) == 64
