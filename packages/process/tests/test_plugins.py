from __future__ import annotations

import builtins


def test_process_core_imports_without_provider_distributions() -> None:
    blocked = {
        "open_table_connector.local_files",
        "open_table_connector.maybe_sheet",
        "open_table_connector.postgres",
        "open_table_connector.sqlite",
    }
    real_import = builtins.__import__

    def guarded_import(name: str, *args: object, **kwargs: object):
        if name in blocked:
            raise ModuleNotFoundError(name=name)
        return real_import(name, *args, **kwargs)

    builtins.__import__ = guarded_import
    try:
        import open_table_connector.process as process

        assert process.build_process_runtime is not None
    finally:
        builtins.__import__ = real_import
