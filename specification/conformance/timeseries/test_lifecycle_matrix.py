from __future__ import annotations

from open_table_connector.conformance import assert_managed_lifecycle
from open_table_connector.contract import TableURI
from open_table_connector.local_files import CsvManagedTemporalStore, JsonManagedTemporalStore
from open_table_connector.sqlite import SQLiteManagedTemporalStore
from specification.conformance.timeseries.support import create_ticks, descriptor, sqlite_uri, ticks_table

from .conftest import lifecycle_case


def test_csv_managed_lifecycle(tmp_path) -> None:
    root = tmp_path / "artifacts"
    target = TableURI(
        (tmp_path / "ticks").as_uri().replace("file://", "managed+csv://", 1)
    )
    result = assert_managed_lifecycle(
        CsvManagedTemporalStore(root, descriptor()), lifecycle_case(root, target)
    )
    assert result.readback.table is not None
    assert result.readback.table.equals(ticks_table())


def test_json_and_jsonl_use_normal_schemes_for_managed_lifecycle(tmp_path) -> None:
    for format_name in ("json", "jsonl"):
        root = tmp_path / format_name / "artifacts"
        path = tmp_path / format_name / f"ticks.{format_name}"
        path.parent.mkdir(parents=True, exist_ok=True)
        target = TableURI(path.as_uri().replace("file://", f"{format_name}://", 1))
        result = assert_managed_lifecycle(
            JsonManagedTemporalStore(format_name, root, descriptor()),
            lifecycle_case(root, target),
        )
        assert result.readback.table is not None
        assert result.readback.table.equals(ticks_table())
        assert target.scheme == format_name
        assert "managed+" not in target.value


def test_sqlite_managed_lifecycle(tmp_path) -> None:
    root = tmp_path / "artifacts"
    path = tmp_path / "ticks.db"
    create_ticks(path)
    target = sqlite_uri(path)
    result = assert_managed_lifecycle(
        SQLiteManagedTemporalStore(target, root, descriptor()),
        lifecycle_case(root, target),
    )
    assert result.readback.table is not None
    assert result.readback.table.equals(ticks_table())
