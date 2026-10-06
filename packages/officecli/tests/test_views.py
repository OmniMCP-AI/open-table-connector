from __future__ import annotations

import pytest
from open_table_connector.artifacts import ViewRequest
from open_table_connector.contract import TargetSelector


def test_missing_browser_explicit(tmp_path):
    from open_table_connector.officecli.views import render_view

    with pytest.raises(RuntimeError, match="renderer"):
        render_view(tmp_path / "snapshot.docx", ViewRequest(TargetSelector((tmp_path / "snapshot.docx").as_uri()), "screenshot"))
