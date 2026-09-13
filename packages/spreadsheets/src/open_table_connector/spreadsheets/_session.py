"""Private, provider-neutral buffering and lifecycle for workbook operations."""

from __future__ import annotations

from collections.abc import Mapping
from threading import Lock
from typing import Any

from open_table_connector.contract import CapabilityIdentity, ConnectorError, ConnectorErrorCode

from ._limits import ArtifactLimits
from ._operations import Change, freeze
from .model import SpreadsheetTarget


def _error(message: str, reason: str) -> ConnectorError:
    return ConnectorError(ConnectorErrorCode.CONFIGURATION, message, {"reason": reason})


class SpreadsheetSession:
    def __init__(
        self,
        provider: Any,
        target: SpreadsheetTarget,
        *,
        new: bool = False,
        profile: str = "general/1.0",
        limits: ArtifactLimits | None = None,
        failure_directory: Any = None,
    ):
        if profile not in {"general/1.0", "literal-artifact/1.0"}:
            raise _error("unsupported workbook profile", "unsupported_capability")
        self.provider = provider
        self.binding = dict(provider.bind(target))
        self.binding.update(
            new=new,
            profile=profile,
            limits=limits or ArtifactLimits(),
            failure_directory=failure_directory,
        )
        self.pending: tuple[Change, ...] = ()
        self.closed = self.sealed = False
        self.unresolved = None
        self._last = None
        self._lock = Lock()
        self.generations: dict[str, int] = {}
        self.expected = None
        self.provider.preflight(self.binding, ())

    def _check(self, *, mutation: bool = False):
        if self.closed:
            raise _error("workbook session is closed", "client_closed")
        if mutation and self.sealed:
            raise _error("literal artifact session is sealed", "invalid_configuration")
        if mutation and self.unresolved is not None:
            raise _error(
                "unresolved effects require reconciliation or rebind", "uncertain_mutation"
            )

    def queue(self, operation: str, sheet: str, arguments: Mapping[str, Any]):
        if not self._lock.acquire(blocking=False):
            raise _error("workbook session is writing", "invalid_configuration")
        try:
            self._check(mutation=True)
            change = Change(
                operation,
                CapabilityIdentity("spreadsheet." + operation, "1.0"),
                sheet,
                dict(arguments),
            )
            proposed = (*self.pending, change)
            self.provider.preflight(self.binding, proposed)
            self.pending = proposed
            if operation in {"worksheet.create", "worksheet.delete", "worksheet.rename"}:
                self.generations[sheet] = self.generations.get(sheet, 0) + 1
                if operation == "worksheet.rename":
                    renamed = arguments.get("name", arguments.get("new_name"))
                    if renamed != sheet:
                        self.generations[renamed] = self.generations.get(renamed, 0) + 1
            return freeze(
                {
                    "outcome": "planned",
                    "commit": "not_started",
                    "verification": "skipped",
                    "value": None,
                    "receipts": ({"operation": operation, "details": {"worksheet": sheet}},),
                }
            )
        finally:
            self._lock.release()

    def write(
        self,
        *,
        dry_run=False,
        allow_partial=False,
        expected_revision=None,
        idempotency_key=None,
        verify=True,
    ):
        if any(not isinstance(flag, bool) for flag in (dry_run, allow_partial, verify)):
            raise _error("write flags must be booleans", "invalid_configuration")
        if not self._lock.acquire(blocking=False):
            raise _error("workbook session is writing", "invalid_configuration")
        try:
            self._check()
            if self.unresolved is not None:
                raise _error(
                    "unresolved effects require reconciliation or rebind", "uncertain_mutation"
                )
            if self.sealed:
                raise _error("literal artifact session is sealed", "invalid_configuration")
            if not self.pending and self._last is not None:
                return self._last
            self.provider.preflight(self.binding, self.pending)
            if dry_run:
                return freeze(
                    {
                        "outcome": "planned",
                        "commit": "not_started",
                        "verification": "skipped",
                        "value": {"changes": len(self.pending)},
                    }
                )
            try:
                result = dict(
                    self.provider.commit(
                        self.binding,
                        self.pending,
                        allow_partial=allow_partial,
                        expected_revision=expected_revision,
                        idempotency_key=idempotency_key,
                    )
                )
            except ConnectorError as exc:
                if (
                    exc.code in {ConnectorErrorCode.TIMEOUT, ConnectorErrorCode.CANCELLED}
                    and "commit" not in exc.safe_details
                ):
                    exc = ConnectorError(
                        exc.code, exc.message, {**exc.safe_details, "commit": "unknown"}
                    )
                    self.unresolved = exc
                    raise exc
                if exc.safe_details.get("commit") == "committed":
                    self.pending = ()
                    self.unresolved = exc
                    self.sealed = self.binding["profile"] == "literal-artifact/1.0"
                if exc.safe_details.get("commit") in {"unknown", "partial"}:
                    self.unresolved = exc
                raise
            if result.get("commit") in {"unknown", "partial"}:
                self.unresolved = freeze(result)
            if result.get("commit") == "committed":
                self.binding.update(result.get("binding", {}))
                self.binding["new"] = False
                self.expected = freeze(
                    result.get("expected", self.binding.get("expected", self.expected))
                )
                self.pending = ()
                self.sealed = self.binding["profile"] == "literal-artifact/1.0"
            self._last = freeze(result)
            return self._last
        finally:
            self._lock.release()

    def observe(self, operation: str, **selector):
        if not self._lock.acquire(blocking=False):
            raise _error("workbook session is writing", "invalid_configuration")
        try:
            self._check()
            return self.provider.observe(
                self.binding, {"operation": operation, "changes": self.pending, **selector}
            )
        finally:
            self._lock.release()

    def verify(self, expected=None):
        if self.pending:
            raise _error("verification requires a clean committed session", "invalid_configuration")
        return self.observe(
            "workbook.verify", expected=self.expected if expected is None else freeze(expected)
        )

    def reconcile(self):
        result = self.observe("workbook.reconcile")
        if result.get("resolved") is True:
            self.unresolved = None
            self.pending = ()
            self.binding.update(result.get("binding", {}))
        return result

    def close(self):
        if not self._lock.acquire(blocking=False):
            raise _error("workbook session is writing", "invalid_configuration")
        try:
            self.closed = True
            self.pending = ()
        finally:
            self._lock.release()
