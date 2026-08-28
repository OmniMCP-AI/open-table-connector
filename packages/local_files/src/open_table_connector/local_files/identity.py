"""Identity constants for the local-files Connector."""

from open_table_connector.contract import CapabilityIdentity, ConnectorIdentity

CONNECTOR_IDENTITY = ConnectorIdentity(
    connector_id="local_files",
    connector_version="0.1.0",
    contract_version="1.0",
)
URI_RESOLVER_CAPABILITY = CapabilityIdentity("uri.resolve", "1.0")
TABLE_INSPECT_CAPABILITY = CapabilityIdentity("table.inspect", "1.0")
TABLE_READ_ARROW_CAPABILITY = CapabilityIdentity("table.read.arrow", "1.0")
TABLE_READ_POLARS_CAPABILITY = CapabilityIdentity("table.read.polars", "1.0")
