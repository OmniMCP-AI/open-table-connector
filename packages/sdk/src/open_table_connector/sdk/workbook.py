"""SDK entry point for the unified workbook operation surface."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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

    def create(
        self,
        uri: str | TableURI,
        *,
        profile: str | None = None,
        limits: Any = None,
        failure_directory: Any = None,
    ):
        self._client._assert_open()
        target = uri.value if isinstance(uri, TableURI) else uri
        connector = self._client._registry.connector_for(target)
        provider = getattr(connector, "spreadsheet_provider", None)
        if callable(provider):
            return WorkbookSession(
                self._client,
                provider(),
                target,
                new=True,
                profile=profile
                or ("literal-artifact/1.0" if target.startswith("file:") else "general/1.0"),
                limits=limits,
                failure_directory=failure_directory,
            )
        factory = getattr(connector, "workbook_create", None)
        if not callable(factory):
            raise self._client._unsupported_workbook(target, ErrorCode.UNSUPPORTED_CAPABILITY)
        session = factory(target, profile=profile or "literal-artifact/1.0", limits=limits)
        if isinstance(session, RemoteWorkbookSession):
            session._client = self._client
        return session

    def __call__(self, uri: str | TableURI, *, limits: Any = None, profile: str = "general/1.0"):
        """Open an existing workbook using the concise ``client.workbook(uri)`` form."""

        return self.open(uri, limits=limits, profile=profile)

    def open(self, uri: str | TableURI, *, limits: Any = None, profile: str = "general/1.0"):
        self._client._assert_open()
        target = uri.value if isinstance(uri, TableURI) else uri
        connector = self._client._registry.connector_for(target)
        provider = getattr(connector, "spreadsheet_provider", None)
        if callable(provider):
            return WorkbookSession(self._client, provider(), target, limits=limits, profile=profile)
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
    return OperationResult(
        value,
        Outcome.SUCCEEDED,
        CommitState.NOT_APPLICABLE,
        VerificationState.UNAVAILABLE,
        (receipt,),
    )


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

        return self._workbook._client.formulas(
            GridFormulaTarget(self._workbook.uri, WorksheetRef(name=self.name))
        ).require_value()


class RemoteRange:
    def __init__(self, workbook: RemoteWorkbookSession, worksheet: str, address: str) -> None:
        self._workbook, self.worksheet, self.address = workbook, worksheet, address

    def read(self) -> OperationResult[list[list[Any]]]:
        reader = getattr(self._workbook.connector, "workbook_read_range", None)
        if not callable(reader):
            raise self._unsupported("range.read")
        return _remote_result(
            reader(self._workbook.uri, self.worksheet, self.address),
            self._workbook.uri,
            "range.read",
        )

    def write(self, values: Sequence[Sequence[Any]] | Sequence[Any]) -> OperationResult[None]:
        writer = getattr(self._workbook.connector, "workbook_write_range", None)
        if not callable(writer):
            raise self._unsupported("range.write")
        rows = [
            list(row) if isinstance(row, Sequence) and not isinstance(row, (str, bytes)) else [row]
            for row in values
        ]
        writer(self._workbook.uri, self.worksheet, self.address, rows)
        return _remote_result(None, self._workbook.uri, "range.write")

    def style(self, _: Any) -> OperationResult[None]:
        raise self._unsupported("range.style")

    def format(self, _: Any) -> OperationResult[None]:
        raise self._unsupported("range.format")

    def _unsupported(self, capability: str) -> Exception:
        from .client import _failure

        return _failure(
            "remote provider does not implement unified workbook operation",
            ErrorCode.UNSUPPORTED_CAPABILITY,
            capability=capability,
        )


__all__ = ["RemoteWorkbookSession", "WorkbookAccess"]


def _adapt(value, uri, operation):
    from .result import ErrorInfo, OTCError

    outcome = Outcome(value.get("outcome", "succeeded"))
    commit = CommitState(value.get("commit", "not_applicable"))
    verification = VerificationState(value.get("verification", "unavailable"))
    receipts = tuple(
        Receipt(
            kind=item.get("kind", "spreadsheet"),
            operation=item.get("operation", operation),
            connector_id=item.get("connector_id"),
            capability=item.get("capability"),
            safe_target=uri,
            mode=TableMode.SHEET_MODE,
            details=item.get(
                "details",
                {
                    key: detail
                    for key, detail in item.items()
                    if key
                    not in {
                        "kind",
                        "operation",
                        "connector_id",
                        "capability",
                        "safe_target",
                        "mode",
                    }
                },
            ),
        )
        for item in value.get("receipts", ())
    )
    error = None
    if outcome not in {Outcome.SUCCEEDED, Outcome.PLANNED}:
        payload = value.get("error") or {}
        error = ErrorInfo(
            ErrorCode(
                payload.get(
                    "code",
                    {Outcome.UNKNOWN: "uncertain_mutation", Outcome.PARTIAL: "partial_effect"}.get(
                        outcome, "execution_failed"
                    ),
                )
            ),
            payload.get("message", "workbook operation failed"),
            payload.get("safe_details", {}),
        )
    result = OperationResult(
        value.get("value"), outcome, commit, verification, receipts, error=error
    )
    if error is not None:
        raise OTCError(error.message, result)
    return result


class WorkbookSession:
    """SDK resource facade over the provider-neutral buffered session."""

    def __init__(self, client, provider, target, **kwargs):
        from open_table_connector.spreadsheets import SpreadsheetTarget
        from open_table_connector.spreadsheets._session import SpreadsheetSession

        self._client = client
        self.uri = TableURI(target)
        self._session = self._call(
            lambda: SpreadsheetSession(provider, SpreadsheetTarget(target), **kwargs)
        )
        self.profile = self._session.binding["profile"]
        self.uri = TableURI(self._session.binding.get("uri", target))

    def _call(self, call):
        from open_table_connector.contract import ConnectorError

        from .client import _failure

        self._client._assert_open()
        try:
            return call()
        except ConnectorError as exc:
            aliases = {
                "invalid_uri": "invalid_target",
                "configuration": "invalid_configuration",
                "conflict": "stale_revision",
                "resource_limit_exceeded": "resource_limit",
                "protocol_invalid": "protocol_failure",
                "literal_formula": "artifact_integrity",
            }
            reason = exc.safe_details.get("reason", exc.code.value)
            try:
                code = ErrorCode(aliases.get(reason, reason))
            except ValueError:
                try:
                    code = ErrorCode(aliases.get(exc.code.value, exc.code.value))
                except ValueError:
                    code = ErrorCode.EXECUTION_FAILED
            state = exc.safe_details.get("commit")
            if state in {"committed", "partial", "unknown", "not_committed"}:
                from .result import ErrorInfo, OTCError

                outcome = {"partial": Outcome.PARTIAL, "unknown": Outcome.UNKNOWN}.get(
                    state, Outcome.FAILED
                )
                verification = (
                    VerificationState.UNAVAILABLE
                    if state == "unknown"
                    else VerificationState.FAILED
                )
                result: OperationResult[Any] = OperationResult(
                    None,
                    outcome,
                    CommitState(state),
                    verification,
                    (),
                    error=ErrorInfo(code, exc.message, exc.safe_details),
                )
                raise OTCError(exc.message, result) from exc
            raise _failure(exc.message, code, **exc.safe_details) from exc
        except (ValueError, TypeError) as exc:
            raise _failure(str(exc), ErrorCode.INVALID_TARGET) from exc

    def _assert_generation(self, sheet, generation):
        if self._session.generations.get(sheet, 0) != generation:
            from .client import _failure

            raise _failure(
                "worksheet handle is stale after a structural edit", ErrorCode.STALE_REVISION
            )

    def _queue(self, operation, sheet, arguments):
        return _adapt(
            self._call(lambda: self._session.queue(operation, sheet, arguments)),
            self.uri,
            operation,
        )

    @property
    def capabilities(self):
        return tuple(self._session.binding.get("capabilities", ()))

    @property
    def worksheet(self):
        return WorksheetCollection(self)

    def write(self, **kwargs):
        try:
            value = self._call(lambda: self._session.write(**kwargs))
        finally:
            self.uri = TableURI(self._session.binding.get("uri", self.uri.value))
        return _adapt(value, self.uri, "workbook.write")

    def verify(self, expected=None):
        return _adapt(
            self._call(lambda: self._session.verify(expected)), self.uri, "workbook.verify"
        )

    def reconcile(self):
        return _adapt(self._call(self._session.reconcile), self.uri, "workbook.reconcile")

    def inspect(self):
        return _adapt(
            self._call(lambda: self._session.observe("workbook.inspect")),
            self.uri,
            "workbook.inspect",
        )

    def close(self):
        self._session.close()

    def __enter__(self):
        self._call(self._session._check)
        return self

    def __exit__(self, *_):
        self.close()


class WorksheetCollection:
    def __init__(self, book):
        self._book = book

    def __call__(self, name):
        return self.get(name)

    def get(self, name):
        return Worksheet(self._book, name)

    def create(self, name):
        result = self._book._queue("worksheet.create", name, {})
        return Worksheet(self._book, name, result)

    def list(self):
        result = self._book._call(lambda: self._book._session.observe("worksheet.list"))
        value = result.get("value", result.get("worksheets", ()))
        if isinstance(value, Mapping):
            value = value.get("worksheets", ())
        return tuple(
            item.get("name", item.get("title")) if isinstance(item, Mapping) else item
            for item in value
        )


class Worksheet:
    def __init__(self, book, name, result=None):
        self._book, self.name, self._result = book, name, result
        self._generation = book._session.generations.get(name, 0)

    def _queue(self, operation, sheet, arguments):
        self._book._assert_generation(self.name, self._generation)
        return self._book._queue(operation, sheet, arguments)

    def with_results(self):
        return self._result

    def range(self, address):
        self._book._assert_generation(self.name, self._generation)
        from open_table_connector.spreadsheets import RangeRef

        return Range(self._book, self.name, self._book._call(lambda: RangeRef(address).address))

    def formulas(self):
        self._book._assert_generation(self.name, self._generation)
        return FormulaCollection(self._book, self.name)

    def delete(self):
        return self._queue("worksheet.delete", self.name, {})

    def rename(self, name):
        result = self._queue("worksheet.rename", self.name, {"name": name})
        self.name = name
        self._generation = self._book._session.generations.get(name, 0)
        return result

    def config(self, **kwargs):
        return self._queue("worksheet.config", self.name, kwargs)

    configure = config

    def read_config(self, *, rows, columns, view_fields=None):
        self._book._assert_generation(self.name, self._generation)
        value = self._book._call(
            lambda: self._book._session.observe(
                "worksheet.config.read",
                target_key=self.name,
                rows=list(rows),
                columns=list(columns),
                view_fields=None if view_fields is None else list(view_fields),
            )
        )
        return _adapt(value, self._book.uri, "worksheet.config.read")

    def merge(self, address):
        return self.range(address).merge()

    def unmerge(self, address):
        return self.range(address).unmerge()

    def move(self, index):
        return self._queue("worksheet.move", self.name, {"index": index})

    def images(self):
        self._book._assert_generation(self.name, self._generation)
        value = self._book._call(
            lambda: self._book._session.observe("image.list", target_key=self.name)
        )
        return _adapt(value, self._book.uri, "image.list")

    def delete_image(self, index=None, *, picture_id=None):
        arguments = {"picture_id": picture_id} if picture_id is not None else {"index": index}
        return self._queue("image.delete", self.name, arguments)

    def read_image(self, picture_id):
        self._book._assert_generation(self.name, self._generation)
        value = self._book._call(
            lambda: self._book._session.observe(
                "image.read", target_key=self.name, picture_id=picture_id
            )
        )
        return _adapt(value, self._book.uri, "image.read")

    def image(self, image, **kwargs):
        return self._queue(
            "image.insert",
            self.name,
            {
                "content": image.content,
                "mime_type": image.mime_type,
                "anchor": image.anchor,
                "sha256": image.sha256,
                **kwargs,
            },
        )


class Range:
    def __init__(self, book, sheet, address):
        self._book, self._sheet, self.address = book, sheet, address
        self._generation = book._session.generations.get(sheet, 0)

    def _queue(self, operation, **kwargs):
        self._book._assert_generation(self._sheet, self._generation)
        return self._book._queue(operation, self._sheet, {"address": self.address, **kwargs})

    def read(self):
        self._book._assert_generation(self._sheet, self._generation)
        value = self._book._call(
            lambda: self._book._session.observe(
                "range.read", target_key=self._sheet, address=self.address
            )
        )
        if isinstance(value.get("value"), Mapping) and "values" in value["value"]:
            payload = value["value"]
            value = {
                **value,
                "value": payload["values"],
                "receipts": (
                    *value.get("receipts", ()),
                    {"details": {"observation": payload.get("observation", "committed")}},
                ),
            }
        return _adapt(value, self._book.uri, "range.read")

    def write_table(self, frame, *, header=True, style=None):
        """Queue a lexical DataFrame in this exact rectangle; commit with workbook.write."""
        from ._excel_table import rectangle_shape, table_matrix

        shape = (frame.height + int(header), frame.width)
        if rectangle_shape(self.address) != shape:
            raise ValueError("table shape must equal the range rectangle")
        # Validate range limits before constructing a Python matrix.
        self.read()
        return self.write(table_matrix(frame, header=header), style=style, format="@")

    def read_table(self, *, header=True):
        """Decode the bounded observation as a lexical DataFrame, preserving receipts."""
        from dataclasses import replace

        from ._excel_table import matrix_table

        result = self.read()
        return replace(result, value=matrix_table(result.require_value(), header=header))

    def read_style(self, fields=None):
        self._book._assert_generation(self._sheet, self._generation)
        value = self._book._call(
            lambda: self._book._session.observe(
                "range.style.read",
                target_key=self._sheet,
                address=self.address,
                fields=None if fields is None else list(fields),
            )
        )
        return _adapt(value, self._book.uri, "range.style.read")

    def write(self, values, *, format=None, style=None):
        from dataclasses import asdict

        if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
            values = [[values]]
        elif values and not isinstance(values[0], (list, tuple)):
            values = [list(values)]
        arguments = {"values": values}
        if style is not None:
            arguments["style"] = asdict(style) if hasattr(style, "__dataclass_fields__") else style
        if format is not None:
            arguments["format"] = (
                asdict(format) if hasattr(format, "__dataclass_fields__") else format
            )
        return self._queue("range.write", **arguments)

    def style(self, value=None, **kwargs):
        from dataclasses import asdict

        if value is not None:
            kwargs = (
                {**asdict(value), **kwargs}
                if hasattr(value, "__dataclass_fields__")
                else {**value, **kwargs}
            )
        return self._queue("range.style", **kwargs)

    def format(self, value=None, **kwargs):
        from dataclasses import asdict

        if value is not None:
            kwargs = (
                {**asdict(value), **kwargs}
                if hasattr(value, "__dataclass_fields__")
                else {"kind": value, **kwargs}
            )
        if "pattern" not in kwargs or kwargs["pattern"] is None:
            patterns = {
                "text": "@",
                "general": "General",
                "number": "0.00",
                "percent": "0.00%",
                "currency": "$#,##0.00",
                "date_time": "yyyy-mm-dd hh:mm:ss",
            }
            if kwargs.get("kind") in patterns:
                kwargs["pattern"] = patterns[kwargs["kind"]]
        return self._queue("range.format", **kwargs)

    def clear(self, **kwargs):
        return self._queue("range.clear", **kwargs)

    def sort(self, *, key_column=1, reverse=False, **kwargs):
        return self._queue("range.sort", key_column=key_column, reverse=reverse, **kwargs)

    def merge(self):
        return self._queue("range.merge")

    def unmerge(self):
        return self._queue("range.unmerge")


class FormulaCollection:
    def __init__(self, book, sheet):
        self._book, self._sheet = book, sheet
        self._generation = book._session.generations.get(sheet, 0)

    def set(self, address, expression):
        self._book._assert_generation(self._sheet, self._generation)
        from open_table_connector.formulas import EXCEL_A1, FormulaExpression
        from open_table_connector.spreadsheets import RangeRef

        address = self._book._call(lambda: RangeRef(address).address)
        dialect = self._book._session.binding.get("dialect", EXCEL_A1)
        formula = self._book._call(
            lambda: (
                expression
                if isinstance(expression, FormulaExpression)
                else FormulaExpression(expression, dialect)
            )
        )
        if formula.dialect != dialect:
            from .client import _failure

            raise _failure(
                "formula dialect differs from workbook dialect", ErrorCode.INVALID_FORMULA
            )
        return self._book._queue(
            "formula.set",
            self._sheet,
            {"address": address, "expression": formula.text, "dialect": formula.dialect},
        )
