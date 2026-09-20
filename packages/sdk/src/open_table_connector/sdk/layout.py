"""Bound physical layout facade for metadata-only Tables."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .result import CommitState, ErrorCode, OperationResult, Outcome, VerificationState


def _success(value: Any, *, operation: str) -> OperationResult[Any]:
    return OperationResult(
        value=value,
        outcome=Outcome.SUCCEEDED,
        commit=CommitState.NOT_APPLICABLE,
        verification=VerificationState.UNAVAILABLE,
        receipts=(),
    )


class TableLayoutSession:
    """A layout-only session tied to one Table's stable worksheet identity."""

    def __init__(self, table, connector, payload: Mapping[str, Any]) -> None:
        self._table = table
        self._client = table._client
        self._connector = connector
        self._payload = dict(payload)
        self._closed = False
        self._workbook = None
        provider = self._payload.get("provider")
        if provider is not None:
            from .workbook import WorkbookSession

            target = self._payload.get("workbook_uri", table.uri.value)
            self._workbook = WorkbookSession(
                self._client,
                provider,
                target,
                profile=self._payload.get("profile", "general/1.0"),
            )
        self._worksheet_name = self._payload.get("worksheet_name")
        if self._worksheet_name is None:
            binding = table._binding.layout_binding or {}
            self._worksheet_name = binding.get("worksheet_name") or binding.get("worksheet_id")
        if not isinstance(self._worksheet_name, str) or not self._worksheet_name.strip():
            self._worksheet_name = "Sheet1"

    @property
    def worksheet(self):
        self._ensure_open()
        if self._workbook is not None:
            return self._workbook.worksheet.get(self._worksheet_name)
        return _DirectWorksheet(self)

    @property
    def capabilities(self):
        return self._payload.get("descriptor", self._payload.get("capabilities", {}))

    def range(self, address: str):
        return self.worksheet.range(address)

    def read_config(self, *, rows: Sequence[int], columns: Sequence[str], view_fields=None):
        return self.worksheet.read_config(rows=rows, columns=columns, view_fields=view_fields)

    def config(self, **kwargs):
        return self.worksheet.config(**kwargs)

    def write(self, **kwargs):
        self._ensure_open()
        if self._workbook is not None:
            return self._workbook.write(**kwargs)
        return self._invoke("write", kwargs, operation="workbook.write")

    def verify(self, expected=None):
        self._ensure_open()
        if self._workbook is not None:
            return self._workbook.verify(expected)
        return self._invoke("verify", {"expected": expected}, operation="workbook.verify")

    def close(self):
        if self._closed:
            return
        if self._workbook is not None:
            self._workbook.close()
        close = getattr(self._connector, "close_table_layout", None)
        if callable(close):
            close(self._table._binding)
        self._closed = True

    def __enter__(self):
        self._ensure_open()
        return self

    def __exit__(self, *_):
        self.close()

    def _ensure_open(self):
        self._client._assert_open()
        if self._closed:
            raise RuntimeError("layout session is closed")

    def _invoke(self, method: str, arguments: Mapping[str, Any], *, operation: str):
        self._ensure_open()
        target = getattr(self._connector, f"layout_{method}", None)
        if not callable(target) and method == "observe":
            target = getattr(self._connector, "observe_layout", None)
        if not callable(target) and method == "observe":
            target = getattr(self._connector, "observe", None)
        if not callable(target):
            candidate = self._payload.get(method)
            target = candidate if callable(candidate) else None
        if not callable(target):
            from .client import _failure

            raise _failure(
                f"connector does not support {operation}",
                ErrorCode.UNSUPPORTED_CAPABILITY,
                capability=f"spreadsheet.{operation}",
            )
        try:
            value = target(self._table._binding, dict(arguments))
        except TypeError:
            # Provider callbacks commonly take only the selector after the
            # binding has already been captured by bind_table_layout.
            value = target(dict(arguments))
        if isinstance(value, OperationResult):
            return self._client._deliver(value)
        return _success(value, operation=operation)


class _DirectWorksheet:
    def __init__(self, layout: TableLayoutSession) -> None:
        self._layout = layout
        self.name = layout._worksheet_name

    def range(self, address: str):
        return _DirectRange(self._layout, address)

    def read_config(self, *, rows, columns, view_fields=None):
        return self._layout._invoke(
            "observe",
            {
                "operation": "worksheet.config.read",
                "worksheet_id": (self._layout._table._binding.layout_binding or {}).get("worksheet_id"),
                "rows": list(rows),
                "columns": list(columns),
                "view_fields": None if view_fields is None else list(view_fields),
            },
            operation="worksheet.config.read",
        )

    def config(self, **kwargs):
        return self._layout._invoke(
            "config",
            {"operation": "worksheet.config", "worksheet": self.name, **kwargs},
            operation="worksheet.config",
        )


class _DirectRange:
    def __init__(self, layout: TableLayoutSession, address: str) -> None:
        self._layout, self.address = layout, address
        self.name = layout._worksheet_name

    def read_style(self, fields=None):
        return self._layout._invoke(
            "observe",
            {
                "operation": "range.style.read",
                "worksheet_id": (self._layout._table._binding.layout_binding or {}).get("worksheet_id"),
                "address": self.address,
                "fields": None if fields is None else list(fields),
            },
            operation="range.style.read",
        )

    def style(self, value=None, **kwargs):
        if value is not None:
            if hasattr(value, "__dataclass_fields__"):
                from dataclasses import asdict

                kwargs = {**asdict(value), **kwargs}
            elif isinstance(value, Mapping):
                kwargs = {**value, **kwargs}
        return self._layout._invoke(
            "style",
            {"operation": "range.style", "worksheet": self.name, "address": self.address, **kwargs},
            operation="range.style",
        )

    def format(self, value=None, **kwargs):
        if value is not None:
            if isinstance(value, str):
                kwargs = {"kind": value, **kwargs}
            elif isinstance(value, Mapping):
                kwargs = {**value, **kwargs}
        return self._layout._invoke(
            "format",
            {"operation": "range.format", "worksheet": self.name, "address": self.address, **kwargs},
            operation="range.format",
        )


__all__ = ["TableLayoutSession"]
