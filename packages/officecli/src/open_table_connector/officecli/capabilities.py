from __future__ import annotations

import os
import re
from dataclasses import dataclass

from .process import run_officecli


@dataclass(frozen=True, slots=True)
class OfficeCliCapability:
    supported: bool
    version: str | None = None
    reason: str | None = None
    modes: tuple[str, ...] = ()
    formats: tuple[str, ...] = ("docx", "pptx", "xlsx")
    browser: str | None = None


def check_officecli(binary: str = "officecli", *, renderer: str = "html", browser: str | None = None) -> OfficeCliCapability:
    if not os.path.isfile(binary) or not os.access(binary, os.X_OK):
        return OfficeCliCapability(False, reason="OfficeCLI binary is unavailable")
    try:
        result = run_officecli([binary, "--version"], input_json=None, timeout_seconds=5, max_output_bytes=4096)
    except OSError:
        return OfficeCliCapability(False, reason="OfficeCLI version probe failed")
    match = re.search(r"\b1\.0\.154\b", result.stdout)
    if result.returncode or result.truncated or result.timed_out or not match:
        return OfficeCliCapability(False, reason="OfficeCLI version is not qualified (requires 1.0.154)")
    modes = ("html", "text", "outline", "stats", "issues", "watch")
    browser_ready = bool(browser and os.path.isfile(browser) and os.access(browser, os.X_OK))
    if browser_ready:
        modes += ("screenshot",)
    if renderer not in modes:
        return OfficeCliCapability(False, "1.0.154", "qualified browser is required for screenshot rendering", modes, browser=browser)
    return OfficeCliCapability(True, "1.0.154", modes=modes, browser=browser if browser_ready else None)


__all__ = ["OfficeCliCapability", "check_officecli"]
