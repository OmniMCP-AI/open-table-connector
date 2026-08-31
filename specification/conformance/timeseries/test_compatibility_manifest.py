from __future__ import annotations

from pathlib import Path

from scripts.verify_compatibility import compute_manifest_hash, verify_compatibility

ROOT = Path(__file__).parents[3]


def test_manifest_hash_changes_only_for_declared_files(tmp_path: Path) -> None:
    (tmp_path / "schemas").mkdir()
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "schemas/a.json").write_text("a", encoding="utf-8")
    (tmp_path / "fixtures/b.json").write_text("b", encoding="utf-8")
    entries = ("schemas/a.json", "fixtures/b.json")
    before = compute_manifest_hash(tmp_path, entries)
    (tmp_path / "README.md").write_text("unrelated", encoding="utf-8")
    assert compute_manifest_hash(tmp_path, entries) == before
    (tmp_path / "schemas/a.json").write_text("changed", encoding="utf-8")
    assert compute_manifest_hash(tmp_path, entries) != before


def test_real_compatibility_manifest_is_valid() -> None:
    assert verify_compatibility(ROOT) == []
