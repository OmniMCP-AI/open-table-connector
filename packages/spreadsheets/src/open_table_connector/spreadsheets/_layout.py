"""Provider-neutral validation for spreadsheet layout patches.

The functions in this module only normalize caller intent.  They never read a
workbook and must therefore not be used to manufacture readback evidence.
"""

from __future__ import annotations

import copy
import json
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

from ._operations import Change
from .formats import normalize_format

JSON = dict[str, Any]


class LayoutCapabilityError(ValueError):
    """A layout field/value is not advertised by the provider descriptor."""

    code = "unsupported_capability"


_STYLE_ALIASES = {
    "size": "font_size",
    "font_size_points": "font_size",
    "format": "number_format",
    "wrap": "text_layout",
}
_STYLE_FIELDS = {
    "bold",
    "italic",
    "font_size",
    "foreground",
    "fill",
    "number_format",
    "horizontal",
    "vertical",
    "text_layout",
    "wrap_text",
    "shrink_to_fit",
    "border",
}
_CONFIG_ALIASES = {"gridline": "gridlines", "show_gridlines": "gridlines", "view_config": "view"}
_CONFIG_FIELDS = {"row_heights", "column_sizes", "column_widths", "column_widths_pixels", "gridlines", "view"}
_EDGE_NAMES = {"top", "bottom", "left", "right"}
_DEFAULT_BORDER_STYLES = {"none", "thin", "medium", "thick", "dashed", "dotted", "double"}
_COLUMN = re.compile(r"^[A-Z]{1,3}$")


def _copy_json(value: Any) -> Any:
    """Make a detached copy while rejecting values that cannot cross the wire."""

    try:
        return copy.deepcopy(value)
    except Exception as exc:  # pragma: no cover - defensive for hostile mappings
        raise ValueError("descriptor contains an unserializable value") from exc


def _operation_fields(descriptor: Mapping[str, Any], operation: str) -> Mapping[str, Any]:
    operations = descriptor.get("operations")
    if isinstance(operations, Mapping) and isinstance(operations.get(operation), Mapping):
        return operations[operation]
    direct = descriptor.get(operation)
    if isinstance(direct, Mapping):
        return direct
    # A few early descriptors used short operation names.  Accept those wire
    # forms while keeping the canonical names in normalized output.
    short = operation.rsplit(".", 1)[-1]
    if isinstance(operations, Mapping) and isinstance(operations.get(short), Mapping):
        return operations[short]
    return {}


def validate_descriptor(value: Mapping[str, Any]) -> JSON:
    """Validate and detach a serializable field capability descriptor."""

    if not isinstance(value, Mapping):
        raise ValueError("layout descriptor must be an object")
    for key in ("target", "dialect", "limits"):
        if key not in value:
            raise ValueError(f"layout descriptor requires {key}")
    if not isinstance(value["target"], str) or not value["target"].strip():
        raise ValueError("descriptor target must be a non-empty string")
    if not isinstance(value["dialect"], str) or not value["dialect"].strip():
        raise ValueError("descriptor dialect must be a non-empty string")
    if not isinstance(value["limits"], Mapping):
        raise ValueError("descriptor limits must be an object")

    result = _copy_json(dict(value))
    operations = result.get("operations")
    if operations is None:
        operations = {
            key: item
            for key, item in result.items()
            if key in {"range.style", "worksheet.config", "style", "config"}
        }
        result["operations"] = operations
    if not isinstance(operations, Mapping):
        raise ValueError("descriptor operations must be an object")
    for operation, fields in operations.items():
        if not isinstance(operation, str) or not operation.strip():
            raise ValueError("descriptor operation names must be strings")
        if not isinstance(fields, Mapping):
            raise ValueError(f"descriptor operation {operation} must be an object")
        for field_name, spec in fields.items():
            if not isinstance(field_name, str) or not field_name.strip():
                raise ValueError("descriptor field names must be strings")
            if not isinstance(spec, Mapping):
                raise ValueError(f"descriptor field {operation}.{field_name} must be an object")
            for flag in ("read", "write", "persist"):
                if flag in spec and type(spec[flag]) is not bool:
                    raise ValueError(f"descriptor {operation}.{field_name}.{flag} must be boolean")
            for array_name in ("values", "units"):
                if array_name in spec and spec[array_name] is not None and not isinstance(spec[array_name], (list, tuple)):
                    raise ValueError(f"descriptor {operation}.{field_name}.{array_name} must be an array")
            if "precision" in spec and (
                isinstance(spec["precision"], bool)
                or not isinstance(spec["precision"], (int, float))
                or not math.isfinite(spec["precision"])
                or spec["precision"] < 0
            ):
                raise ValueError(f"descriptor {operation}.{field_name}.precision is invalid")
            if "defaults_source" in spec and not isinstance(spec["defaults_source"], str):
                raise ValueError(f"descriptor {operation}.{field_name}.defaults_source must be a string")
    return result


