from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from open_table_connector.contract import TableURI

CONTRACT = "otc.mobile.table/1.0"
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
MAX_FIELDS = 50
MAX_PATCH_FIELDS = 10
MAX_PATCH_BYTES = 16 * 1024


@dataclass(frozen=True, slots=True)
class MobileRequestEnvelope:
    contract: str
    request_id: str
    table_uri: str

    def to_wire(self) -> dict[str, str]:
        return {"contract": self.contract, "request_id": self.request_id, "table_uri": self.table_uri}


def parse_request(payload: Mapping[str, object], allowed_keys: frozenset[str]) -> MobileRequestEnvelope:
    if not isinstance(payload, Mapping):
        raise TypeError("request must be an object")
    unknown = set(payload) - set(allowed_keys)
    if unknown:
        raise ValueError(f"unknown request field: {sorted(unknown)[0]}")
    contract = payload.get("contract")
    request_id = payload.get("request_id")
    table_uri = payload.get("table_uri")
    if contract != CONTRACT:
        raise ValueError("unsupported mobile table contract")
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("request_id must be a non-empty string")
    if not isinstance(table_uri, str):
        raise ValueError("table_uri must be a string")
    try:
        safe_uri = TableURI(table_uri).value
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid table_uri: {exc}") from exc
    return MobileRequestEnvelope(CONTRACT, request_id.strip(), safe_uri)


def validate_field_selection(fields: Sequence[str]) -> tuple[str, ...]:
    if isinstance(fields, (str, bytes, bytearray)):
        raise TypeError("fields must be an array")
    result = tuple(fields)
    if len(result) > MAX_FIELDS:
        raise ValueError("a request may select at most 50 fields")
    if any(not isinstance(field, str) or not field.strip() for field in result):
        raise ValueError("field IDs must be non-empty strings")
    if len(set(result)) != len(result):
        raise ValueError("field IDs must be unique")
    return result


def _safe_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _safe_json(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_safe_json(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError("patch values must be JSON-compatible")


def validate_patch_size(patch: Mapping[str, object]) -> dict[str, Any]:
    if not isinstance(patch, Mapping):
        raise TypeError("patch must be an object")
    if len(patch) > MAX_PATCH_FIELDS:
        raise ValueError("a record patch may contain at most 10 fields")
    clean = _safe_json(patch)
    encoded = json.dumps(clean, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(encoded) > MAX_PATCH_BYTES:
        raise ValueError("a record patch must be at most 16 KiB")
    return clean
