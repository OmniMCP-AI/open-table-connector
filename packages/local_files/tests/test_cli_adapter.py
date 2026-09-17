from __future__ import annotations

from open_table_connector.contract import (
    AdapterOptions,
    ProviderConfig,
    ProviderFactoryContext,
    parse_adapter_endpoint,
)
from open_table_connector.local_files.cli_adapter import local_files_cli_plugin


def test_local_files_cli_adapter_reads_csv_file_url(tmp_path) -> None:
    source = tmp_path / "orders.csv"
    source.write_text("id,amount\na,1\n", encoding="utf-8")
    context = ProviderFactoryContext(ProviderConfig("local_files"))

    result = local_files_cli_plugin().factory(context).read(
        parse_adapter_endpoint(source.as_uri()), AdapterOptions()
    )

    assert result.table.to_pylist() == [{"id": "a", "amount": "1"}]
    assert result.receipt.connector.connector_id == "local_files"