def _require_field(descriptor: Mapping[str, Any], operation: str, field_name: str, access: str = "write") -> Mapping[str, Any]:
    fields = _operation_fields(descriptor, operation)
    spec = fields.get(field_name)
    if not isinstance(spec, Mapping) or spec.get(access) is not True:
        raise LayoutCapabilityError(f"{operation}.{field_name} does not support {access}")
    return spec


def _allowed_values(spec: Mapping[str, Any], fallback: set[str]) -> set[str]:
    values = spec.get("values")
    if values is None:
        return fallback
    return {item for item in values if isinstance(item, str)}


def _color(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"#[0-9A-Fa-f]{6}", value) is None:
        raise ValueError(f"{field_name} must be #RRGGBB")
    return value


def _finite_number(value: Any, field_name: str, *, positive: bool = False) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{field_name} must be a finite number")
    if positive and value <= 0:
        raise ValueError(f"{field_name} must be positive")
    return value


def _format_descriptor(descriptor: Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(descriptor.get("formats"), Mapping):
        return descriptor
    # Layout descriptors from providers may omit format metadata when a format
    # patch is not advertised.  The complete format validator still receives a
    # deterministic, provider-neutral descriptor in that case.
    fallback = {
        "dialect": descriptor.get("dialect", "excel"),
        "version": "1.0",
        "locales": ["en-US", "zh-CN", "de-DE"],
        "builtins": {},
        "custom_code": True,
        "unsupported_features": [],
    }
    result = dict(descriptor)
    result["formats"] = fallback
    return result


def normalize_style(
    arguments: Mapping[str, Any],
    *,
    descriptor: Mapping[str, Any],
    baseline: Mapping[str, Any] | None = None,
) -> JSON:
    """Normalize a style patch without filling omitted fields from a readback."""

    descriptor = validate_descriptor(descriptor)
    if not isinstance(arguments, Mapping):
        raise ValueError("style arguments must be an object")
    canonical: dict[str, Any] = {}
    for raw_key, value in arguments.items():
        if value is None:
            continue  # preserve the historic null-as-omitted behavior
        if raw_key not in _STYLE_FIELDS and raw_key not in _STYLE_ALIASES:
            raise ValueError(f"unknown style parameter: {raw_key}")
        key = _STYLE_ALIASES.get(raw_key, raw_key)
        if key in canonical:
            raise ValueError(f"conflicting aliases for style field {key}")
        canonical[key] = value

    if "text_layout" in canonical and ({"wrap_text", "shrink_to_fit"} & canonical.keys()):
        raise ValueError("text_layout conflicts with raw wrap flags")
    if canonical.get("wrap_text") is True and canonical.get("shrink_to_fit") is True:
        raise ValueError("wrap_text and shrink_to_fit cannot both be true")

    result: JSON = {}
    for key, value in canonical.items():
        spec = _require_field(descriptor, "range.style", key)
        if key in {"bold", "italic", "wrap_text", "shrink_to_fit"}:
            if type(value) is not bool:
                raise ValueError(f"{key} must be a boolean")
            result[key] = value
        elif key == "font_size":
            result[key] = _finite_number(value, key, positive=True)
        elif key in {"foreground", "fill"}:
            result[key] = _color(value, key)
        elif key in {"horizontal", "vertical"}:
            allowed = _allowed_values(spec, {"left", "center", "right"} if key == "horizontal" else {"top", "center", "bottom"})
            if not isinstance(value, str) or value not in allowed:
                raise LayoutCapabilityError(f"unsupported {key} alignment: {value!r}")
            result[key] = value
        elif key == "text_layout":
            if not isinstance(value, str):
                raise ValueError("text_layout must be a string")
            allowed = _allowed_values(spec, {"no_wrap", "wrap", "shrink_to_fit"})
            if value not in allowed:
                raise LayoutCapabilityError(f"unsupported text_layout mode: {value}")
            mappings = spec.get("mappings", {})
            mapping = mappings.get(value) if isinstance(mappings, Mapping) else None
            if mapping is None:
                mapping = {
                    "no_wrap": {"wrap_text": False, "shrink_to_fit": False},
                    "wrap": {"wrap_text": True, "shrink_to_fit": False},
                    "shrink_to_fit": {"wrap_text": False, "shrink_to_fit": True},
                }.get(value)
            if not isinstance(mapping, Mapping):
                raise LayoutCapabilityError(f"text_layout mode has no lossless mapping: {value}")
            for flag, flag_value in mapping.items():
                if flag not in {"wrap_text", "shrink_to_fit"} or type(flag_value) is not bool:
                    raise ValueError("invalid text_layout mapping")
                _require_field(descriptor, "range.style", flag)
                result[flag] = flag_value
        elif key == "number_format":
            if isinstance(value, str):
                value = {"kind": "custom", "pattern": value}
            if not isinstance(value, Mapping):
                raise ValueError("number_format must be an object or format code")
            result[key] = normalize_format(value, descriptor=_format_descriptor(descriptor))
        elif key == "border":
            if not isinstance(value, Mapping):
                raise ValueError("border must be an object")
            allowed_styles = _allowed_values(spec, _DEFAULT_BORDER_STYLES)
            border: dict[str, Any] = {}
            for edge, edge_spec in value.items():
                if edge not in _EDGE_NAMES:
                    raise ValueError(f"unknown border edge: {edge}")
                if not isinstance(edge_spec, Mapping):
                    raise ValueError("border edge must be an object")
                if set(edge_spec) - {"style", "color"} or "style" not in edge_spec:
                    raise ValueError("border edge requires style")
                style = edge_spec["style"]
                if not isinstance(style, str) or style not in allowed_styles:
                    raise LayoutCapabilityError(f"unsupported border style: {style!r}")
                normalized_edge: dict[str, Any] = {"style": style}
                if "color" in edge_spec and style != "none":
                    normalized_edge["color"] = _color(edge_spec["color"], "border color")
                elif "color" in edge_spec and edge_spec["color"] is not None:
                    _color(edge_spec["color"], "border color")
                border[edge] = normalized_edge
            result[key] = border

    if baseline is not None:
        if not isinstance(baseline, Mapping):
            raise ValueError("style baseline must be an object")
        wrap = result.get("wrap_text", baseline.get("wrap_text"))
        shrink = result.get("shrink_to_fit", baseline.get("shrink_to_fit"))
        if wrap is True and shrink is True:
            raise ValueError("wrap_text and shrink_to_fit cannot both be true")
    return result


def _rows(value: Any) -> dict[int, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("row_heights must be an object")
    result: dict[int, Any] = {}
    for raw_row, raw_value in value.items():
        if isinstance(raw_row, bool) or not isinstance(raw_row, int) or raw_row <= 0:
            raise ValueError("row number must be a positive integer")
        if isinstance(raw_value, Mapping):
            if set(raw_value) - {"value", "unit"} or "value" not in raw_value:
                raise ValueError("row height object requires value")
            if raw_value.get("unit", "points") != "points":
                raise ValueError("row height unit must be points")
            result[raw_row] = _finite_number(raw_value["value"], "row height", positive=True)
        else:
            result[raw_row] = _finite_number(raw_value, "row height", positive=True)
    return result


def _columns(value: Any, *, units: set[str]) -> dict[str, dict[str, Any]]:
    if not isinstance(value, Mapping):
        raise ValueError("column_sizes must be an object")
    result: dict[str, dict[str, Any]] = {}
    for raw_column, spec in value.items():
        if not isinstance(raw_column, str) or _COLUMN.fullmatch(raw_column.upper()) is None:
            raise ValueError("column key must be an A-Z column")
        column = raw_column.upper()
        if not isinstance(spec, Mapping) or set(spec) - {"value", "unit"} or "value" not in spec:
            raise ValueError("column size requires value and unit")
        unit = spec.get("unit")
        if not isinstance(unit, str) or unit not in units:
            raise LayoutCapabilityError(f"unsupported column width unit: {unit!r}")
        result[column] = {"value": _finite_number(spec["value"], "column width", positive=True), "unit": unit}
    return result


def normalize_config(arguments: Mapping[str, Any], *, descriptor: Mapping[str, Any]) -> JSON:
    """Normalize row/column dimensions and persisted worksheet view settings."""

    descriptor = validate_descriptor(descriptor)
    if not isinstance(arguments, Mapping):
        raise ValueError("config arguments must be an object")
    canonical: dict[str, Any] = {}
    for raw_key, value in arguments.items():
        if value is None:
            continue
        if raw_key not in _CONFIG_FIELDS and raw_key not in _CONFIG_ALIASES:
            raise ValueError(f"unknown config parameter: {raw_key}")
        key = _CONFIG_ALIASES.get(raw_key, raw_key)
        if key in canonical:
            raise ValueError(f"conflicting aliases for config field {key}")
        canonical[key] = value

    result: JSON = {}
    if "row_heights" in canonical:
        _require_field(descriptor, "worksheet.config", "row_heights")
        result["row_heights"] = _rows(canonical["row_heights"])
    if "column_sizes" in canonical:
        spec = _require_field(descriptor, "worksheet.config", "column_sizes")
        units = set(spec.get("units", ("px", "excel_character")))
        result["column_sizes"] = _columns(canonical["column_sizes"], units=units)
    for alias, unit in (("column_widths", "excel_character"), ("column_widths_pixels", "px")):
        if alias not in canonical:
            continue
        _require_field(descriptor, "worksheet.config", "column_sizes")
        converted = {
            column: {"value": _finite_number(width, "column width", positive=True), "unit": unit}
            for column, width in _validate_column_numbers(canonical[alias]).items()
        }
        if "column_sizes" in result and set(result["column_sizes"]) & set(converted):
            raise ValueError("column size aliases conflict")
        result.setdefault("column_sizes", {}).update(converted)
    if "gridlines" in canonical:
        _require_field(descriptor, "worksheet.config", "gridlines")
        if type(canonical["gridlines"]) is not bool:
            raise ValueError("gridlines must be a boolean")
        result["gridlines"] = canonical["gridlines"]
    if "view" in canonical:
        _require_field(descriptor, "worksheet.config", "view")
        if not isinstance(canonical["view"], Mapping):
            raise ValueError("view must be an object")
        result["view"] = _copy_json(dict(canonical["view"]))
    return result


def _validate_column_numbers(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("column widths must be an object")
    result: dict[str, Any] = {}
    for raw_column, width in value.items():
        if not isinstance(raw_column, str) or _COLUMN.fullmatch(raw_column.upper()) is None:
            raise ValueError("column key must be an A-Z column")
        result[raw_column.upper()] = width
    return result


def _change_operation(change: Change) -> str:
    capability = change.capability.capability_id
    if capability.endswith("worksheet.config") or capability.endswith("worksheet.config.write"):
        return "worksheet.config"
    if capability.endswith("range.style") or capability.endswith("range.style.write"):
        return "range.style"
    operation = change.arguments.get("operation")
    if operation in {"range.style", "worksheet.config"}:
        return operation
    raise ValueError(f"unsupported layout change capability: {capability}")


def _strip_transport(arguments: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in arguments.items()
        if key not in {"address", "worksheet", "worksheet_id", "operation"}
    }


def _cell_count(address: Any) -> int:
    if not isinstance(address, str):
        return 0
    match = re.fullmatch(r"([A-Z]+)([1-9][0-9]*)(?::([A-Z]+)([1-9][0-9]*))?", address.upper())
    if match is None:
        return 0
    def column(value: str) -> int:
        total = 0
        for char in value:
            total = total * 26 + ord(char) - 64
        return total
    start_col, start_row = column(match.group(1)), int(match.group(2))
    end_col, end_row = column(match.group(3) or match.group(1)), int(match.group(4) or match.group(2))
    return max(0, end_col - start_col + 1) * max(0, end_row - start_row + 1)


def prepare_layout(
    changes: Sequence[Change],
    *,
    baseline: Mapping[str, Any],
    descriptor: Mapping[str, Any],
) -> JSON:
    """Normalize a complete batch and build an expectation from its own baseline."""

    descriptor = validate_descriptor(descriptor)
    if not isinstance(changes, Sequence) or isinstance(changes, (str, bytes)):
        raise ValueError("changes must be a sequence")
    if not isinstance(baseline, Mapping):
        raise ValueError("layout baseline must be an object")
    limits = descriptor.get("limits", {})
    max_changes = limits.get("max_changes", limits.get("changes")) if isinstance(limits, Mapping) else None
    if max_changes is not None and len(changes) > max_changes:
        raise ValueError("layout change budget exceeded")
    expected: dict[str, Any] = _copy_json(dict(baseline))
    expected.setdefault("style", {})
    expected.setdefault("config", {})
    normalized_changes: list[JSON] = []
    total_bytes = 0
    total_cells = 0
    for change in changes:
        if not isinstance(change, Change):
            raise TypeError("changes must contain Change values")
        operation = _change_operation(change)
        arguments = _strip_transport(change.arguments)
        if operation == "range.style":
            normalized = normalize_style(arguments, descriptor=descriptor, baseline=expected["style"])
            expected["style"].update(normalized)
            if "border" in normalized:
                current = expected["style"].get("border", {})
                merged = dict(current) if isinstance(current, Mapping) else {}
                merged.update(normalized["border"])
                expected["style"]["border"] = merged
            total_cells += _cell_count(change.arguments.get("address"))
        else:
            normalized = normalize_config(arguments, descriptor=descriptor)
            expected["config"].update(normalized)
        wire_arguments = _copy_json(dict(normalized))
        normalized_changes.append(
            {
                "operation_id": change.operation_id,
                "capability": change.capability.to_reference(),
                "target_key": change.target_key,
                "arguments": wire_arguments,
            }
        )
        total_bytes += len(json.dumps(wire_arguments, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    max_cells = limits.get("max_cells", limits.get("cells")) if isinstance(limits, Mapping) else None
    max_bytes = limits.get("max_bytes", limits.get("bytes")) if isinstance(limits, Mapping) else None
    if max_cells is not None and total_cells > max_cells:
        raise ValueError("layout cell budget exceeded")
    if max_bytes is not None and total_bytes > max_bytes:
        raise ValueError("layout byte budget exceeded")
    coverage = {
        "style": sorted(expected["style"]),
        "config": sorted(expected["config"]),
    }
    return {"changes": normalized_changes, "expected": expected, "coverage": coverage}


__all__ = [
    "LayoutCapabilityError",
    "normalize_config",
    "normalize_style",
    "prepare_layout",
    "validate_descriptor",
]
