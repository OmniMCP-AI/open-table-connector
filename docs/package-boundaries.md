# Package boundaries

Each workspace distribution is retained as an independently discoverable
surface. The contract and timeseries packages define shared interfaces;
the SDK depends on those layers; provider, process, conformance, dbt, and CLI
packages depend on those lower layers without reverse imports. Every package
has its own README, version, license, and typing marker so it can be released
and imported independently.

## Direction

The intended dependency direction is:

```text
contract + timeseries
          ^
          |
         sdk
      ^      ^
      |      |
     cli   providers
```

- `open-table-connector-contract` defines the closed compatibility contracts
  and provider entry-point metadata.
- `open-table-connector-timeseries` defines the portable temporal plan and
  managed lifecycle protocols.
- `open-table-connector-sdk` is the application-facing pure-Python layer with
  `Client`, `Table`, `Query`, `OperationResult`, SQL policy, and DataFrame
  normalization.
- Provider packages implement physical connector behavior and are adapted into
  the SDK surface. They must not import the SDK.
- The CLI is a thin parser/renderer over the SDK. It must not become a second
  routing or domain layer.

## Public vocabulary

The normalized public data model is deliberately narrow:

- `pl.DataFrame`: in-memory table value
- `Table`: physical connector-backed table
- `Query`: deferred table-producing computation

There is no public logical `Table`, `TableRef`, `TableHandle`,
`MaterializedTable`, or `Table.frame()`.

`TableMode` uses two public values:

- `base-mode`
- `sheet-mode`

These names distinguish Maybe base-mode from Maybe sheet-mode without leaking
package names such as SheetTable or Excelize into the shared public contract.

## SQL and execution seam

The SDK owns three explicit SQL lanes:

- relational SQL lite
- temporal SQL lite
- provider-native SQL

SQLGlot is the parser, normalization, and policy layer. OTC's portable local
execution path is a Polars plan mapper over bounded inputs. DuckDB is tracked
only as a future local-execution option and is not part of the current
dependency boundary.

## Rust boundary

The future OTS seam is:

```text
OTC Python SDK <-> Rust adapter SDK <-> OTS Rust
```

That bridge is separate from the current Python SDK implementation and should
not force Rust concerns back into the connector or CLI packages.

The CLI and process hosts keep provider integrations optional. Installed
providers register through `open_table_connector.providers`, while temporal
process handlers register through `open_table_connector.process_handlers`.
Provider-specific extras (such as PostgreSQL's `live` driver) remain opt-in;
removing a provider wheel must not prevent the contract, timeseries, CLI, or
process core from importing. The same rule applies to the SDK: removing a
provider wheel must not prevent `open-table-connector-sdk` from importing.
