"""SDK entry point for the unified workbook operation surface."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from open_table_connector.contract import TableURI

from .model import TableMode
from .result import (
    CommitState,
    ErrorCode,
    OperationResult,
    Outcome,
    Receipt,
    VerificationState,
)

if TYPE_CHECKING:
    from .client import Client


class WorkbookAccess:
    def __init__(self, client: Client) -> None:
        self._client = client

    def create(self, uri: str | TableURI, *, profile: str = "literal-artifact/1.0", limits: Any = None):
        self._client._assert_open()
        target = uri.value if isinstance(uri, TableURI) else uri
        connector = self._client._registry.connector_for(target)
        factory = getattr(connector, "workbook_create", None)
        if not callable(factory):
            raise self._client._unsupported_workbook(target, ErrorCode.UNSUPPORTED_CAPABILITY)
        session = factory(target, profile=profile, limits=limits)
        if isinstance(session, RemoteWorkbookSession):
            session._client = self._client
        return session

    def __call__(self, uri: str | TableURI, *, limits: Any = None):
        """Open an existing workbook using the concise ``client.workbook(uri)`` form."""

        return self.open(uri, limits=limits)

    def open(self, uri: str | TableURI, *, limits: Any = None):
        self._client._assert_open()
        target = uri.value if isinstance(uri, TableURI) else uri
        connector = self._client._registry.connector_for(target)
        opener = getattr(connector, "workbook_open", None)
        if not callable(opener):
            raise self._client._unsupported_workbook(target, ErrorCode.UNSUPPORTED_CAPABILITY)
        session = opener(target, limits=limits)
        if isinstance(session, RemoteWorkbookSession):
            session._client = self._client
        return session


def _remote_result(value: Any, uri: TableURI, operation: str) -> OperationResult[Any]:
    receipt = Receipt(
        kind="spreadsheet",
        operation=operation,
        connector_id="remote",
        capability=f"spreadsheet.{operation}/1.0",
        safe_target=uri,
        mode=TableMode.SHEET_MODE,
        details={"execution": "provider"},
    )
    return OperationResult(value, Outcome.SUCCEEDED, CommitState.NOT_APPLICABLE, VerificationState.UNAVAILABLE, (receipt,))


@dataclass(slots=True)
class RemoteWorkbookSession:
    """Provider-backed workbook handle used by Google Sheets and Maybe Sheet.

    Providers opt into concrete range methods.  Formula calls are delegated to
    the SDK Formula view, preserving each provider's existing dialect and
    result verification rules.
    """

    connector: Any
    uri: TableURI
    profile: str = "general/1.0"
    _client: Any = None

    @property
    def worksheet(self) -> RemoteWorksheetCollection:
        return RemoteWorksheetCollection(self)

    def write(self, **_: Any) -> OperationResult[dict[str, Any]]:
        return _remote_result({"status": "provider-committed"}, self.uri, "workbook.write")

    def verify(self) -> OperationResult[dict[str, Any]]:
        verifier = getattr(self.connector, "workbook_verify", None)
        value = verifier(self.uri) if callable(verifier) else {"status": "provider-observed"}
        return _remote_result(value, self.uri, "workbook.verify")


class RemoteWorksheetCollection:
    def __init__(self, workbook: RemoteWorkbookSession) -> None:
        self._workbook = workbook

    def create(self, name: str) -> RemoteWorksheet:
        return RemoteWorksheet(self._workbook, name)

    def get(self, name: str) -> RemoteWorksheet:
        return RemoteWorksheet(self._workbook, name)

    def __call__(self, name: str) -> RemoteWorksheet:
        return self.get(name)

    def list(self) -> tuple[str, ...]:
        lister = getattr(self._workbook.connector, "workbook_list_worksheets", None)
        if callable(lister):
            return tuple(lister(self._workbook.uri))
        return ()


class RemoteWorksheet:
    def __init__(self, workbook: RemoteWorkbookSession, name: str) -> None:
        self._workbook, self.name = workbook, name

    def range(self, address: str) -> RemoteRange:
        return RemoteRange(self._workbook, self.name, address)

    def formulas(self):
        if self._workbook._client is None:
            raise RuntimeError("remote formula views require an SDK client")
        from open_table_connector.formulas import GridFormulaTarget, WorksheetRef

        return self._workbook._client.formulas(GridFormulaTarget(self._workbook.uri, WorksheetRef(name=self.name))).require_value()


class RemoteRange:
    def __init__(self, workbook: RemoteWorkbookSession, worksheet: str, address: str) -> None:
        self._workbook, self.worksheet, self.address = workbook, worksheet, address

    def read(self) -> OperationResult[list[list[Any]]]:
        reader = getattr(self._workbook.connector, "workbook_read_range", None)
        if not callable(reader):
            raise self._unsupported("range.read")
        return _remote_result(reader(self._workbook.uri, self.worksheet, self.address), self._workbook.uri, "range.read")

    def write(self, values: Sequence[Sequence[Any]] | Sequence[Any]) -> OperationResult[None]:
        writer = getattr(self._workbook.connector, "workbook_write_range", None)
        if not callable(writer):
            raise self._unsupported("range.write")
        rows = [list(row) if isinstance(row, Sequence) and not isinstance(row, (str, bytes)) else [row] for row in values]
        writer(self._workbook.uri, self.worksheet, self.address, rows)
        return _remote_result(None, self._workbook.uri, "range.write")

    def style(self, _: Any) -> OperationResult[None]:
        raise self._unsupported("range.style")

    def format(self, _: Any) -> OperationResult[None]:
        raise self._unsupported("range.format")

    def _unsupported(self, capability: str) -> Exception:
        from .client import _failure

        return _failure("remote provider does not implement unified workbook operation", ErrorCode.UNSUPPORTED_CAPABILITY, capability=capability)


__all__ = ["RemoteWorkbookSession", "WorkbookAccess"]
