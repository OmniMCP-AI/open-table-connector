from open_connectors.contract import CapabilityIdentity, ConnectorIdentity

CONNECTOR_IDENTITY = ConnectorIdentity("maybesheet", "0.2.0", "1.0")
BASE_READ_CAPABILITY = CapabilityIdentity("base.read", "1.0")
SHEET_READ_CAPABILITY = CapabilityIdentity("sheet.read", "1.0")
BASE_INSPECT_CAPABILITY = CapabilityIdentity("base.inspect", "1.0")
SHEET_INSPECT_CAPABILITY = CapabilityIdentity("sheet.inspect", "1.0")
TABLE_WRITE_CAPABILITY = CapabilityIdentity("table.write", "1.0")
