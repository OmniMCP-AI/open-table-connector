from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path
from typing import Any, NamedTuple

from open_table_connector.contract import PROVIDER_FEISHU_BITABLE, PROVIDER_GOOGLE_SHEETS

_INTERNAL_PREFIX = "open-table-connector-"
_INTERNAL_RANGE = ">=0.1,<0.2"
_HOSTED_CONNECTORS = (PROVIDER_GOOGLE_SHEETS, PROVIDER_FEISHU_BITABLE)


class PackageMetadata(NamedTuple):
    name: str
    requires_python: str
    dependencies: tuple[str, ...]
    dependency_ranges: dict[str, str]
    license: str | None
    workspace_sources: frozenset[str]


def _canonical_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _requirement_parts(requirement: str) -> tuple[str, str]:
    match = re.match(r"^([A-Za-z0-9_.-]+)(.*)$", requirement.strip())
    if match is None:
        raise ValueError(f"invalid dependency requirement: {requirement!r}")
    return _canonical_name(match.group(1)), match.group(2).strip()


def package_metadata(path: Path) -> PackageMetadata:
    document = tomllib.loads(path.read_text(encoding="utf-8"))
    project = document.get("project", {})
    ranges: dict[str, str] = {}
    for requirement in project.get("dependencies", []):
        name, specifier = _requirement_parts(str(requirement))
        ranges[name] = specifier

    raw_license = project.get("license")
    license_name = raw_license.get("text") if isinstance(raw_license, dict) else raw_license

    raw_sources: dict[str, Any] = document.get("tool", {}).get("uv", {}).get(
        "sources", {}
    )
    workspace_sources = frozenset(
        _canonical_name(name)
        for name, source in raw_sources.items()
        if isinstance(source, dict) and source.get("workspace") is True
    )
    return PackageMetadata(
        name=_canonical_name(str(project.get("name", ""))),
        requires_python=str(project.get("requires-python", "")),
        dependencies=tuple(ranges),
        dependency_ranges=ranges,
        license=str(license_name) if license_name is not None else None,
        workspace_sources=workspace_sources,
    )


def _runtime_ranges(path: Path) -> dict[str, str]:
    ranges: dict[str, str] = {}
    in_runtime_ranges = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line == "runtime_ranges:":
            in_runtime_ranges = True
            continue
        if in_runtime_ranges and line and not line.startswith("  "):
            break
        if in_runtime_ranges:
            match = re.match(r'^  ([a-z_]+):\s+"([^"]+)"$', line)
            if match is not None:
                ranges[match.group(1)] = match.group(2)
    return ranges


def check_package_metadata(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    root_document = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    if root_document.get("tool", {}).get("uv", {}).get("package") is not False:
        errors.append("workspace: root must set [tool.uv] package = false")
    for forbidden_table in ("build-system", "project"):
        if forbidden_table in root_document:
            errors.append(f"workspace: root must not define [{forbidden_table}]")

    support = root_document.get("tool", {}).get("otc", {}).get("support", {})
    expected_support = {
        "python": ">=3.11,<3.15",
        "pyarrow": ">=14,<20",
        "polars": ">=1,<2",
    }
    for name, expected in expected_support.items():
        actual = support.get(name)
        if actual != expected:
            errors.append(
                f"workspace: {name} support range must be {expected!r}, got {actual!r}"
            )

    members = root_document.get("tool", {}).get("uv", {}).get("workspace", {}).get(
        "members", []
    )
    metadata_by_member: dict[str, PackageMetadata] = {}
    for member in members:
        pyproject = root / str(member) / "pyproject.toml"
        if not pyproject.is_file():
            errors.append(f"{member}: missing pyproject.toml")
            continue
        metadata = package_metadata(pyproject)
        metadata_by_member[str(member)] = metadata
        project_document = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        if project_readme := project_document.get("project", {}).get("readme"):
            readme_name = str(project_readme)
        else:
            readme_name = "README.md"
        if not (pyproject.parent / readme_name).is_file():
            errors.append(f"{metadata.name}: missing README.md")
        package_dir = pyproject.parent.name
        typed_marker = pyproject.parent / "src" / "open_table_connector" / package_dir / "py.typed"
        if not typed_marker.is_file():
            errors.append(f"{metadata.name}: missing py.typed")
        if metadata.requires_python != expected_support["python"]:
            errors.append(
                f"{metadata.name}: requires-python must be {expected_support['python']!r}"
            )
        if metadata.license != "Apache-2.0":
            errors.append(f"{metadata.name}: license must be 'Apache-2.0'")
        for dependency, specifier in metadata.dependency_ranges.items():
            if dependency.startswith(_INTERNAL_PREFIX):
                if specifier != _INTERNAL_RANGE:
                    errors.append(
                        f"{metadata.name}: {dependency} range must be {_INTERNAL_RANGE!r}"
                    )
                if dependency not in metadata.workspace_sources:
                    errors.append(
                        f"{metadata.name}: {dependency} must be a workspace source"
                    )
            elif dependency in ("pyarrow", "polars"):
                expected = expected_support[dependency]
                if specifier != expected:
                    errors.append(
                        f"{metadata.name}: {dependency} range must be {expected!r}"
                    )

    for package in _HOSTED_CONNECTORS:
        hosted_metadata = metadata_by_member.get(f"packages/{package}")
        if hosted_metadata is None:
            errors.append(f"{package}: missing workspace package")
            continue
        for dependency in ("open-table-connector-contract", "polars", "pyarrow"):
            if dependency not in hosted_metadata.dependencies:
                errors.append(f"{hosted_metadata.name}: missing dependency {dependency}")

    compatibility = _runtime_ranges(
        root / "specification/compatibility/ots-otc-timeseries-v1.yaml"
    )
    for name, expected in expected_support.items():
        actual = compatibility.get(name)
        if actual != expected:
            errors.append(
                f"compatibility: {name} range must be {expected!r}, got {actual!r}"
            )
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = check_package_metadata(root)
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
