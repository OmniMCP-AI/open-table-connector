"""Strict, provider-neutral physical layout observations and hashes."""

from __future__ import annotations

import hashlib
import json
import math
import re
from copy import deepcopy
from collections.abc import Mapping, Sequence
from typing import Any

JSON = dict[str, Any]
_OBSERVATION_KEYS = {"kind", "target", "coverage", "physical", "provenance", "physical_hash"}
_EXPECTATION_KIND = "spreadsheet.financial-layout.expectation/1.0"
_OBSERVATION_SUFFIX = ".observation/1.0"
_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("observation object keys must be strings")
        return {key: _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("observation cannot contain non-finite numbers")
        if value == 0:
            return 0
    return value


def _encode(value: Any) -> bytes:
    return json.dumps(
        _canonical(value), ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _required_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _validate_target(target: Any) -> JSON:
    if not isinstance(target, Mapping) or not target:
        raise ValueError("observation target must be a non-empty object")
    if any(not isinstance(key, str) for key in target):
        raise ValueError("observation target keys must be strings")
    for key in ("provider", "resource", "worksheet_id"):
        if key not in target:
            raise ValueError(f"observation target requires {key}")
        _required_text(target[key], f"target.{key}")
    return _canonical(dict(target))


def _validate_coverage(coverage: Any) -> JSON:
    if not isinstance(coverage, Mapping):
        raise ValueError("observation coverage must be an object")
    if coverage.get("complete") is not True:
        raise ValueError("observation coverage must be complete")
    if "fields" not in coverage or not isinstance(coverage["fields"], Sequence):
        raise ValueError("observation coverage requires fields")
    fields = list(coverage["fields"])
    if not fields or len(set(fields)) != len(fields) or any(not isinstance(field, str) or not field for field in fields):
        raise ValueError("observation coverage fields must be unique non-empty strings")
    if "range" in coverage:
        _required_text(coverage["range"], "coverage.range")
    else:
        for key in ("rows", "columns"):
            if key not in coverage or not isinstance(coverage[key], Sequence) or not coverage[key]:
                raise ValueError("config coverage requires rows and columns")
    return _canonical(dict(coverage))


def _validate_sources(physical: Mapping[str, Any]) -> None:
    sources = physical.get("sources")
    if not isinstance(sources, Mapping):
        raise ValueError("physical evidence requires sources")
    for source_id, source in sources.items():
        _required_text(source_id, "source id")
        if not isinstance(source, Mapping) or source.get("kind") not in {"explicit", "inherited", "default"}:
            raise ValueError("physical source must declare explicit, inherited, or default kind")
    cells = physical.get("cells")
    if cells is None:
        return
    if not isinstance(cells, Sequence):
        raise ValueError("physical.cells must be an array")
    seen: set[tuple[int, int]] = set()
    for cell in cells:
        if not isinstance(cell, Mapping) or type(cell.get("row")) is not int or type(cell.get("column")) is not int:
            raise ValueError("physical cell requires integer row and column")
        coordinate = (cell["row"], cell["column"])
        if min(coordinate) < 1 or coordinate in seen:
            raise ValueError("physical cells must have unique positive coordinates")
        seen.add(coordinate)
        fields = cell.get("fields")
        if not isinstance(fields, Mapping):
            raise ValueError("physical cell requires fields")
        for field, value in fields.items():
            if not isinstance(field, str) or not isinstance(value, Mapping):
                raise ValueError("physical fields must be objects")
            source_ref = value.get("source_ref")
            if source_ref not in sources:
                raise ValueError("physical field source_ref is dangling")


def _validate_observation(payload: Mapping[str, Any]) -> JSON:
    if not isinstance(payload, Mapping):
        raise ValueError("observation must be an object")
    unknown = set(payload) - _OBSERVATION_KEYS
    if unknown:
        raise ValueError(f"observation has unknown fields: {sorted(unknown)}")
    kind = _required_text(payload.get("kind"), "kind")
    if not kind.endswith(_OBSERVATION_SUFFIX):
        raise ValueError("observation kind must use version 1.0")
    target = _validate_target(payload.get("target"))
    coverage = _validate_coverage(payload.get("coverage"))
    physical = payload.get("physical")
    if not isinstance(physical, Mapping):
        raise ValueError("observation physical evidence must be an object")
    _validate_sources(physical)
    result = _canonical({"kind": kind, "target": target, "coverage": coverage, "physical": dict(physical)})
    if "provenance" in payload:
        if not isinstance(payload["provenance"], Mapping):
            raise ValueError("observation provenance must be an object")
        result["provenance"] = _canonical(dict(payload["provenance"]))
    return result


def hash_payload(payload: Mapping[str, Any]) -> JSON:
    """Return the exact physical fields that participate in a layout hash."""

    observation = _validate_observation(payload)
    return {key: observation[key] for key in ("kind", "target", "coverage", "physical")}


def physical_hash(payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(_encode(hash_payload(payload))).hexdigest()
    return f"sha256:{digest}"


def decode_observation(payload: Mapping[str, Any]) -> JSON:
    observation = _validate_observation(payload)
    digest = physical_hash(observation)
    supplied = payload.get("physical_hash")
    if supplied is not None:
        if not isinstance(supplied, str) or not _HASH_RE.fullmatch(supplied) or supplied != digest:
            raise ValueError("physical_hash does not match physical evidence")
    observation["physical_hash"] = digest
    return observation


def aggregate_observations(items: Sequence[Mapping[str, Any]]) -> JSON:
    if not items:
        raise ValueError("at least one observation is required")
    observations = [decode_observation(item) for item in items]
    keys: set[str] = set()
    for observation in observations:
        key = _encode({"target": observation["target"], "coverage": observation["coverage"]}).decode()
        if key in keys:
            raise ValueError("duplicate observation coverage")
        keys.add(key)
    revisions = {observation.get("provenance", {}).get("revision") for observation in observations}
    consistency = "single_revision" if len(revisions) == 1 and None not in revisions else "sequential_unversioned"
    result: JSON = {
        "kind": "spreadsheet.financial-layout.evidence/1.0",
        "observations": observations,
        "consistency": consistency,
    }
    result["physical_hash"] = "sha256:" + hashlib.sha256(_encode({"kind": result["kind"], "observations": [hash_payload(item) for item in observations]})).hexdigest()
    return result


def compare_layout(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> tuple[JSON, ...]:
    if not isinstance(expected, Mapping) or expected.get("kind") != _EXPECTATION_KIND:
        raise ValueError("expected layout has an invalid kind")
    observation = decode_observation(actual)
    if expected.get("target") != observation["target"]:
        raise ValueError("expected and actual target differ")
    if expected.get("coverage") != observation["coverage"]:
        raise ValueError("expected and actual coverage differ")
    required = expected.get("required_fields")
    if not isinstance(required, Sequence) or any(field not in observation["coverage"]["fields"] for field in required):
        raise ValueError("expected required_fields are not covered")
    expected_cells = expected.get("physical", {}).get("cells", [])
    actual_cells = {(cell["row"], cell["column"]): cell for cell in observation["physical"].get("cells", [])}
    differences: list[JSON] = []
    for wanted in expected_cells:
        coordinate = (wanted.get("row"), wanted.get("column"))
        actual_cell = actual_cells.get(coordinate)
        if actual_cell is None:
            differences.append({"target": observation["target"], "address_or_dimension": coordinate, "field": "cell", "expected": wanted, "actual": None})
            continue
        for field, value in wanted.get("fields", {}).items():
            actual_field = actual_cell.get("fields", {}).get(field, {})
            actual_value = actual_field.get("effective") if isinstance(actual_field, Mapping) else None
            if actual_value != value:
                differences.append({"target": observation["target"], "address_or_dimension": coordinate, "field": field, "expected": value, "actual": actual_value})
    return tuple(differences)

