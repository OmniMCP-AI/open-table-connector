from open_table_connector.contract import PROVIDER_DBT, CapabilityIdentity, ConnectorIdentity

CONNECTOR_IDENTITY = ConnectorIdentity(PROVIDER_DBT, "0.1.0", "1.0")
DBT_COMPILE_CAPABILITY = CapabilityIdentity("dbt.compile", "1.0")
DBT_RUN_CAPABILITY = CapabilityIdentity("dbt.run", "1.0")
DBT_CANCEL_CAPABILITY = CapabilityIdentity("dbt.cancel", "1.0")
DBT_ARTIFACT_READ_CAPABILITY = CapabilityIdentity("dbt.artifact.read", "1.0")
