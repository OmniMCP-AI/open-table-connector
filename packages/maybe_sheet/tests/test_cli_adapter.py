from __future__ import annotations

from pathlib import Path

import pyarrow as pa
from open_table_connector.contract import (
    CREDENTIAL_ACCESS_TOKEN,
    HOST_MAYBE,
    OPTION_TIMEOUT_SECONDS,
    PROVIDER_MAYBE_SHEET,
    SCHEME_MAYBE,
    SETTING_BINARY,
    AdapterOptions,
    ProviderConfig,
    ProviderFactoryContext,
    parse_adapter_endpoint,
)
from open_table_connector.maybe_sheet import MaybeSheetCliAdapter, maybe_sheet_cli_plugin


class RecordingProcess:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], dict[str, object]]] = []

    def run(self, argv, *, credentials=None, stdin=None, timeout=None):
        self.calls.append(
            (tuple(argv), {"credentials": credentials, "stdin": stdin, "timeout": timeout})
        )
        return {"rows": [{"name": "Ada"}], "source_revision": "v1"}


def test_maybe_plugin_factory_scopes_binary_credentials_and_timeout() -> None:
    process = RecordingProcess()
    descriptor = maybe_sheet_cli_plugin()
    adapter = descriptor.factory(
        ProviderFactoryContext(
            ProviderConfig(
                PROVIDER_MAYBE_SHEET,
                environment={SETTING_BINARY: "/opt/mbs"},
                options={OPTION_TIMEOUT_SECONDS: 9},
            ),
            environment={SETTING_BINARY: "/opt/mbs"},
            credentials={CREDENTIAL_ACCESS_TOKEN: "access-secret"},
            transports={PROVIDER_MAYBE_SHEET: process},
        )
    )

    assert isinstance(adapter, MaybeSheetCliAdapter)
    result = adapter.read(parse_adapter_endpoint("maybe://doc/table"), AdapterOptions())
    assert result.table.column_names == ["name"]
    assert process.calls[0][0][:2] == ("mbs", "db-table")
    assert process.calls[0][1]["credentials"] == {CREDENTIAL_ACCESS_TOKEN: "access-secret"}
    assert process.calls[0][1]["timeout"] == 9


def test_maybe_plugin_descriptor_declares_document_route() -> None:
    descriptor = maybe_sheet_cli_plugin()
    assert descriptor.name == PROVIDER_MAYBE_SHEET
    assert descriptor.schemes == (SCHEME_MAYBE, "https")
    assert descriptor.hosts == (HOST_MAYBE,)


def test_maybe_write_uses_table_insert_and_scoped_credentials() -> None:
    process = RecordingProcess()
    adapter = MaybeSheetCliAdapter.from_context(
        ProviderFactoryContext(
            ProviderConfig(PROVIDER_MAYBE_SHEET),
            credentials={CREDENTIAL_ACCESS_TOKEN: "access-secret"},
            transports={PROVIDER_MAYBE_SHEET: process},
        )
    )
    adapter.write(
        parse_adapter_endpoint("maybe://doc/table"),
        pa.table({"name": ["Ada"]}),
        AdapterOptions(if_exists="append"),
    )
    argv = process.calls[0][0]
    assert argv[:7] == (
        "mbs",
        "table",
        "insert",
        "--target",
        "https://www.maybe.ai/docs/spreadsheets/d/doc",
        "--table-name",
        "table",
    )
    assert argv[7] == "--frame-in"
    assert Path(argv[8]).suffix == ".json"
    assert not Path(argv[8]).exists()
    assert argv[9:] == ("--output", "json")
    assert process.calls[0][1]["credentials"] == {CREDENTIAL_ACCESS_TOKEN: "access-secret"}
    assert process.calls[0][1]["stdin"] is None
