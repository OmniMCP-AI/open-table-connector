from __future__ import annotations

from pathlib import Path

import pytest

from open_connectors.conformance.static_suite import assert_framework_import_free


def test_runtime_connector_tree_has_no_framework_imports(tmp_path: Path) -> None:
    (tmp_path / "connector.py").write_text("import pyarrow\n", encoding="utf-8")

    assert_framework_import_free(tmp_path)


def test_framework_import_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "connector.py").write_text("from finclaw.api import run\n", encoding="utf-8")

    with pytest.raises(AssertionError, match="framework import"):
        assert_framework_import_free(tmp_path)
