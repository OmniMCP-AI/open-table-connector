"""Strict decoder for MaybeSheet physical layout read responses."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from open_table_connector.spreadsheets.observations import decode_observation


def decode_maybe_layout(
    payload: Mapping[str, Any],
    *,
    target: Mapping[str, Any],
    selector: Mapping[str, Any],
    descriptor: Mapping[str, Any],
) -> dict[str, Any]:
    """Decode only provider read evidence; acknowledgements are not evidence."""

    if not isinstance(payload, Mapping):
        raise ValueError("MaybeSheet layout response must be an object")
    observation = payload.get("observation", payload.get("result", payload))
    if not isinstance(observation, Mapping):
        raise ValueError("MaybeSheet layout response has no observation object")
    if observation.get("kind") not in {
        "spreadsheet.range.style.observation/1.0",
        "spreadsheet.worksheet.config.observation/1.0",
    }:
        raise ValueError("MaybeSheet response is not a layout observation")
    expected_target = dict(target)
    if observation.get("target") != expected_target:
        raise ValueError("MaybeSheet observation target does not match the bound sheet")
    coverage = observation.get("coverage")
    if not isinstance(coverage, Mapping) or coverage.get("complete") is not True:
        raise ValueError("MaybeSheet layout response is incomplete")
    fields = coverage.get("fields")
    requested = selector.get("fields") or selector.get("view_fields")
    if requested is not None and (not isinstance(fields, list) or any(item not in fields for item in requested)):
        raise ValueError("MaybeSheet layout response does not cover requested fields")
    if not isinstance(descriptor, Mapping):
        raise ValueError("MaybeSheet layout descriptor is missing")
    # A descriptor can enumerate field-level units and modes.  A response that
    # returns an unknown mode/unit is a protocol failure, never a best-effort
    # conversion.
    operations = descriptor.get("operations", descriptor)
    operation = "range.style" if observation["kind"].startswith("spreadsheet.range.style") else "worksheet.config"
    available = operations.get(operation, {}) if isinstance(operations, Mapping) else {}
    physical = observation.get("physical")
    if not isinstance(physical, Mapping):
        raise ValueError("MaybeSheet layout response has no physical evidence")
    if operation == "range.style":
        for cell in physical.get("cells", ()):
            if not isinstance(cell, Mapping) or not isinstance(cell.get("fields"), Mapping):
                raise ValueError("MaybeSheet style evidence has an invalid cell")
            for field, value in cell["fields"].items():
                spec = available.get(field, {}) if isinstance(available, Mapping) else {}
                allowed = spec.get("values") if isinstance(spec, Mapping) else None
                effective = value.get("effective") if isinstance(value, Mapping) else None
                if allowed is not None and isinstance(effective, str) and effective not in allowed:
                    raise ValueError(f"MaybeSheet response contains unsupported {field} value")
    return decode_observation(observation)


__all__ = ["decode_maybe_layout"]
