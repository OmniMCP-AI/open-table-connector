# Package boundaries

Each workspace distribution is retained as an independently discoverable
surface. The contract and timeseries packages define shared interfaces;
provider, process, conformance, dbt, and CLI packages depend on those layers
without reverse imports. Every package has its own README, version, license,
and typing marker so it can be released and imported independently.
