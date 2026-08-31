from pathlib import Path

from scripts.check_package_boundaries import check_boundaries

ROOT = Path(__file__).resolve().parents[3]


def test_real_workspace_dependency_direction() -> None:
    assert check_boundaries(ROOT) == []
