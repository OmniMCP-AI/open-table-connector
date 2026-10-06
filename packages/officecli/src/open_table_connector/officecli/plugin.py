"""Lazy OfficeCLI adapter registration."""

from __future__ import annotations


def artifact_adapter():
    from .document import OfficeCliAdapter

    return OfficeCliAdapter()


__all__ = ["artifact_adapter"]
