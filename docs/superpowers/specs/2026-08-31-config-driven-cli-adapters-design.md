# Config-Driven Provider-Owned CLI Adapters

**Status:** approved for implementation planning

**Date:** 2026-08-31

## Problem

The workspace has an independent plugin seam based on
`open_table_connector.contract.PluginDescriptor` and Python entry points, but
the CLI does not finish that design. `packages/cli` still owns every concrete
adapter class, maps canonical provider IDs to those classes, names provider
environment variables, and contains a fallback that imports and constructs
installed providers directly. As a result, provider installation is dynamic
while provider behavior and configuration remain hardcoded in the host.

The CLI must become a thin host. Provider packages must own their adapter
implementations and safe route defaults. A versioned configuration file must
control provider activation, environment bindings, credential references, and
provider options without containing secret values.

## Goals

- Reuse and deepen the existing contract-owned plugin interface; do not create
  a second adapter-contract package or parallel discovery mechanism.
- Move every concrete CLI adapter implementation into the package that owns
  the corresponding connector.
- Remove provider IDs, schemes, hosts, environment-variable names, adapter
  classes, and provider imports from the CLI implementation.
- Load provider configuration from a strict, versioned TOML document.
- Treat provider IDs as canonical identities validated against installed entry
  point descriptors, never as user-defined aliases.
- Treat `key` as a credential reference. Never store credential values in the
  TOML document.
- Preserve independent package installation, import, discovery, disablement,
  and removal.
- Preserve deterministic route-collision checks and credential-safe errors.
- Replace the secret-bearing `--token` option with credential-reference
  overrides.

## Non-goals

- Configuration does not override canonical provider IDs, schemes, hosts,
  capabilities, modes, or connector versions.
- Configuration does not declare Python import paths or arbitrary factories.
- Configuration does not install packages or discover providers outside the
  existing Python entry-point mechanism.
- This change does not add a general-purpose secret store.
- This change does not make local formats independently uninstallable from the
  `open-table-connector-local-files` distribution.
- This change does not alter connector wire contracts, table semantics, or
  receipt identities.

## Architectural Decisions

### Reuse the existing plugin seam

`open-table-connector-contract` remains the single provider-neutral seam. The
existing `PluginDescriptor` is extended so a host can route and list a provider
without importing or constructing the concrete adapter. It owns immutable,
zero-I/O metadata and a lazy factory:

- canonical name and `ConnectorIdentity`;
- schemes and optional HTTPS hosts;
- capabilities and modes required for discovery and `otc list`;
- a factory returning an object that satisfies the adapter protocol.

The contract also owns the small neutral values required by both the host and
provider packages:

- `AdapterEndpoint` for URI, filesystem-path, and stdio endpoints;
- `AdapterOptions` for validated operation options;
- `ProviderConfig` for one configured provider;
- `ProviderFactoryContext` for config, resolved environment values,
  credential access, and test transports;
- `ConnectorAdapter`, the `read`, `inspect`, `write`, and optional
  `preflight_write` interface.

These types extend the interface already introduced for package plug/unplug.
They do not form a new package or a second registry.

### Provider packages own implementations

Each CLI entry point targets a provider-owned function returning a complete
descriptor. The descriptor factory returns a provider-owned adapter directly.
Provider packages depend downward on the contract, never upward on the CLI.
Provider packages may expose a separate descriptor for the neutral
`open_table_connector.providers` group, but the CLI entry point must target an
adapter descriptor and must not rely on the host to wrap a connector factory.

Ownership after migration:

| Adapter | Owning package |
| --- | --- |
| CSV, Excel, Markdown, JSON/JSONL/local compatibility | `local_files` |
| Google Sheets | `google_sheets` |
| Feishu Bitable | `feishu_bitable` |
| MaybeSheet | `maybe_sheet` |

The local-files distribution publishes distinct CLI adapter entry points for
its independently configurable identities even though they share one wheel.
The CLI package publishes no provider adapter entry points of its own.

### Descriptor defaults are authoritative

Canonical IDs, identities, schemes, hosts, capabilities, and modes come from
the installed provider descriptor. The configuration file cannot change these
values. This prevents configuration from redirecting a trusted provider
factory onto an unrelated scheme or impersonating another connector.

Installed descriptors are enabled by default. Configuration can disable an
adapter or provide runtime bindings, but cannot rewrite its identity or routes.

## Configuration

### Location and precedence

The CLI resolves configuration in this order:

