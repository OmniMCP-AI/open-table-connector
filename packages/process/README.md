# Open Table Connector Process

`open-table-connector-process` provides the local, versioned
`otc.connector-process/v1` supervisor. It carries bounded control envelopes over
framed JSON and exchanges Arrow data through verified content-addressed artifacts.

The package is transport infrastructure only. Portable time-series semantics live
in `open-table-connector-timeseries`, and provider connectors are admitted through
an explicit registry rather than arbitrary module imports.

The `otc-process` executable requires `OTC_PROCESS_CONFIG` to name an absolute,
deployment-owned `otc.process-bootstrap/v1` JSON file. The closed file binds one
provider, target, temporal descriptor, and provider-specific options. It contains
no credentials; deployments that need credential references construct
`run_server` with their own `CredentialResolver`. OTS deployments can pin a small
wrapper executable that sets this configuration path before invoking
`otc-process`.
