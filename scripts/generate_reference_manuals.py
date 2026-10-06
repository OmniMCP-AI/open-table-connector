"""Generate complete CLI, Python export, and operation-schema reference appendices."""

from __future__ import annotations

import argparse
import inspect
import json
import re
from enum import Enum
from importlib import import_module
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
MODULES = (
    "sdk", "sdk.workbook", "sdk.layout", "sdk.recipes", "sdk.snapshots",
    "sdk.discovery", "sdk.operations", "otc", "contract", "spreadsheets",
    "formulas", "timeseries", "artifacts", "officecli", "officecli.document",
    "officecli.process", "officecli.capabilities", "mcp.policy", "mcp.tools",
    "mcp.server", "process", "local_files", "sqlite", "postgres",
    "google_sheets", "maybe_sheet", "feishu_bitable", "dbt", "conformance",
)


def cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def signature(value: Any) -> str:
    try:
        text = str(inspect.signature(value))
    except (ValueError, TypeError):
        return "(signature unavailable; see source)"
    return re.sub(r" at 0x[0-9a-fA-F]+", "", text)


def source_link(value: object) -> str:
    try:
        source = inspect.getsourcefile(cast(Any, value))
        if source is None:
            return ""
        path = Path(source).resolve()
        relative = path.relative_to(ROOT).as_posix()
    except (TypeError, ValueError):
        return ""
    return f"[source](../../{relative})"


def public_names(module: Any) -> list[str]:
    exported = getattr(module, "__all__", None)
    if exported is not None:
        return sorted(set(exported))
    return sorted(
        name for name, value in vars(module).items()
        if not name.startswith("_") and getattr(value, "__module__", None) == module.__name__
    )


def api_reference() -> str:
    lines = [
        "# Python API Inventory", "",
        "Generated from public exports and runtime signatures. Regenerate with",
        "`uv run --all-packages python scripts/generate_reference_manuals.py`.", "",
        "Start with the [SDK manual](../user-guide/sdk-manual.md) for behavior and examples, and",
        "the [component manual](../user-guide/components.md) for provider prerequisites. A public",
        "name or callable signature does not prove provider support. Returned handles",
        "are obtained through their owning client/session, not constructed directly.", "",
        "Annotations are printed as declared; string annotations are not evaluated.",
        "Private implementation methods are excluded. Inherited public OTC methods",
        "are included; third-party base-class methods are omitted.", "",
    ]
    for suffix in MODULES:
        module = import_module("open_table_connector." + suffix)
        lines.extend([f"## {module.__name__}", ""])
        names = public_names(module)
        if not names:
            lines.extend(["No declared public exports; use the package's entry points.", ""])
            continue
        lines.extend(["| Name | Kind | Definition |", "| --- | --- | --- |"])
        classes = []
        for name in names:
            value = getattr(module, name)
            if inspect.isclass(value):
                definition = signature(value)
                kind = "enum" if issubclass(value, Enum) else "class"
                classes.append((name, value))
            elif inspect.isfunction(value):
                definition, kind = signature(value), "function"
            else:
                definition, kind = repr(value), "constant"
                if len(definition) > 240:
                    definition = f"{type(value).__name__}; inspect via this named export"
            lines.append(f"| `{name}` | {kind} | `{cell(definition)}` {source_link(value)} |")
        lines.append("")
        for name, cls in classes:
            lines.extend([f"### {name}", ""])
            if issubclass(cls, Enum):
                lines.extend(["| Member | Wire value |", "| --- | --- |"])
                for key, value in cls.__members__.items():
                    lines.append(f"| `{key}` | `{cell(value.value)}` |")
                lines.append("")
                continue
            annotations: dict[str, Any] = {}
            members: dict[str, Any] = {}
            for parent in reversed(cls.__mro__):
                if not parent.__module__.startswith("open_table_connector"):
                    continue
                annotations.update(getattr(parent, "__annotations__", {}))
                members.update(vars(parent))
            public_fields = {k: v for k, v in annotations.items() if not k.startswith("_")}
            if public_fields:
                lines.extend(["| Field | Declared type |", "| --- | --- |"])
                for key, value in sorted(public_fields.items()):
                    lines.append(f"| `{key}` | `{cell(value)}` |")
                lines.append("")
            public = [(k, v) for k, v in sorted(members.items()) if not k.startswith("_")]
            method_lines = []
            for key, raw in public:
                value = getattr(cls, key)
                if isinstance(raw, property):
                    detail = "property (read-only)" if raw.fset is None else "property"
                elif callable(value):
                    detail = signature(value)
                else:
                    continue
                method_lines.append(f"| `{key}` | `{cell(detail)}` |")
            if method_lines:
                lines.extend(["| Public member | Signature or access |", "| --- | --- |", *method_lines, ""])
    return "\n".join(lines).rstrip() + "\n"