1. an explicitly injected path supplied by an embedding caller or test;
2. the `OTC_CONFIG` environment variable;
3. `$XDG_CONFIG_HOME/open-table-connector/config.toml` when
   `XDG_CONFIG_HOME` is set;
4. `~/.config/open-table-connector/config.toml`;
5. no document, which is equivalent to enabling every installed descriptor
   with empty runtime bindings.

The loader reads one document. It does not merge multiple files or walk parent
directories. A present document must be a bounded regular non-symlink file and
is opened and verified without a path-swap window, following the existing
process-bootstrap file-safety rules.

### Closed TOML schema

```toml
schema_version = "otc.cli-config/v1"

[[providers]]
id = "google_sheets"
enabled = true
key = "work-google"
env = { endpoint = "OTC_GOOGLE_ENDPOINT" }
options = { timeout_seconds = 30 }

[credentials."work-google"]
access_token = { env = "GOOGLE_SHEETS_ACCESS_TOKEN" }
```

Each item in the `providers` array has this closed shape:

- `id`: required canonical provider ID; it must equal the installed
  descriptor identity; duplicate IDs are rejected;
- `enabled`: optional Boolean, defaulting to `true`;
- `key`: optional non-empty credential reference;
- `env`: optional mapping from provider-owned logical setting names to process
  environment-variable names;
- `options`: optional closed provider-owned mapping whose values are safe TOML
  scalars or arrays of safe scalars. Secret-like option names are rejected so
  credentials cannot be smuggled into this table.

Credential entries map logical secret field names to a closed source object.
Version 1 supports only `{ env = "VARIABLE_NAME" }`. Literal credential
values, command substitutions, file reads, and nested arbitrary objects are
rejected. An injected deployment resolver may use the same credential key to
resolve values from another store and ignore the environment bindings.

Unknown top-level fields, provider fields, credential-source fields, duplicate
tables, invalid types, blank names, and unsupported schema versions fail before
any provider factory runs. Provider-owned `options` are validated by that
provider before it performs I/O.

### Installed and removed providers

An installed descriptor with no config item uses its safe defaults and is
enabled. A disabled entry is omitted from the registry and its factory is never
called.

Configuration for an uninstalled provider is ignored with a credential-safe
diagnostic. This allows a package to be unplugged without making the CLI host
unusable. Because route metadata is descriptor-owned, an absent provider does
not leave behind a routable phantom adapter.

## Credential and Environment Handling

The configuration document contains references and environment-variable names,
not secret values. The host resolves an adapter's declared non-secret `env`
bindings into a logical mapping and supplies the mapping in
`ProviderFactoryContext`.

Credential resolution is injected through the existing deployment-owned
pattern: a resolver receives the canonical provider ID and configured `key`
and returns a scoped credential lease. The default CLI resolver supports the
closed `[credentials]` environment bindings. Provider factories and adapters
consume logical fields such as `access_token`; they do not know process
environment-variable names.

Credential mappings and transports are excluded from `repr`, equality,
serialization, route metadata, list output, diagnostics, and hashes. Missing
required credential fields fail with a stable authentication/configuration
error that includes only the canonical provider ID, credential key, and missing
logical field names.

The secret-bearing `--token` option is removed. A repeatable
`--credential-key PROVIDER=REFERENCE` option may override configured references
for one invocation. The override carries only a reference and is validated
against installed canonical provider IDs.

## Discovery and Data Flow

Startup and operation follow this sequence:

1. Parse CLI arguments without importing provider packages.
2. Load and validate the TOML document.
3. Discover and load zero-I/O descriptors from
   `open_table_connector.cli_adapters` entry points in deterministic order.
4. Match config entries by canonical descriptor ID and apply enablement and
   reference overrides.
5. Register descriptor routes and reject collisions before any factory or
   credential resolver runs.
6. `otc list` renders descriptor metadata without constructing adapters or
   resolving credentials.
7. When a command selects a route, resolve only that provider's environment
   and credential reference, construct its adapter lazily, and dispatch through
   the contract protocol.
8. Dispose the credential lease when the command finishes.

The host owns parsing, configuration precedence, registry dispatch, pipeline
orchestration, and output. The provider owns option interpretation, connector
construction, request translation, route defaults, and provider-specific
write policy.

## CLI and Provider Changes

### Contract package

- Deepen `PluginDescriptor` with capabilities, modes, and a typed factory.
- Add the neutral adapter/config/context protocols and frozen values.
- Validate canonical descriptor/config relationships and route metadata.
- Keep imports zero-I/O and provider-neutral.

