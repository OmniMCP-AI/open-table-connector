from __future__ import annotations

from pathlib import Path

from open_connectors.contract import TableURI
from open_connectors.conformance import run_read_suite
from open_connectors.local_files.reader import LocalFilesConnector, LocalTableReadRequest


def test_local_files_connector_passes_shared_read_conformance(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    source.write_text("id,amount\n1,2.50\n2,\n", encoding="utf-8")

    run_read_suite(
        LocalFilesConnector(),
        [LocalTableReadRequest(TableURI(source.as_uri()))],
    )
