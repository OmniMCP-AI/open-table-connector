from open_connectors.contract import CapabilityIdentity, ConnectorIdentity

CONNECTOR_IDENTITY = ConnectorIdentity("postgres", "0.1.0", "1.0")
TABLE_READ_ARROW_CAPABILITY = CapabilityIdentity("table.read.arrow", "1.0")
TABLE_READ_POLARS_CAPABILITY = CapabilityIdentity("table.read.polars", "1.0")
TABLE_INSPECT_CAPABILITY = CapabilityIdentity("table.inspect", "1.0")
