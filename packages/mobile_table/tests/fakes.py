from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import open_table_connector.sdk as otc
from open_table_connector.contract import TableURI
from open_table_connector.mobile_table.models import (
    MobileCapabilities,
    MobileInspection,
    MobileReadPage,
    MobileUpdateResult,
)
from open_table_connector.mobile_table.validation import CONTRACT

from .conftest import load_fixture


def success(value: Any) -> otc.OperationResult[Any]:
    return otc.OperationResult(
        value=value,
        outcome=otc.Outcome.SUCCEEDED,
        commit=otc.CommitState.COMMITTED,
        verification=otc.VerificationState.PASSED,
        receipts=(),
    )


def rejected(code: otc.ErrorCode, message: str = "rejected", details: dict[str, Any] | None = None):
    return otc.OperationResult(
        value=None,
        outcome=otc.Outcome.REJECTED,
        commit=otc.CommitState.NOT_STARTED,
        verification=otc.VerificationState.SKIPPED,
        receipts=(),
        error=otc.ErrorInfo(code, message, details or {}),
    )


@dataclass
class FakeMobileHost:
    capabilities_result: otc.OperationResult[MobileCapabilities] | None = None
    inspect_result: otc.OperationResult[MobileInspection] | None = None
    read_result: otc.OperationResult[MobileReadPage] | None = None
    update_result: otc.OperationResult[MobileUpdateResult] | None = None
    calls: list[tuple[str, Any]] = field(default_factory=list)

    def capabilities(self, table_uri: TableURI):
        self.calls.append(("capabilities", table_uri.value))
        return self.capabilities_result or success(MobileCapabilities.from_wire(load_fixture("capabilities-supported.json")))

    def inspect(self, table_uri: TableURI, fields: tuple[str, ...] | None):
        self.calls.append(("inspect", (table_uri.value, fields)))
        return self.inspect_result or success(MobileInspection.from_wire(load_fixture("inspect-base.json")))

    def read(self, table_uri: TableURI, *, page_size: int, page_token: str | None, fields: tuple[str, ...]):
        self.calls.append(("read", (table_uri.value, page_size, page_token, fields)))
        return self.read_result or success(MobileReadPage.from_wire(load_fixture("read-first-page.json")))

    def update(self, table_uri: TableURI, request):
        self.calls.append(("update", (table_uri.value, request)))
        return self.update_result or success(MobileUpdateResult.from_wire(load_fixture("update-success.json")))


def supported_capabilities() -> MobileCapabilities:
    return MobileCapabilities.from_wire(load_fixture("capabilities-supported.json"))


def unknown_capabilities() -> MobileCapabilities:
    return MobileCapabilities.from_wire(load_fixture("capabilities-unknown.json"))


assert CONTRACT == "otc.mobile.table/1.0"
