"""Closed manifest loader for cross-framework conformance cases."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_COMPARISONS = frozenset(
    {
        "arrow_schema",
        "polars_schema",
        "nulls",
        "row_order",
        "coordinate_convention",
        "source_revision",
        "content_fingerprint",
        "receipt_facts",
    }
)


@dataclass(frozen=True)
class ManifestCase:
    id: str
    source: Path
    expected: Path
    expected_mode: str


def load_manifest(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    required = {"schema_version", "connector", "fixtures", "comparisons"}
    if set(document) != required:
        raise ValueError("cross-framework manifest keys are not closed")
    if document["schema_version"] != "otc.cross-framework-manifest/v1":
        raise ValueError("unsupported cross-framework manifest version")
    if not isinstance(document["fixtures"], list) or not document["fixtures"]:
        raise ValueError("manifest fixtures must be a non-empty list")
    if (
        not isinstance(document["comparisons"], list)
        or not set(document["comparisons"]) <= _COMPARISONS
    ):
        raise ValueError("manifest contains an unsupported comparison")
    ids: set[str] = set()
    root = path.parent
    for item in document["fixtures"]:
        if set(item) != {"id", "source", "expected", "expected_mode"}:
            raise ValueError("fixture keys are not closed")
        if item["id"] in ids:
            raise ValueError(f"duplicate fixture id: {item['id']}")
        ids.add(item["id"])
        for key in ("source", "expected"):
            candidate = root / str(item[key])
            if not candidate.is_file() or candidate.is_symlink():
                raise ValueError(f"missing fixture artifact: {item[key]}")
    return document


def collected_cases(path: Path) -> tuple[ManifestCase, ...]:
    document = load_manifest(path)
    root = path.parent
    return tuple(
        ManifestCase(
            id=item["id"],
            source=root / item["source"],
            expected=root / item["expected"],
            expected_mode=item["expected_mode"],
        )
        for item in document["fixtures"]
    )
