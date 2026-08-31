from __future__ import annotations

import builtins
import sys

from open_table_connector.cli import plugins
from open_table_connector.cli.adapters import build_adapters


def test_cli_imports_and_builds_without_provider_distributions(monkeypatch) -> None:
    blocked = (
        "open_table_connector.google_sheets",
        "open_table_connector.feishu_bitable",
        "open_table_connector.maybe_sheet",
        "open_table_connector.local_files",
    )
    for module in tuple(sys.modules):
        if any(module == item or module.startswith(item + ".") for item in blocked):
            sys.modules.pop(module, None)
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.startswith(blocked):
            raise ModuleNotFoundError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(plugins, "_descriptor_entries", lambda: ())
    assert build_adapters({}) == ()
