"""Identity constants for the local-files Connector."""

from open_table_connector.contract import CapabilityIdentity, ConnectorIdentity


def connector_identity(connector_id: str) -> ConnectorIdentity:
    return ConnectorIdentity(
        connector_id=connector_id,
        connector_version="0.1.0",
        contract_version="1.0",
    )


CONNECTOR_IDENTITY = connector_identity("local_files")
URI_RESOLVER_CAPABILITY = CapabilityIdentity("uri.resolve", "1.0")
TABLE_INSPECT_CAPABILITY = CapabilityIdentity("table.inspect", "1.0")
TABLE_READ_ARROW_CAPABILITY = CapabilityIdentity("table.read.arrow", "1.0")
TABLE_READ_POLARS_CAPABILITY = CapabilityIdentity("table.read.polars", "1.0")
