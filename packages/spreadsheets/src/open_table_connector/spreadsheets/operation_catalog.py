"""Static operation descriptors for the provider-neutral spreadsheet surface."""

from __future__ import annotations

from typing import Any

from open_table_connector.contract import OperationDescriptor


def _schema(properties: dict[str, Any], *, required: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


_ADDRESS = {"type": "string", "minLength": 1}
_SHEET = {"type": "string", "minLength": 1}
_DESCRIPTORS: tuple[OperationDescriptor, ...] = ()


def _build() -> tuple[OperationDescriptor, ...]:
    definitions: list[tuple[str, str, dict[str, Any], tuple[str, ...], tuple[str, ...]]] = [
        ("workbook.inspect", "spreadsheet.workbook.inspect", _schema({}), ("read",), ()),
        ("worksheet.list", "spreadsheet.worksheet.list", _schema({}), ("read",), ()),
        ("worksheet.create", "spreadsheet.worksheet.create", _schema({"name": _SHEET}, required=("name",)), ("buffered_write",), ("name",)),
        ("worksheet.rename", "spreadsheet.worksheet.rename", _schema({"name": _SHEET}, required=("name",)), ("buffered_write",), ()),
        ("worksheet.delete", "spreadsheet.worksheet.delete", _schema({}), ("buffered_write",), ()),
        ("worksheet.move", "spreadsheet.worksheet.move", _schema({"index": {"type": "integer", "minimum": 0}}, required=("index",)), ("buffered_write",), ()),
        ("worksheet.config", "spreadsheet.worksheet.config", _schema({}), ("buffered_write",), ()),
        ("worksheet.config.read", "spreadsheet.worksheet.config.read", _schema({"rows": {"type": "array"}, "columns": {"type": "array"}}, required=("rows", "columns")), ("read",), ()),
        ("range.read", "spreadsheet.range.read", _schema({"address": _ADDRESS}, required=("address",)), ("read",), ("address",)),
        ("range.write", "spreadsheet.range.write", _schema({"address": _ADDRESS, "values": {"type": "array"}}, required=("address", "values")), ("buffered_write",), ("address", "values")),
        ("range.clear", "spreadsheet.range.clear", _schema({"address": _ADDRESS}, required=("address",)), ("buffered_write",), ("address",)),
        ("range.sort", "spreadsheet.range.sort", _schema({"address": _ADDRESS, "key_column": {"type": "integer", "minimum": 1}, "reverse": {"type": "boolean"}}, required=("address",)), ("buffered_write",), ("address",)),
        ("range.merge", "spreadsheet.range.merge", _schema({"address": _ADDRESS}, required=("address",)), ("buffered_write",), ("address",)),
        ("range.unmerge", "spreadsheet.range.unmerge", _schema({"address": _ADDRESS}, required=("address",)), ("buffered_write",), ("address",)),
        ("range.style", "spreadsheet.range.style", _schema({"address": _ADDRESS, "bold": {"type": "boolean"}, "italic": {"type": "boolean"}, "font_size": {"type": "number"}}, required=("address",)), ("buffered_write",), ("address",)),
        ("range.format", "spreadsheet.range.format", _schema({"address": _ADDRESS, "kind": {"type": "string"}, "pattern": {"type": "string"}}, required=("address",)), ("buffered_write",), ("address",)),
        ("range.style.read", "spreadsheet.range.style.read", _schema({"address": _ADDRESS, "fields": {"type": "array"}}, required=("address",)), ("read",), ("address",)),
        ("range.alignment.read", "spreadsheet.range.alignment.read", _schema({"address": _ADDRESS}, required=("address",)), ("read",), ("address",)),
        ("range.alignment.write", "spreadsheet.range.alignment.write", _schema({"address": _ADDRESS}, required=("address",)), ("buffered_write",), ("address",)),
        ("range.border.read", "spreadsheet.range.border.read", _schema({"address": _ADDRESS}, required=("address",)), ("read",), ("address",)),
        ("range.border.write", "spreadsheet.range.border.write", _schema({"address": _ADDRESS}, required=("address",)), ("buffered_write",), ("address",)),
        ("range.text_layout.read", "spreadsheet.range.text_layout.read", _schema({"address": _ADDRESS}, required=("address",)), ("read",), ("address",)),
        ("range.text_layout.write", "spreadsheet.range.text_layout.write", _schema({"address": _ADDRESS}, required=("address",)), ("buffered_write",), ("address",)),
        ("formula.set", "spreadsheet.formula.set", _schema({"address": _ADDRESS, "expression": {"type": "string"}, "dialect": {"type": "string"}}, required=("address", "expression")), ("buffered_write",), ("address",)),
        ("image.insert", "spreadsheet.image.insert", _schema({"content": {}, "mime_type": {"type": "string"}, "anchor": {"type": "string"}}, required=("content", "mime_type", "anchor")), ("buffered_write",), ()),
        ("image.list", "spreadsheet.image.insert", _schema({}), ("read",), ()),
        ("image.read", "spreadsheet.image.insert", _schema({"picture_id": {"type": "string"}}, required=("picture_id",)), ("read",), ()),
        ("image.delete", "spreadsheet.image.insert", _schema({"picture_id": {"type": "string"}}, required=("picture_id",)), ("buffered_write",), ()),
        ("workbook.copy", "spreadsheet.workbook.copy", _schema({"source": {"type": "string"}, "title": {"type": "string"}}, required=("source",)), ("publish",), ()),
        ("workbook.write", "spreadsheet.workbook.write", _schema({}), ("publish",), ()),
        ("workbook.verify", "spreadsheet.workbook.verify", _schema({"expected": {}}), ("read",), ()),
        ("workbook.reconcile", "spreadsheet.workbook.verify", _schema({}), ("session_control",), ()),
    ]
    result = []
    for operation_id, capability, arguments_schema, effects, _example_keys in definitions:
        examples = {
            "address": "A1",
            "name": "Sheet1",
            "source": "file:///tmp/source.xlsx",
            "values": [[1]],
            "expression": "=1+1",
            "dialect": "excel-a1",
            "index": 0,
            "rows": [],
            "columns": [],
            "expected": {},
            "content": "",
            "mime_type": "image/png",
            "anchor": "A1",
            "picture_id": "picture-1",
        }
        example = {key: examples[key] for key in arguments_schema.get("required", ())}
        result.append(
            OperationDescriptor(
                schema="otc.operation/1.0",
                operation_id=operation_id,
                version="1.0",
                target_kind="spreadsheet",
                arguments_schema=arguments_schema,
                capability=f"{capability}/1.0",
                effects=effects,
                limits={"max_arguments_bytes": 16 * 1024 * 1024},
                examples=(example,),
                result_schema={},
            )
        )
    return tuple(result)


def operation_catalog() -> tuple[OperationDescriptor, ...]:
    """Return descriptors without importing or activating a provider."""

    global _DESCRIPTORS
    if not _DESCRIPTORS:
        _DESCRIPTORS = _build()
    return _DESCRIPTORS


__all__ = ["operation_catalog"]