### CLI package

- Add a TOML loader and environment-backed credential resolver.
- Make plugin discovery return configured lazy registrations rather than
  concrete provider objects.
- Make the registry route descriptors and instantiate adapters lazily.
- Keep endpoint parsing, command parsing, output formatting, and pipeline
  orchestration generic.
- Remove concrete adapters, provider factories, provider ID dispatch maps,
  provider environment-variable names, provider imports, and fallback
  construction.
- Remove CLI-owned CSV, Excel, and Markdown entry points.

### Provider packages

- Move the corresponding adapter implementation and its request translation
  into the provider package.
- Return complete descriptors from provider-owned entry points.
- Consume logical config, environment, and credential fields from
  `ProviderFactoryContext`.
- Keep entry-point import and descriptor construction free of I/O.

## Error Handling

Configuration and discovery failures use stable credential-safe diagnostics:

- invalid TOML or schema: configuration error with path and field name only;
- canonical ID mismatch: configuration error naming the configured ID and
  installed descriptor ID;
- duplicate route: conflict naming only scheme and safe host;
- unavailable configured provider: non-fatal diagnostic naming only its
  canonical ID;
- missing environment binding: configuration error naming the logical field
  and environment-variable name, never any value;
- unresolved credential reference: authentication error naming the provider
  ID and reference;
- provider factory failure: preserve an existing typed `ConnectorError`, or
  wrap an unexpected exception without including config, environment, or
  credential values.

No error includes raw TOML contents, process environment values, credential
values, provider response bodies, or physical URIs containing credentials.

## Compatibility and Migration

- With no config file, every installed descriptor remains enabled and existing
  URI routing continues to work.
- Canonical provider IDs and route schemes remain unchanged.
- `build_default_registry` retains dependency-injection parameters for tests
  and embedders, but accepts config and credential resolver objects rather than
  provider-specific environment conventions.
- The current `env` and `transports` test seams migrate into
  `ProviderFactoryContext`; provider tests no longer require the CLI package.
- `--token` is removed in the same release and documentation is migrated to
  credential keys and environment-backed credential entries.
- The old `build_adapters` fallback and `_wrap_provider_adapter` path are
  deleted rather than retained as a compatibility layer.

## Testing Strategy

### Contract tests

- closed `ProviderConfig`, endpoint, options, factory-context, and descriptor
  validation;
- descriptor/config canonical ID agreement;
- route collision and HTTPS host validation;
- credential-bearing fields excluded from representation and serialization;
- provider-neutral isolated imports.

### CLI tests

- config path precedence and no-config defaults;
- valid TOML parsing and every closed-schema rejection path;
- installed enabled, installed disabled, and configured-but-uninstalled
  behavior;
- lazy factories and no credential resolution for `list`;
- environment-backed and injected resolver behavior;
- repeatable credential-key overrides;
- duplicate route rejection before provider construction;
- redaction of secret values from stdout, stderr, exceptions, and reprs;
- CLI-only import and execution with no provider distributions.

### Provider tests

- adapter behavior moves from CLI tests into each owning package;
- descriptor construction performs no I/O;
- factories consume logical config and credentials without reading global
  environment names;
- provider options are closed and validated before connector I/O;
- existing read, inspect, write, preflight, receipt, and redaction behavior is
  preserved.

### Package and integration gates

- Build all wheels and run the independent install/uninstall matrix.
- Install the CLI alone and verify help/list/config errors without providers.
- Install each provider alongside the CLI and verify only its routes appear.
- Remove each provider while leaving its config entry and verify the CLI still
  runs with a safe diagnostic.
- Run the existing compatibility verifier, wheel smoke tests, provider suites,
  CLI suites, and universal conformance tests.

## Acceptance Criteria

- `packages/cli` contains no concrete provider adapter implementation or
  provider-specific import/factory map.
- `packages/cli` contains no provider IDs, provider schemes/hosts, or provider
  environment-variable names.
- Every CLI adapter implementation and entry point lives in its provider
  package.
- Configuration is strict, versioned, credential-free, and keyed by canonical
  provider IDs.
- Descriptor routes remain safe defaults and cannot be changed by config.
- `otc list` performs no provider construction or credential resolution.
- Removing any provider wheel leaves contract, CLI, process, and remaining
  provider imports operational.
- All route collisions, configuration failures, and credential failures are
  deterministic and credential-safe.
- Reused identifiers are imported from canonical constants rather than
  repeated as literals.
