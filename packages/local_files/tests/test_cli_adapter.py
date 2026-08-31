from __future__ import annotations

from open_table_connector.contract import (
    PROVIDER_CSV,
    AdapterOptions,
    ProviderConfig,
    ProviderFactoryContext,
    parse_adapter_endpoint,
)
from open_table_connector.local_files.cli_adapter import csv_cli_plugin


def test_csv_cli_adapter_reads_through_provider_owned_connector(tmp_path) -> None:
    source = tmp_path / "orders.csv"
    source.write_text("id,amount\na,1\n", encoding="utf-8")
    context = ProviderFactoryContext(ProviderConfig(PROVIDER_CSV))

    result = csv_cli_plugin().factory(context).read(
        parse_adapter_endpoint(f"csv://{source}"), AdapterOptions()
    )

    assert result.table.to_pylist() == [{"id": "a", "amount": "1"}]