def cli_reference() -> str:
    from open_table_connector.cli.__main__ import build_parser  # type: ignore[import-not-found]

    parser = build_parser()
    lines = [
        "# CLI Option Inventory", "",
        "Generated from `build_parser()`; includes every command, positional, flag,",
        "choice, and parser default. Regenerate with",
        "`uv run --all-packages python scripts/generate_reference_manuals.py`.", "",
        "The [CLI manual](../user-guide/cli-manual.md) documents execution semantics and current",
        "limitations. Parser acceptance alone does not mean an operation commits.", "",
    ]
    commands = {"otc": parser}
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            commands.update({"otc " + name: child for name, child in action.choices.items()})
    for command, selected in commands.items():
        lines.extend([f"## {command}", "", "```text", selected.format_usage().strip(), "```", "",
                      "| Argument | Required | Default | Choices/type | Help |", "| --- | --- | --- | --- | --- |"])
        for action in selected._actions:
            if isinstance(action, argparse._SubParsersAction):
                continue
            flags = ", ".join(action.option_strings) or action.dest
            choices = ", ".join(str(item) for item in action.choices) if action.choices else getattr(action.type, "__name__", "")
            if isinstance(action, (argparse._StoreTrueAction, argparse._StoreFalseAction)):
                choices = "boolean flag"
            default = "-" if action.default == argparse.SUPPRESS else repr(action.default)
            lines.append(f"| `{flags}` | {'yes' if action.required else 'no'} | `{cell(default)}` | {cell(choices)} | {cell(action.help or '')} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def operation_reference() -> str:
    from open_table_connector.spreadsheets.operation_catalog import (  # type: ignore[import-not-found]
        operation_catalog,
    )

    descriptors = sorted(operation_catalog(), key=lambda item: (item.operation_id, item.version))
    lines = [
        "# Spreadsheet Operation Schemas", "",
        "Generated from the built-in spreadsheet catalog. Regenerate with",
        "`uv run --all-packages python scripts/generate_reference_manuals.py`.", "",
        "These are static descriptors, not a promise of provider implementation.",
        "Check bound workbook support, the [component manual](../user-guide/components.md), and",
        "the [CLI manual](../user-guide/cli-manual.md). The generic SDK dispatcher implements a",
        "subset; mutations there can return planned results without publishing.", "",
        "| Operation | Version | Capability | Effects |", "| --- | --- | --- | --- |",
    ]
    for descriptor in descriptors:
        lines.append(f"| `{descriptor.operation_id}` | `{descriptor.version}` | `{descriptor.capability}` | {', '.join(descriptor.effects)} |")
    lines.append("")
    for descriptor in descriptors:
        lines.extend([f"## {descriptor.operation_id}", "", "```json",
                      json.dumps(descriptor.to_wire(), ensure_ascii=True, indent=2, sort_keys=True), "```", ""])
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when generated references are stale")
    args = parser.parse_args()
    outputs = {
        "docs/reference/cli-options.md": cli_reference(),
        "docs/reference/api-inventory.md": api_reference(),
        "docs/reference/spreadsheet-schemas.md": operation_reference(),
    }
    errors = []
    for relative, content in outputs.items():
        path = ROOT / relative
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                errors.append(f"stale reference: {relative}")
        else:
            path.write_text(content, encoding="utf-8")
            print(f"generated {relative} ({len(content.encode('utf-8'))} bytes)")
    for error in errors:
        print(error)
    if not errors and args.check:
        print("CLI, Python API, and operation-schema references are current")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
