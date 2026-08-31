from open_table_connector.contract import (
    PROVIDER_POSTGRES,
    CapabilityIdentity,
    ConnectorIdentity,
)

CONNECTOR_IDENTITY = ConnectorIdentity(PROVIDER_POSTGRES, "0.1.0", "1.0")
TABLE_READ_ARROW_CAPABILITY = CapabilityIdentity("table.read.arrow", "1.0")
TABLE_READ_POLARS_CAPABILITY = CapabilityIdentity("table.read.polars", "1.0")
TABLE_INSPECT_CAPABILITY = CapabilityIdentity("table.inspect", "1.0")
TABLE_EXECUTE_CAPABILITY = CapabilityIdentity("table.execute", "1.0")
TABLE_WRITE_CAPABILITY = CapabilityIdentity("table.write", "1.0")
