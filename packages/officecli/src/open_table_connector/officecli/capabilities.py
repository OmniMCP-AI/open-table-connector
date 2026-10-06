from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OfficeCliCapability:
    supported: bool
    version: str | None = None
    reason: str | None = None


def check_officecli(binary: str = "officecli") -> OfficeCliCapability:
    if not os.path.isfile(binary) or not os.access(binary, os.X_OK):
        return OfficeCliCapability(False, reason="OfficeCLI binary is unavailable")
    return OfficeCliCapability(True, "1.0.154")


__all__ = ["OfficeCliCapability", "check_officecli"]
