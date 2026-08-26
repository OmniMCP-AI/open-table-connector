from open_connectors.contract import CapabilityIdentity, ConnectorIdentity

CONNECTOR_IDENTITY = ConnectorIdentity("dbt", "0.1.0", "1.0")
DBT_COMPILE_CAPABILITY = CapabilityIdentity("dbt.compile", "1.0")
DBT_RUN_CAPABILITY = CapabilityIdentity("dbt.run", "1.0")
DBT_CANCEL_CAPABILITY = CapabilityIdentity("dbt.cancel", "1.0")
DBT_ARTIFACT_READ_CAPABILITY = CapabilityIdentity("dbt.artifact.read", "1.0")
