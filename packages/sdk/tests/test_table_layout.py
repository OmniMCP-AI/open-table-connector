from __future__ import annotations

import polars as pl

import open_table_connector.sdk as otc
from open_table_connector.contract import ConnectorIdentity, TableURI
from open_table_connector.sdk.connector import ArrowTableCarrier


class MetadataConnector:
    identity = ConnectorIdentity("metadata-fake", "1", "1")
    schemes = ("meta",)
    hosts = ()
    capabilities = ()
    modes = (otc.TableMode.SHEET_MODE,)
    local = False
    handles_paths = False

    def __init__(self):
        self.data_reads = 0
        self.observed_sheet_id = None
        self.frame = pl.DataFrame({"value": [1]})

    def open_table_metadata(self, address):
        return otc.OperationResult(
            otc.TableBinding(
                TableURI(address.uri.value),
                otc.TableMode.SHEET_MODE,
                None,
                "rev-1",
                self.identity.connector_id,
                schema_observed=False,
                layout_binding={"worksheet_id": "7", "worksheet_name": "Report"},
            ),
            otc.Outcome.SUCCEEDED,
            otc.CommitState.NOT_APPLICABLE,
            otc.VerificationState.PASSED,
            (),
        )

    def open_table(self, address):
        self.data_reads += 1
        result = self.open_table_metadata(address)
        return otc.OperationResult(
            otc.TableBinding(
                result.value.uri,
                result.value.mode,
                self.frame.schema,
                result.value.observed_revision,
                result.value.connector_id,
                schema_observed=True,
                layout_binding=result.value.layout_binding,
            ),
            result.outcome,
            result.commit,
            result.verification,
            result.receipts,
        )

    def bind_table_layout(self, binding):
        return {
            "provider": LayoutProvider(self),
            "workbook_uri": binding.uri.value,
            "worksheet_name": "Report",
            "descriptor": {"target": "fake", "operations": {}},
        }

    def inspect_table(self, binding):
        return otc.OperationResult(
            otc.TableInspection(binding.uri, binding.mode, self.frame.schema, 1, binding.observed_revision),
            otc.Outcome.SUCCEEDED,
            otc.CommitState.NOT_APPLICABLE,
            otc.VerificationState.PASSED,
            (),
        )

    def capabilities_for(self, binding):
        return otc.OperationResult(
            otc.CapabilitySet(()),
            otc.Outcome.SUCCEEDED,
            otc.CommitState.NOT_APPLICABLE,
            otc.VerificationState.PASSED,
            (),
        )

    def read_table(self, binding, **kwargs):
        self.data_reads += 1
        return otc.OperationResult(
            ArrowTableCarrier(self.frame.to_arrow()),
            otc.Outcome.SUCCEEDED,
            otc.CommitState.NOT_APPLICABLE,
            otc.VerificationState.PASSED,
            (),
        )

    def close(self):
        pass


class LayoutProvider:
    def __init__(self, connector):
        self.connector = connector

    def bind(self, target):
        return {"uri": target.uri, "profile": "general/1.0", "capabilities": ()}

    def preflight(self, binding, changes):
        return {}

    def commit(self, binding, changes, **kwargs):
        return {"outcome": "succeeded", "commit": "committed", "verification": "passed", "value": {}}

    def observe(self, binding, selector):
        self.connector.observed_sheet_id = "7"
        if selector["operation"] == "range.style.read":
            return {"value": {"bold": True}}
        return {"value": {"show_gridlines": True}}


def test_layout_binding_does_not_read_data():
    connector = MetadataConnector()
    client = otc.Client(registry=otc.ConnectorRegistry([connector]))
    table = client.open("meta://doc/7", metadata_only=True).require_value()
    with table.layout() as layout:
        assert layout.range("A1:B1").read_style(fields=["bold"]).require_value() == {"bold": True}
    assert connector.data_reads == 0
    assert connector.observed_sheet_id == "7"


def test_metadata_table_reads_data_only_when_data_api_is_used():
    connector = MetadataConnector()
    client = otc.Client(registry=otc.ConnectorRegistry([connector]))
    table = client.open("meta://doc/7", metadata_only=True).require_value()
    assert table.read().require_value().height == 1
    assert connector.data_reads >= 1
