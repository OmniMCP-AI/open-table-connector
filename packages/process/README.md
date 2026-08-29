# Open Table Connector Process

`open-table-connector-process` provides the local, versioned
`otc.connector-process/v1` supervisor. It carries bounded control envelopes over
framed JSON and exchanges Arrow data through verified content-addressed artifacts.

The package is transport infrastructure only. Portable time-series semantics live
in `open-table-connector-timeseries`, and provider connectors are admitted through
an explicit registry rather than arbitrary module imports.
