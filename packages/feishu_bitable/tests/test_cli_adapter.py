from __future__ import annotations

import polars as pl
from open_table_connector.contract import (
    CREDENTIAL_TENANT_ACCESS_TOKEN,
    HOST_GOOGLE_DOCS,
    OPTION_TIMEOUT_SECONDS,
    PROVIDER_FEISHU_BITABLE,
    SCHEME_FEISHU,
    SETTING_ENDPOINT,
    AdapterOptions,
    ProviderConfig,
    ProviderFactoryContext,
    parse_adapter_endpoint,
)
from open_table_connector.feishu_bitable import (
    FEISHU_RECORD_ID_FIELD,
    FeishuBitableCliAdapter,
    feishu_bitable_cli_plugin,
)


class RecordingTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object] | None, int | None]] = []

    def request(self, method, url, *, headers, body=None, timeout=None):
        self.calls.append((method, url, body, timeout))
        if method == "GET":
            return {
                "code": 0,
                "data": {
                    "items": [{"record_id": "rec_1", "fields": {"name": "Ada"}}],
                    "has_more": False,
                },
            }
        return {"code": 0, "data": {"records": []}}


def test_feishu_plugin_factory_uses_scoped_credentials_transport_and_endpoint() -> None:
    transport = RecordingTransport()
    descriptor = feishu_bitable_cli_plugin()
    adapter = descriptor.factory(
        ProviderFactoryContext(
            ProviderConfig(
                PROVIDER_FEISHU_BITABLE,
                options={OPTION_TIMEOUT_SECONDS: 17},
            ),
            environment={SETTING_ENDPOINT: "https://feishu.example.test/api"},
            credentials={CREDENTIAL_TENANT_ACCESS_TOKEN: "tenant-secret"},
            transports={PROVIDER_FEISHU_BITABLE: transport},
        )
    )

    assert isinstance(adapter, FeishuBitableCliAdapter)
    result = adapter.read(
        parse_adapter_endpoint("feishu://app-token/table-id"), AdapterOptions()
    )
    assert result.table.column_names == [FEISHU_RECORD_ID_FIELD, "name"]
    assert transport.calls[0][1].startswith("https://feishu.example.test/api/apps/")
    assert transport.calls[0][3] == 17


def test_feishu_plugin_descriptor_declares_feishu_route_and_identity() -> None:
    descriptor = feishu_bitable_cli_plugin()
    assert descriptor.name == PROVIDER_FEISHU_BITABLE
    assert descriptor.schemes == (SCHEME_FEISHU, PROVIDER_FEISHU_BITABLE)
    assert descriptor.hosts == ()
    assert HOST_GOOGLE_DOCS not in descriptor.hosts


def test_feishu_adapter_write_delegates_to_provider_connector() -> None:
    transport = RecordingTransport()
    adapter = FeishuBitableCliAdapter.from_context(
        ProviderFactoryContext(
            ProviderConfig(PROVIDER_FEISHU_BITABLE),
            credentials={CREDENTIAL_TENANT_ACCESS_TOKEN: "tenant-secret"},
            transports={PROVIDER_FEISHU_BITABLE: transport},
        )
    )
    adapter.write(
        parse_adapter_endpoint("feishu://app-token/table-id"),
        pl.DataFrame({"name": ["Ada"]}).to_arrow(),
        AdapterOptions(if_exists="append"),
    )
    assert transport.calls[0][0] == "POST"
