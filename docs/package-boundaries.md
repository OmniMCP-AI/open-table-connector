# Package boundaries

Each workspace distribution is retained as an independently discoverable
surface. The contract and timeseries packages define shared interfaces;
provider, process, conformance, dbt, and CLI packages depend on those layers
without reverse imports. Every package has its own README, version, license,
and typing marker so it can be released and imported independently.

The CLI and process hosts keep provider integrations optional. Installed
providers register through `open_table_connector.providers`, while temporal
process handlers register through `open_table_connector.process_handlers`.
Provider-specific extras (such as PostgreSQL's `live` driver) remain opt-in;
removing a provider wheel must not prevent the contract, timeseries, CLI, or
process core from importing.
