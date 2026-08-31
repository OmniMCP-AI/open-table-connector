"""Verify the checked-in compatibility manifest and provider evidence hashes."""

from __future__ import annotations

import hashlib
import re
import sys
from collections.abc import Sequence
from pathlib import Path

MANIFEST = Path("specification/compatibility/ots-otc-timeseries-v1.files")
RECORD = Path("specification/compatibility/ots-otc-timeseries-v1.yaml")


def compute_manifest_hash(root: Path, entries: Sequence[str]) -> str:
    """Hash declared UTF-8 paths and raw bytes using unambiguous length prefixes."""
    root = root.resolve()
    normalized = sorted(entries)
    if len(normalized) != len(set(normalized)):
        raise ValueError("manifest contains duplicate paths")
    digest = hashlib.sha256()
    for entry in normalized:
        path = Path(entry)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"manifest path is outside repository: {entry}")
        target = (root / path).resolve()
        if target.is_symlink() or not target.is_file() or root not in target.parents:
            raise ValueError(f"manifest path is not a regular repository file: {entry}")
        path_bytes = entry.encode("utf-8")
        content = target.read_bytes()
        digest.update(str(len(path_bytes)).encode("ascii"))
        digest.update(b":")
        digest.update(path_bytes)
        digest.update(str(len(content)).encode("ascii"))
        digest.update(b":")
        digest.update(content)
    return f"sha256:{digest.hexdigest()}"


def _declared_entries(root: Path) -> tuple[str, ...]:
    path = root / MANIFEST
    if not path.is_file():
        raise ValueError(f"missing compatibility manifest: {MANIFEST}")
    entries = tuple(
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    return entries


def verify_compatibility(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    try:
        entries = _declared_entries(root)
        manifest_hash = compute_manifest_hash(root, entries)
    except (OSError, ValueError) as exc:
        return [str(exc)]
    record = root / RECORD
    if not record.is_file():
        return [f"missing compatibility record: {RECORD}"]
    text = record.read_text(encoding="utf-8")
    expected_match = re.search(r"^fixture_manifest_hash:\s*([^\s]+)", text, re.MULTILINE)
    if expected_match is None:
        errors.append("compatibility record is missing fixture_manifest_hash")
    elif expected_match.group(1) not in {manifest_hash, manifest_hash.removeprefix("sha256:")}:
        errors.append(
            "fixture manifest hash mismatch: "
            f"expected {expected_match.group(1)}, got {manifest_hash}"
        )
    for provider, expected in re.findall(
        r"^  - id:\s*([^\s]+)\n(?:.*\n)*?    evidence_hash:\s*([^\s]+)",
        text,
        re.MULTILINE,
    ):
        evidence = root / "specification/evidence/providers" / f"{provider}.json"
        if not evidence.is_file():
            continue
        actual = hashlib.sha256(evidence.read_bytes()).hexdigest()
        if expected not in {actual, f"sha256:{actual}"}:
            errors.append(f"provider {provider} evidence_hash mismatch")
    return errors


def main() -> int:
    errors = verify_compatibility(Path(__file__).resolve().parents[1])
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
