"""Deterministic identity helpers over canonical Arrow tables."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

import pyarrow as pa

from .identity import CapabilityIdentity, ConnectorIdentity
from .uri import TableURI


def arrow_schema_fingerprint(schema: pa.Schema) -> str:
    payload = schema.serialize().to_pybytes()
    return hashlib.sha256(payload).hexdigest()


def arrow_content_fingerprint(table: pa.Table) -> str:
    table = canonical_arrow_table(table)
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return hashlib.sha256(sink.getvalue().to_pybytes()).hexdigest()


def canonical_arrow_table(table: pa.Table) -> pa.Table:
    """Normalize record-batch chunking while preserving schema metadata."""
    if not isinstance(table, pa.Table):
        raise TypeError("table must be a pyarrow.Table")
    combined = table.combine_chunks()
    if combined.schema.metadata != table.schema.metadata:
        combined = combined.replace_schema_metadata(table.schema.metadata)
    return combined


def operation_identity(
    *,
    connector: ConnectorIdentity,
    capability: CapabilityIdentity,
    uri: TableURI,
    source_revision: str,
    schema_fingerprint: str,
    content_fingerprint: str,
    parameters: Mapping[str, Any] | None = None,
) -> str:
    payload: Mapping[str, Any] = {
        "connector": connector.to_wire(),
        "capability": capability.to_wire(),
        "uri": uri.value,
        "source_revision": source_revision,
        "schema_fingerprint": schema_fingerprint,
        "content_fingerprint": content_fingerprint,
    }
    if parameters:
        payload["parameters"] = parameters
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return "op_" + hashlib.sha256(encoded).hexdigest()
