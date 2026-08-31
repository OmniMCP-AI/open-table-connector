from __future__ import annotations

import builtins

from open_table_connector.cli.adapters import build_adapters


def test_cli_imports_and_builds_without_provider_distributions(monkeypatch) -> None:
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.startswith(
            (
                "open_table_connector.google_sheets",
                "open_table_connector.feishu_bitable",
                "open_table_connector.maybe_sheet",
                "open_table_connector.local_files",
            )
        ):
            raise ModuleNotFoundError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    assert build_adapters({}) == ()
