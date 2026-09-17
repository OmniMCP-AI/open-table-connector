"""OTC package and source-checkout version labels."""

from __future__ import annotations

import importlib.metadata
import re
import subprocess
from datetime import date
from pathlib import Path

_STABLE_VERSION = "0.1.0"
_GIT_TIMEOUT_SECONDS = 2.0


def _package_version() -> str:
    try:
        return importlib.metadata.version("open-table-connector")
    except importlib.metadata.PackageNotFoundError:
        return _STABLE_VERSION


def _repository_root() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists():
            return parent
    return None


def _git_metadata() -> tuple[str, str] | None:
    root = _repository_root()
    if root is None:
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "log", "-1", "--format=%cs%x00%h"],
            check=True,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    fields = result.stdout.strip().split("\x00")
    if len(fields) != 2:
        return None
    commit_date, short_sha = fields
    try:
        parsed_date = date.fromisoformat(commit_date)
    except ValueError:
        return None
    if parsed_date.isoformat() != commit_date or not re.fullmatch(r"[0-9a-f]{7,40}", short_sha):
        return None
    return commit_date, short_sha


def get_machine_version() -> str:
    """Return the PEP 440-compatible package version label."""

    package_version = _package_version()
    metadata = _git_metadata()
    if metadata is None:
        return package_version
    commit_date, short_sha = metadata
    return f"{package_version}+git.{commit_date.replace('-', '')}.g{short_sha}"


def get_version_label() -> str:
    """Return the human-readable OTC version label."""

    package_version = _package_version()
    metadata = _git_metadata()
    if metadata is None:
        return f"OTC {package_version} · commit metadata unavailable"
    commit_date, short_sha = metadata
    return f"OTC {package_version} · {commit_date} · {short_sha}"


__all__ = ["get_machine_version", "get_version_label"]
