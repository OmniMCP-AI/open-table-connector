# Config-Driven Provider-Owned CLI Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the OTC CLI a config-driven plugin host whose concrete adapters, routes, environment bindings, and credential interpretation live in independently installable provider packages.

**Architecture:** Deepen the existing contract-owned `PluginDescriptor` seam with neutral adapter/configuration types. Build a strict TOML overlay and lazy configured registry in the CLI, move each adapter implementation into its provider package, then delete all provider-specific CLI construction and route knowledge.

**Tech Stack:** Python 3.11–3.14, stdlib `tomllib`, `importlib.metadata` entry points, frozen dataclasses/protocols, PyArrow, Polars, pytest, Ruff, setuptools, uv.

**Spec:** `docs/superpowers/specs/2026-08-31-config-driven-cli-adapters-design.md`

## Global Constraints

- Reuse `open_table_connector.contract.PluginDescriptor`; do not add another plugin registry or adapter-contract distribution.
- Canonical IDs, schemes, hosts, capabilities, and modes remain provider-descriptor metadata and cannot be overridden by TOML.
- The CLI must contain no provider IDs, provider schemes/hosts, provider environment-variable names, concrete provider adapter classes, or provider import/factory maps after cutover.
- Provider packages may depend on contract/timeseries but must not depend on CLI or process.
- Config schema version is exactly `otc.cli-config/v1`.
- Config lookup precedence is injected path, `OTC_CONFIG`, `$XDG_CONFIG_HOME/open-table-connector/config.toml`, `~/.config/open-table-connector/config.toml`, then no config.
- Config files contain only references, environment-variable names, and non-secret options; literal secrets and secret-like option names are rejected.
- Installed adapters default to enabled; stale config for an uninstalled provider is non-fatal and credential-safe.
- Descriptor loading and `otc list` perform no provider construction, credential resolution, or I/O.
- Replace `--token` with repeatable `--credential-key PROVIDER=REFERENCE`; never accept a secret on the command line.
- Every reused package/provider/scheme/config token is imported from one canonical constant.
- Preserve the current unrelated full-suite baseline while this plan executes; do not fold hosted-transport or PostgreSQL transaction fixes into this feature.
- Recorded pre-plan full-suite baseline: 844 passed, 3 skipped, and 24 failed in hosted-transport bounds/error mapping, PostgreSQL transaction setup, and legacy parser/security tests; focused feature gates must pass, and the final report must distinguish remaining baseline failures from regressions.
- Every task ends in a commit pushed to both `origin/codex/critical-review-remediation` and `origin/main`.

## File Structure

### Contract-owned seam

- `packages/contract/src/open_table_connector/contract/adapters.py` — neutral endpoint, format, operation options, provider config/context, and adapter protocol.
- `packages/contract/src/open_table_connector/contract/plugins.py` — immutable descriptor metadata, lazy factory, local/path ownership, and route validation.
- `packages/contract/src/open_table_connector/contract/names.py` — shared config, provider, scheme, format, and entry-point constants.

### CLI host

- `packages/cli/src/open_table_connector/cli/configuration.py` — secure path resolution and closed TOML parsing.
- `packages/cli/src/open_table_connector/cli/credentials.py` — environment-backed credential leases and reference overrides.
- `packages/cli/src/open_table_connector/cli/configured_registry.py` — descriptor routing and lazy adapter activation during migration.
- `packages/cli/src/open_table_connector/cli/plugins.py` — final deterministic entry-point discovery only.
- `packages/cli/src/open_table_connector/cli/registry.py` — final public registry facade over configured registrations.
- `packages/cli/src/open_table_connector/cli/model.py` — CLI parsing plus re-exports of neutral contract values.
- `packages/cli/src/open_table_connector/cli/pipeline.py` — generic orchestration through adapter leases.
- `packages/cli/src/open_table_connector/cli/__main__.py` — config loading and reference-only command-line overrides.

### Provider-owned adapters

- `packages/local_files/src/open_table_connector/local_files/cli_adapter.py` — CSV, Excel, Markdown, JSON/JSONL/local adapters and local format I/O.
- `packages/google_sheets/src/open_table_connector/google_sheets/cli_adapter.py` — Google Sheets adapter.
- `packages/feishu_bitable/src/open_table_connector/feishu_bitable/cli_adapter.py` — Feishu Bitable adapter.
- `packages/maybe_sheet/src/open_table_connector/maybe_sheet/cli_adapter.py` — MaybeSheet adapter.
- Provider `plugin.py` and `pyproject.toml` files — provider-owned CLI descriptors and entry points.

---

### Task 1: Deepen the Existing Contract Plugin Seam

**Files:**
- Create: `packages/contract/src/open_table_connector/contract/adapters.py`
- Modify: `packages/contract/src/open_table_connector/contract/plugins.py`
- Modify: `packages/contract/src/open_table_connector/contract/names.py`
- Modify: `packages/contract/src/open_table_connector/contract/errors.py`
- Modify: `packages/contract/src/open_table_connector/contract/__init__.py`
- Create: `packages/contract/tests/test_adapters.py`
- Modify: `packages/contract/tests/test_plugins.py`
- Modify: `packages/contract/tests/test_errors.py`

**Interfaces:**
- Consumes: existing `ConnectorIdentity`, `CapabilityIdentity`, `TableMode`, `TableURI`, `ArrowReadResult`, `TableInspection`, and `TableWriteResult`.
- Produces: `ConfigScalar`, `ConfigValue`, `AdapterFormat`, `AdapterEndpoint`, `AdapterOptions`, `parse_adapter_endpoint`, `parse_adapter_format`, `ProviderConfig`, `ProviderFactoryContext`, `ConnectorAdapter`, `WritePreflightAdapter`, `PROVIDER_IDS`, `ConnectorErrorCode.CONFIGURATION`, and an extended `PluginDescriptor` with `capabilities`, `modes`, `local`, and `handles_paths` metadata. CLI-group descriptor factories take exactly one `ProviderFactoryContext`; neutral provider-group descriptors may retain their connector-specific factory return type.

- [ ] **Step 1: Write failing contract tests for frozen neutral values and hidden secrets**

```python
from pathlib import Path

import pytest
from open_table_connector.contract import (
    AdapterEndpoint,
    AdapterFormat,
    AdapterOptions,
    ProviderConfig,
    ProviderFactoryContext,
    TableURI,
)


def test_provider_factory_context_hides_credentials_and_transports() -> None:
    config = ProviderConfig(
        provider_id=PROVIDER_GOOGLE_SHEETS,
        credential_reference="work-google",
        environment={SETTING_ENDPOINT: "OTC_GOOGLE_ENDPOINT"},
        options={OPTION_TIMEOUT_SECONDS: 30},
    )
    context = ProviderFactoryContext(
        config=config,
        environment={SETTING_ENDPOINT: "https://example.test"},
        credentials={CREDENTIAL_ACCESS_TOKEN: "provider-secret"},
        transports={PROVIDER_GOOGLE_SHEETS: object()},
    )

    assert "provider-secret" not in repr(context)
    assert "https://example.test" not in repr(context)
    assert "transports" not in repr(context)
    assert context.environment[SETTING_ENDPOINT] == "https://example.test"
    assert context.credentials[CREDENTIAL_ACCESS_TOKEN] == "provider-secret"


def test_adapter_endpoint_rejects_mixed_uri_and_path() -> None:
    with pytest.raises(ValueError, match="cannot have both"):
        AdapterEndpoint(
            raw="orders.csv",
            uri=TableURI("csv:///tmp/orders.csv"),
            path=Path("orders.csv"),
        )


def test_adapter_options_normalize_formats_and_validate_limits() -> None:
    options = AdapterOptions(from_format="json", output_format="jsonl")
    assert options.from_format is AdapterFormat.JSON
    assert options.output_format is AdapterFormat.JSONL
    with pytest.raises(ValueError, match="positive"):
        AdapterOptions(limit=0)


def test_parse_adapter_endpoint_keeps_file_scheme_knowledge_in_contract(tmp_path) -> None:
    endpoint = parse_adapter_endpoint((tmp_path / "orders.csv").as_uri())
    assert endpoint.uri is None
    assert endpoint.path == tmp_path / "orders.csv"
    assert endpoint.is_stdio is False


def test_configuration_error_exposes_only_explicit_safe_details() -> None:
    error = ConnectorError.configuration(
        "provider configuration is invalid",
        safe_details={"provider_id": PROVIDER_GOOGLE_SHEETS},
    )
    assert error.code is ConnectorErrorCode.CONFIGURATION
    assert error.to_wire()["safe_details"] == {
        "provider_id": PROVIDER_GOOGLE_SHEETS
    }
```

- [ ] **Step 2: Run the new contract tests and verify the red phase**

Run:

```bash
uv run --frozen python -m pytest packages/contract/tests/test_adapters.py -q
```

Expected: collection fails because the new contract symbols do not exist.

- [ ] **Step 3: Implement the neutral values and adapter protocol**

Add canonical `FORMAT_AUTO = "auto"`, `FORMAT_TABLE = "table"`,
`CLI_CONFIG_SCHEMA_VERSION = "otc.cli-config/v1"`,
`CLI_CONFIG_ENV = "OTC_CONFIG"`, `XDG_CONFIG_HOME_ENV = "XDG_CONFIG_HOME"`,
`CLI_CONFIG_DIRECTORY = "open-table-connector"`, and
`CLI_CONFIG_FILENAME = "config.toml"` to `contract/names.py`. Also add shared
capability/action constants `CAPABILITY_TABLE_READ_ARROW =
"table.read.arrow"`, `CAPABILITY_TABLE_WRITE = "table.write"`,
`IF_EXISTS_APPEND = "append"`, `IF_EXISTS_REPLACE = "replace"`, and
`IF_EXISTS_ERROR = "error"`. Add shared logical-field
constants `CREDENTIAL_ACCESS_TOKEN = "access_token"`,
`CREDENTIAL_TENANT_ACCESS_TOKEN = "tenant_access_token"`,
`SETTING_ENDPOINT = "endpoint"`, `SETTING_BINARY = "binary"`, and
`OPTION_TIMEOUT_SECONDS = "timeout_seconds"`; these are vocabulary keys, not
secret values or process environment-variable names. Add `PROVIDER_IDS` as a
tuple composed only from the existing `PROVIDER_*` constants plus `SCHEME_MD`,
which is also the canonical Markdown adapter identity; do not add a second
Markdown constant with the same value. Export all of
them from `contract.__init__` and assert their exact values once in contract
tests. In `adapters.py`, implement these exact public shapes:

```python
class AdapterFormat(StrEnum):
    AUTO = FORMAT_AUTO
    CSV = PROVIDER_CSV
    EXCEL = PROVIDER_EXCEL
    JSON = PROVIDER_JSON
    JSONL = PROVIDER_JSONL
    TABLE = FORMAT_TABLE


ConfigScalar: TypeAlias = str | int | float | bool
ConfigValue: TypeAlias = ConfigScalar | tuple[ConfigScalar, ...]


@dataclass(frozen=True)
class AdapterEndpoint:
    raw: str
    uri: TableURI | None = None
    path: Path | None = None
    is_stdio: bool = False


@dataclass(frozen=True)
class AdapterOptions:
    from_format: AdapterFormat = AdapterFormat.AUTO
    output_format: AdapterFormat = AdapterFormat.AUTO
    to_format: AdapterFormat = AdapterFormat.AUTO
    limit: int | None = None
    timeout: float | int | None = None
    sheet: str | None = None
    range: str | None = None
    field_names: tuple[str, ...] = ()
    if_exists: str = IF_EXISTS_ERROR
    target: str | None = None


@dataclass(frozen=True)
class ProviderConfig:
    provider_id: str
    enabled: bool = True
    credential_reference: str | None = None
    environment: Mapping[str, str] = field(default_factory=dict)
    options: Mapping[str, ConfigValue] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderFactoryContext:
    config: ProviderConfig
    environment: Mapping[str, str] = field(default_factory=dict, repr=False, compare=False)
    credentials: Mapping[str, str] = field(default_factory=dict, repr=False, compare=False)
    transports: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)


@runtime_checkable
class ConnectorAdapter(Protocol):
    identity: ConnectorIdentity
    schemes: tuple[str, ...]
    hosts: tuple[str, ...]
    capabilities: tuple[CapabilityIdentity, ...]
    modes: tuple[TableMode, ...]

    def read(self, endpoint: AdapterEndpoint, options: AdapterOptions) -> ArrowReadResult: ...
    def inspect(self, endpoint: AdapterEndpoint, options: AdapterOptions) -> TableInspection: ...
    def write(
        self, endpoint: AdapterEndpoint, table: pa.Table, options: AdapterOptions
    ) -> TableWriteResult: ...


@runtime_checkable
class WritePreflightAdapter(Protocol):
    def preflight_write(
        self, endpoint: AdapterEndpoint, options: AdapterOptions
    ) -> None: ...


def parse_adapter_endpoint(value: str) -> AdapterEndpoint: ...


def parse_adapter_format(value: str | None) -> AdapterFormat: ...
```

Normalize nested mappings to immutable copies in `__post_init__`; validate
blank IDs/references, positive bounds, valid endpoint state, scalar option
values, and tuple coercion exactly once in this module. Move the complete
Windows-drive, file-URI, URI, path, and stdio parsing rules from CLI
`model.py` into `parse_adapter_endpoint`; this keeps all scheme knowledge out
of the final CLI source. Keep the descriptor factory alias product-neutral
because the same descriptor type also serves the separate neutral provider
entry-point group; type each provider-owned CLI factory itself as
`Callable[[ProviderFactoryContext], ConnectorAdapter]`, and make CLI discovery
validate that convention before activation.

Add `CONFIGURATION = "configuration"` to `ConnectorErrorCode` and a
`ConnectorError.configuration(message, *, safe_details=None)` constructor.
Config/discovery code uses this typed error for invalid paths, schema, fields,
bindings, and descriptor mismatches. Unexpected provider factory failures use
`EXECUTION_FAILED`. Neither path places document contents, environment values,
credential values, or raw exceptions in `safe_details`.

- [ ] **Step 4: Extend `PluginDescriptor` without breaking its existing positional constructor**

Append fields after `hosts` so the existing `(name, identity, schemes,
factory, hosts)` calls remain valid:

```python
@dataclass(frozen=True)
class PluginDescriptor:
    name: str
    identity: ConnectorIdentity
    schemes: tuple[str, ...]
    factory: PluginFactory = field(repr=False, compare=False)
    hosts: tuple[str, ...] = ()
    capabilities: tuple[CapabilityIdentity, ...] = ()
    modes: tuple[TableMode, ...] = ()
    local: bool = False
    handles_paths: bool = False
```

Validate capability IDs, modes, Boolean metadata, `handles_paths` implying
`local`, and `identity.connector_id == name`. Update existing descriptors/tests
whose display name differed from the canonical ID. `local` classifies an
adapter for pipeline policy; `handles_paths` exclusively claims bare path and
stdio fallback routing.

- [ ] **Step 5: Run contract tests and static checks**

Run:

```bash
uv run --frozen python -m pytest packages/contract/tests -q
uv run --frozen ruff check packages/contract/src packages/contract/tests
```

Expected: all contract tests pass and Ruff reports no contract-package errors.

- [ ] **Step 6: Commit and push the contract seam**

```bash
git add packages/contract
git commit -m "feat: deepen provider adapter contract"
git push origin codex/critical-review-remediation
git push origin HEAD:main
```

### Task 2: Add Strict CLI TOML Configuration and Credential References

**Files:**
- Create: `packages/cli/src/open_table_connector/cli/configuration.py`
- Create: `packages/cli/src/open_table_connector/cli/credentials.py`
- Create: `packages/cli/tests/test_configuration.py`
- Create: `packages/cli/tests/test_credentials.py`
- Modify: `packages/cli/src/open_table_connector/cli/__init__.py`

**Interfaces:**
- Consumes: `ProviderConfig`, `CLI_CONFIG_SCHEMA_VERSION`, and `CLI_CONFIG_ENV` from Task 1.
- Produces: `CredentialBinding`, `CliConfig`, `resolve_config_path`, `load_cli_config`, `CredentialLease`, `CredentialResolver`, `EnvironmentCredentialResolver`, and `apply_credential_overrides`.

- [ ] **Step 1: Write failing tests for path precedence and closed TOML parsing**

```python
def test_explicit_config_path_wins_over_environment(tmp_path) -> None:
    explicit = tmp_path / "explicit.toml"
    configured = tmp_path / "configured.toml"
    assert resolve_config_path(
        explicit,
        {
            CLI_CONFIG_ENV: str(configured),
            XDG_CONFIG_HOME_ENV: str(tmp_path / "xdg"),
        },
        home=tmp_path / "home",
    ) == explicit


def test_load_cli_config_parses_references_without_secret_values(tmp_path) -> None:
    path = tmp_path / CLI_CONFIG_FILENAME
    path.write_text(
        f'''schema_version = "{CLI_CONFIG_SCHEMA_VERSION}"
[[providers]]
id = "{PROVIDER_GOOGLE_SHEETS}"
key = "work-google"
[credentials."work-google"]
{CREDENTIAL_ACCESS_TOKEN} = {{ env = "GOOGLE_SHEETS_ACCESS_TOKEN" }}
'''
    )
    config = load_cli_config(path, environ={})
    assert config.providers[PROVIDER_GOOGLE_SHEETS].credential_reference == "work-google"
    assert config.credentials["work-google"][CREDENTIAL_ACCESS_TOKEN].env == (
        "GOOGLE_SHEETS_ACCESS_TOKEN"
    )


@pytest.mark.parametrize("field", ["token", "password", "api_key", "secret"])
def test_provider_options_reject_secret_like_fields(tmp_path, field: str) -> None:
    path = tmp_path / CLI_CONFIG_FILENAME
    path.write_text(
        f'''schema_version = "otc.cli-config/v1"
[[providers]]
id = "fixture"
options = {{ {field} = "literal-secret" }}
'''
    )
    with pytest.raises(ValueError, match="secret-like option"):
        load_cli_config(path, environ={})
```

Also add tests for wrong schema versions, unknown fields, duplicate provider
IDs, non-regular/symlink files, a bounded maximum file size, literal credential
values, absent default candidates meaning `CliConfig.empty()`, and an explicitly
selected missing path failing with a safe configuration error.

- [ ] **Step 2: Run configuration tests and verify the red phase**

Run:

```bash
uv run --frozen python -m pytest packages/cli/tests/test_configuration.py -q
```

Expected: collection fails because `cli.configuration` does not exist.

- [ ] **Step 3: Implement secure config lookup and parsing**

Implement these exact interfaces:

```python
CLI_CONFIG_MAX_BYTES = 1_048_576


@dataclass(frozen=True)
class CredentialBinding:
    env: str


@dataclass(frozen=True)
class CliConfig:
    providers: Mapping[str, ProviderConfig]
    credentials: Mapping[str, Mapping[str, CredentialBinding]]

    @classmethod
    def empty(cls) -> CliConfig: ...


def resolve_config_path(
    explicit: str | Path | None,
    environ: Mapping[str, str],
    *,
    home: Path | None = None,
) -> Path | None: ...


def load_cli_config(
    path: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> CliConfig: ...
```

Use `os.open` with `O_NOFOLLOW` where available, verify the opened descriptor
with `fstat`, and on platforms without `O_NOFOLLOW` compare pre-open `lstat`
device/inode/type data with `fstat` before reading. Bound reads to
`CLI_CONFIG_MAX_BYTES + 1`, decode UTF-8 strictly, and parse with
`tomllib.loads`. Parse only the exact schema from the spec.
Map every validation/read/parse failure to
`ConnectorErrorCode.CONFIGURATION` with only a safe path and field identifier;
never attach raw TOML text or a caught exception.

- [ ] **Step 4: Write failing credential resolver and override tests**

```python
def cli_config_with_credential(
    reference: str, logical_field: str, environment_name: str
) -> CliConfig:
    return CliConfig(
        providers={},
        credentials={
            reference: {logical_field: CredentialBinding(env=environment_name)}
        },
    )


def test_environment_resolver_returns_scoped_logical_credentials() -> None:
    config = cli_config_with_credential(
        "work-google", CREDENTIAL_ACCESS_TOKEN, "GOOGLE_TOKEN"
    )
    resolver = EnvironmentCredentialResolver(config, {"GOOGLE_TOKEN": "secret-value"})
    provider = ProviderConfig(
        PROVIDER_GOOGLE_SHEETS, credential_reference="work-google"
    )

    with resolver.resolve(provider) as lease:
        assert lease.values == {CREDENTIAL_ACCESS_TOKEN: "secret-value"}
        assert "secret-value" not in repr(lease)
    with pytest.raises(RuntimeError, match="disposed"):
        _ = lease.values


def test_credential_override_requires_provider_equals_reference() -> None:
    overrides = parse_credential_overrides(
        [f"{PROVIDER_GOOGLE_SHEETS}=work-google"]
    )
    assert overrides == {PROVIDER_GOOGLE_SHEETS: "work-google"}
    with pytest.raises(ValueError, match="PROVIDER=REFERENCE"):
        parse_credential_overrides(["work-google"])
```

- [ ] **Step 5: Implement scoped credential leases and reference-only overrides**

```python
class CredentialLease:
    def __init__(self, values: Mapping[str, str]) -> None: ...
    @property
    def values(self) -> Mapping[str, str]: ...
    def dispose(self) -> None: ...
    def __enter__(self) -> CredentialLease: ...
    def __exit__(self, *_: object) -> None: ...


class CredentialResolver(Protocol):
    def resolve(self, provider: ProviderConfig) -> CredentialLease: ...


class EnvironmentCredentialResolver:
    def __init__(self, config: CliConfig, environ: Mapping[str, str]) -> None: ...
    def resolve(self, provider: ProviderConfig) -> CredentialLease: ...


def parse_credential_overrides(values: Sequence[str]) -> Mapping[str, str]: ...


def apply_credential_overrides(
    config: CliConfig, overrides: Mapping[str, str]
) -> CliConfig: ...
```

Reject duplicate overrides, blank IDs/references, references absent from
`[credentials]`, and missing environment variables using safe field names
only. `apply_credential_overrides` performs structural/reference validation;
Task 3 validates override provider IDs against installed descriptors. Clear
each lease's copied values on exit.

- [ ] **Step 6: Run focused CLI configuration tests**

Run:

```bash
uv run --frozen python -m pytest packages/cli/tests/test_configuration.py packages/cli/tests/test_credentials.py -q
uv run --frozen ruff check packages/cli/src/open_table_connector/cli/configuration.py packages/cli/src/open_table_connector/cli/credentials.py packages/cli/tests/test_configuration.py packages/cli/tests/test_credentials.py
```

Expected: all new tests pass and Ruff is clean for the new modules.

- [ ] **Step 7: Commit and push config/credential support**

```bash
git add packages/cli/src/open_table_connector/cli/configuration.py packages/cli/src/open_table_connector/cli/credentials.py packages/cli/src/open_table_connector/cli/__init__.py packages/cli/tests/test_configuration.py packages/cli/tests/test_credentials.py
git commit -m "feat: add cli provider configuration"
git push origin codex/critical-review-remediation
git push origin HEAD:main
```

### Task 3: Build Generic Lazy Discovery and Activation Alongside the Legacy Registry

**Files:**
- Create: `packages/cli/src/open_table_connector/cli/configured_registry.py`
- Modify: `packages/cli/src/open_table_connector/cli/plugins.py`
- Create: `packages/cli/tests/test_configured_registry.py`
- Modify: `packages/cli/tests/test_plugins.py`

**Interfaces:**
- Consumes: `CliConfig`, `EnvironmentCredentialResolver`, `ProviderFactoryContext`, `PluginDescriptor`, and `ConnectorAdapter`.
- Produces: `ConfiguredPlugin`, `discover_configured_plugins`, and `ConfiguredConnectorRegistry` with descriptor-only listing, route resolution, capability checks, and context-managed lazy activation.

- [ ] **Step 1: Write failing fake-plugin tests for zero-I/O discovery and lazy activation**

```python
FIXTURE_PROVIDER_ID = "fixture"
FIXTURE_SCHEME = "fixture"
FIXTURE_CREDENTIAL_REFERENCE = "fixture-key"


class FakeAdapter:
    identity = ConnectorIdentity(FIXTURE_PROVIDER_ID, "0.1.0", "1.0")
    schemes = (FIXTURE_SCHEME,)
    hosts: tuple[str, ...] = ()
    capabilities = (CapabilityIdentity(CAPABILITY_TABLE_READ_ARROW, "1.0"),)
    modes = (TableMode.BASE,)

    def read(self, *_):
        raise AssertionError("operation is not part of this registry test")

    def inspect(self, *_):
        raise AssertionError("operation is not part of this registry test")

    def write(self, *_):
        raise AssertionError("operation is not part of this registry test")


class RecordingLease(CredentialLease):
    def __init__(self, calls: list[str]) -> None:
        super().__init__({})
        self._calls = calls

    def dispose(self) -> None:
        super().dispose()
        self._calls.append("dispose")


class RecordingResolver:
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    def resolve(self, provider: ProviderConfig) -> CredentialLease:
        assert provider.provider_id == FIXTURE_PROVIDER_ID
        self._calls.append("resolve")
        return RecordingLease(self._calls)


def fixture_descriptor(factory) -> PluginDescriptor:
    return PluginDescriptor(
        FIXTURE_PROVIDER_ID,
        FakeAdapter.identity,
        (FIXTURE_SCHEME,),
        factory,
        capabilities=FakeAdapter.capabilities,
        modes=FakeAdapter.modes,
    )


def fixture_config() -> CliConfig:
    return CliConfig(
        providers={
            FIXTURE_PROVIDER_ID: ProviderConfig(
                FIXTURE_PROVIDER_ID,
                credential_reference=FIXTURE_CREDENTIAL_REFERENCE,
            )
        },
        credentials={FIXTURE_CREDENTIAL_REFERENCE: {}},
    )


def recording_factory(calls: list[str]):
    def factory(context: ProviderFactoryContext) -> ConnectorAdapter:
        assert context.config.provider_id == FIXTURE_PROVIDER_ID
        calls.append("factory")
        return FakeAdapter()

    return factory


def test_list_does_not_call_factory_or_resolver() -> None:
    calls: list[str] = []
    descriptor = fixture_descriptor(
        factory=lambda context: calls.append("factory") or FakeAdapter()
    )
    resolver = RecordingResolver(calls)
    registry = ConfiguredConnectorRegistry.from_descriptors(
        (descriptor,), CliConfig.empty(), resolver=resolver
    )

    assert registry.list() == (descriptor,)
    assert calls == []


def test_open_adapter_scopes_credentials_around_factory_and_operation() -> None:
    calls: list[str] = []
    descriptor = fixture_descriptor(factory=recording_factory(calls))
    registry = ConfiguredConnectorRegistry.from_descriptors(
        (descriptor,), fixture_config(), resolver=RecordingResolver(calls)
    )

    with registry.open_adapter(parse_adapter_endpoint("fixture://table")) as adapter:
        calls.append(adapter.identity.connector_id)

    assert calls == ["resolve", "factory", "fixture", "dispose"]
```

Add tests for descriptor sorting, disabled providers, configured-but-absent
diagnostics, duplicate routes before factory calls, HTTPS host routing, local
path/stdin routing through exactly one `descriptor.handles_paths`, rejection of
duplicate path handlers, and capability rejection using descriptor metadata
only. Also assert that a credential override naming an
uninstalled or disabled provider fails before resolver/factory calls.

- [ ] **Step 2: Run the new registry tests and verify the red phase**

Run:

```bash
uv run --frozen python -m pytest packages/cli/tests/test_configured_registry.py -q
```

Expected: collection fails because `ConfiguredConnectorRegistry` is missing.

- [ ] **Step 3: Implement configured plugin records and deterministic discovery**

```python
@dataclass(frozen=True)
class ConfiguredPlugin:
    descriptor: PluginDescriptor
    config: ProviderConfig


def discover_configured_plugins(
    config: CliConfig,
    *,
    entries: Iterable[EntryPoint] | None = None,
) -> tuple[ConfiguredPlugin, ...]: ...
```

Load only `open_table_connector.cli_adapters`, verify each loaded object returns
`PluginDescriptor`, match config by `descriptor.identity.connector_id`, omit
disabled entries, synthesize `ProviderConfig(provider_id=descriptor.name)` for
installed descriptors absent from the document, and return missing configured
IDs as safe diagnostics on the registry. Do not import anything from a
provider namespace in the CLI module.

- [ ] **Step 4: Implement lazy descriptor routing and adapter activation**

```python
@dataclass
class ConfiguredConnectorRegistry:
    _plugins: list[ConfiguredPlugin] = field(default_factory=list)

    @classmethod
    def from_descriptors(
        cls,
        descriptors: Iterable[PluginDescriptor],
        config: CliConfig,
        *,
        resolver: CredentialResolver,
        environ: Mapping[str, str] | None = None,
        transports: Mapping[str, Any] | None = None,
    ) -> ConfiguredConnectorRegistry: ...

    def list(self) -> tuple[PluginDescriptor, ...]: ...
    def descriptor_for(self, endpoint: AdapterEndpoint) -> PluginDescriptor: ...
    def require_capability(
        self, endpoint: AdapterEndpoint, capability_id: str
    ) -> PluginDescriptor: ...

    @contextmanager
    def open_adapter(self, endpoint: AdapterEndpoint) -> Iterator[ConnectorAdapter]: ...
```

`open_adapter` resolves `ProviderConfig.environment` variable names against the
registry's injected environment mapping into a separate logical
`ProviderFactoryContext.environment` mapping, enters one credential lease,
builds the context with at most the selected provider's canonical transport
key, validates the returned object against `ConnectorAdapter`, yields it, and
disposes the lease on every exit path. Missing non-secret
environment variables identify only the provider, logical field, and variable
name.

During registration, build URI route keys from `descriptor.route_keys()` and a
separate optional path fallback from `descriptor.handles_paths`. Reject a
second path handler before any factory/resolver call. `descriptor_for` uses the
path handler only for `endpoint.path` or stdio and never infers provider IDs or
schemes in CLI code.

- [ ] **Step 5: Run generic discovery tests plus CLI-only guarded imports**

Run:

```bash
uv run --frozen python -m pytest packages/cli/tests/test_configured_registry.py packages/cli/tests/test_plugins.py -q
uv run --frozen ruff check packages/cli/src/open_table_connector/cli/configured_registry.py packages/cli/src/open_table_connector/cli/plugins.py packages/cli/tests/test_configured_registry.py packages/cli/tests/test_plugins.py
```

Expected: all focused tests pass; guarded imports prove discovery works with no
provider distributions.

- [ ] **Step 6: Commit and push the generic registry**

```bash
git add packages/cli/src/open_table_connector/cli/configured_registry.py packages/cli/src/open_table_connector/cli/plugins.py packages/cli/tests/test_configured_registry.py packages/cli/tests/test_plugins.py
git commit -m "feat: add lazy configured adapter registry"
git push origin codex/critical-review-remediation
git push origin HEAD:main
```

### Task 4: Move Local-File Adapter Implementations into `local_files`

**Files:**
- Create: `packages/local_files/src/open_table_connector/local_files/cli_adapter.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/plugin.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/__init__.py`
- Create: `packages/local_files/tests/test_cli_adapter.py`
- Create: `packages/local_files/tests/test_cli_plugin.py`
- Reference during migration: `packages/cli/src/open_table_connector/cli/adapters.py`
- Reference during migration: `packages/cli/src/open_table_connector/cli/formats.py`

**Interfaces:**
- Consumes: Task 1 contract types and existing local connector/read/write/receipt modules.
- Produces: `CsvCliAdapter`, `ExcelCliAdapter`, `MarkdownCliAdapter`, `LocalFilesCliAdapter`, plus `csv_cli_plugin`, `excel_cli_plugin`, `markdown_cli_plugin`, and `local_files_cli_plugin`.

- [ ] **Step 1: Move local adapter behavior tests to the owning package and make them fail**

Create provider-local tests covering explicit CSV/Excel/Markdown schemes,
path/stdio JSON and JSONL, format inference, row limits, inspection receipt
identity, write behavior, descriptor metadata, and rejection of non-empty
provider `environment`/`options` before filesystem or stdio access. Include
this ownership test:

```python
@pytest.mark.parametrize(
    ("factory", "provider_id", "schemes", "local", "handles_paths"),
    (
        (csv_cli_plugin, PROVIDER_CSV, (PROVIDER_CSV,), True, False),
        (
            excel_cli_plugin,
            PROVIDER_EXCEL,
            (PROVIDER_EXCEL, SCHEME_XLSX),
            True,
            False,
        ),
        (markdown_cli_plugin, SCHEME_MD, (SCHEME_MD,), True, False),
        (
            local_files_cli_plugin,
            PROVIDER_LOCAL_FILES,
            (SCHEME_FILE, PROVIDER_JSON, PROVIDER_JSONL),
            True,
            True,
        ),
    ),
)
def test_local_cli_descriptors_are_provider_owned(
    factory, provider_id, schemes, local, handles_paths
):
    descriptor = factory()
    assert descriptor.identity.connector_id == provider_id
    assert descriptor.schemes == schemes
    assert descriptor.local is local
    assert descriptor.handles_paths is handles_paths
    assert descriptor.factory.__module__.startswith("open_table_connector.local_files")
```

- [ ] **Step 2: Run provider-local adapter tests and verify the red phase**

Run:

```bash
uv run --frozen python -m pytest packages/local_files/tests/test_cli_adapter.py packages/local_files/tests/test_cli_plugin.py -q
```

Expected: collection fails because `local_files.cli_adapter` does not exist.

- [ ] **Step 3: Move local format and adapter implementation into the provider**

Move, do not import, the relevant implementation from CLI `formats.py` and
the four local adapter classes from CLI `adapters.py`. Replace CLI model types
with `AdapterEndpoint`, `AdapterFormat`, and `AdapterOptions`. Use canonical
contract constants for every identity/scheme/format. Keep local receipt and
format helpers private to `local_files.cli_adapter` unless already public in a
local-files module. The four local factories accept empty config/runtime maps
only and reject unknown provider environment, option, credential, or transport
keys before local I/O.

Each factory has this form:

```python
def _csv_cli_factory(context: ProviderFactoryContext) -> ConnectorAdapter:
    return CsvCliAdapter(CsvConnector())


def csv_cli_plugin() -> PluginDescriptor:
    return PluginDescriptor(
        PROVIDER_CSV,
        CSV_CONNECTOR_IDENTITY,
        (PROVIDER_CSV,),
        _csv_cli_factory,
        capabilities=tuple(CSV_CAPABILITY_MANIFEST.capabilities),
        modes=tuple(CSV_CAPABILITY_MANIFEST.modes),
        local=True,
        handles_paths=False,
    )
```

Repeat the full descriptor metadata for Excel, Markdown, and local-files; do
not implement one factory in terms of a CLI host wrapper. Set `local=True` on
all four and `handles_paths=True` only on `local_files_cli_plugin`.

- [ ] **Step 4: Run all local-files tests and provider boundary checks**

Run:

```bash
uv run --frozen python -m pytest packages/local_files/tests -q
uv run --frozen python scripts/check_package_boundaries.py
uv run --frozen ruff check packages/local_files/src/open_table_connector/local_files/cli_adapter.py packages/local_files/tests/test_cli_adapter.py packages/local_files/tests/test_cli_plugin.py
```

Expected: all local-files tests pass, and no local-files source imports the CLI
or process package.

- [ ] **Step 5: Commit and push local adapter ownership**

```bash
git add packages/local_files
git commit -m "feat: move local cli adapters to provider"
git push origin codex/critical-review-remediation
git push origin HEAD:main
```

### Task 5: Move Google Sheets Adapter into `google_sheets`

**Files:**
- Create: `packages/google_sheets/src/open_table_connector/google_sheets/cli_adapter.py`
- Modify: `packages/google_sheets/src/open_table_connector/google_sheets/connector.py`
- Modify: `packages/google_sheets/src/open_table_connector/google_sheets/plugin.py`
- Modify: `packages/google_sheets/src/open_table_connector/google_sheets/__init__.py`
- Create: `packages/google_sheets/tests/test_cli_adapter.py`
- Reference during migration: `packages/cli/src/open_table_connector/cli/adapters.py`

**Interfaces:**
- Consumes: `ProviderFactoryContext`, Google connector requests/results, and canonical Google route constants.
- Produces: `GoogleSheetsCliAdapter` and `google_sheets_cli_plugin`.

- [ ] **Step 1: Write failing provider-owned Google adapter tests**

```python
@dataclass(frozen=True)
class RecordedCall:
    method: str
    url: str
    headers: dict[str, str]
    body: dict | None
    timeout: int | None


class RecordingTransport:
    def __init__(self, responses: Mapping[str, Mapping[str, Any]]) -> None:
        self._responses = responses
        self.calls: list[RecordedCall] = []

    def request(self, method, url, *, headers, body=None, timeout=None):
        self.calls.append(RecordedCall(method, url, dict(headers), body, timeout))
        return self._responses[method]


def test_google_cli_factory_uses_logical_credentials_not_global_environment() -> None:
    transport = RecordingTransport({"GET": {"values": [["id"], ["1"]]}})
    context = ProviderFactoryContext(
        ProviderConfig(
            PROVIDER_GOOGLE_SHEETS,
            credential_reference="work-google",
            environment={SETTING_ENDPOINT: "GOOGLE_TEST_ENDPOINT"},
            options={OPTION_TIMEOUT_SECONDS: 7},
        ),
        environment={SETTING_ENDPOINT: "https://sheets.example.test"},
        credentials={CREDENTIAL_ACCESS_TOKEN: "configured-secret"},
        transports={PROVIDER_GOOGLE_SHEETS: transport},
    )
    adapter = google_sheets_cli_plugin().factory(context)

    result = adapter.read(
        parse_adapter_endpoint("gsheets://book/Orders"),
        AdapterOptions(range="A1:B2"),
    )

    assert result.table.to_pylist() == [{"id": "1"}]
    assert transport.calls[0].headers == {"Authorization": "Bearer configured-secret"}
    assert transport.calls[0].url.startswith("https://sheets.example.test/")
    assert transport.calls[0].timeout == 7


def test_google_cli_descriptor_owns_https_host_route() -> None:
    descriptor = google_sheets_cli_plugin()
    assert descriptor.identity.connector_id == PROVIDER_GOOGLE_SHEETS
    assert descriptor.route_keys() == (
        (SCHEME_GSHEETS, None),
        (SCHEME_HTTPS, HOST_GOOGLE_DOCS),
    )
```

- [ ] **Step 2: Run the tests and verify the red phase**

Run:

```bash
uv run --frozen python -m pytest packages/google_sheets/tests/test_cli_adapter.py -q
```

Expected: collection fails because the provider-owned CLI adapter is absent.

- [ ] **Step 3: Move the Google adapter and publish a dedicated CLI descriptor**

Move `GoogleSheetsAdapter` behavior from the CLI into
`google_sheets/cli_adapter.py`. The adapter reads only logical
`context.credentials[CREDENTIAL_ACCESS_TOKEN]`, consumes the transport under
the canonical `PROVIDER_GOOGLE_SHEETS` key, and does not read `os.environ`.
Non-secret endpoint/timeout behavior consumes `context.environment` and
`context.config.options` through canonical logical-field constants. Keep
connector construction and request translation provider-local. Add
`google_sheets_cli_plugin()` alongside the neutral `provider_plugin()`; do not
point both groups at the same connector factory. The provider accepts only
`SETTING_ENDPOINT` in `environment` and `OPTION_TIMEOUT_SECONDS` in `options`;
credentials accept only `CREDENTIAL_ACCESS_TOKEN`; unknown keys or wrong types
fail before transport I/O. Add one provider-local
`GOOGLE_SHEETS_API_ENDPOINT` constant and parameterize connector URL assembly
so the default wire behavior remains unchanged. The adapter's identity,
schemes, hosts, capabilities, and modes exactly match its descriptor metadata.

- [ ] **Step 4: Run Google and focused contract tests**

Run:

```bash
uv run --frozen python -m pytest packages/google_sheets/tests packages/contract/tests/test_adapters.py packages/contract/tests/test_plugins.py -q
uv run --frozen ruff check packages/google_sheets/src packages/google_sheets/tests/test_cli_adapter.py
```

Expected: provider adapter tests pass; any pre-existing hosted transport test
baseline remains unchanged.

- [ ] **Step 5: Commit and push Google adapter ownership**

```bash
git add packages/google_sheets
git commit -m "feat: move google cli adapter to provider"
git push origin codex/critical-review-remediation
git push origin HEAD:main
```

### Task 6: Move Feishu Bitable Adapter into `feishu_bitable`

**Files:**
- Create: `packages/feishu_bitable/src/open_table_connector/feishu_bitable/cli_adapter.py`
- Modify: `packages/feishu_bitable/src/open_table_connector/feishu_bitable/plugin.py`
- Modify: `packages/feishu_bitable/src/open_table_connector/feishu_bitable/identity.py`
- Modify: `packages/feishu_bitable/src/open_table_connector/feishu_bitable/connector.py`
- Modify: `packages/feishu_bitable/src/open_table_connector/feishu_bitable/__init__.py`
- Create: `packages/feishu_bitable/tests/test_cli_adapter.py`
- Reference during migration: `packages/cli/src/open_table_connector/cli/adapters.py`

**Interfaces:**
- Consumes: `ProviderFactoryContext`, Feishu connector requests/results, and canonical Feishu route constants.
- Produces: `FeishuBitableCliAdapter` and `feishu_bitable_cli_plugin`.

- [ ] **Step 1: Write failing provider-owned Feishu adapter tests**

```python
@dataclass(frozen=True)
class RecordedCall:
    method: str
    url: str
    headers: dict[str, str]
    body: dict | None
    timeout: int | None


class RecordingTransport:
    def __init__(self, responses: Mapping[str, Mapping[str, Any]]) -> None:
        self._responses = responses
        self.calls: list[RecordedCall] = []

    def request(self, method, url, *, headers, body=None, timeout=None):
        self.calls.append(RecordedCall(method, url, dict(headers), body, timeout))
        return self._responses[method]


def test_feishu_cli_factory_uses_logical_tenant_token() -> None:
    transport = RecordingTransport(
        {"GET": {"code": 0, "data": {"items": [], "has_more": False}}}
    )
    context = ProviderFactoryContext(
        ProviderConfig(
            PROVIDER_FEISHU_BITABLE,
            credential_reference="work-feishu",
            environment={SETTING_ENDPOINT: "FEISHU_TEST_ENDPOINT"},
            options={OPTION_TIMEOUT_SECONDS: 9},
        ),
        environment={SETTING_ENDPOINT: "https://feishu.example.test"},
        credentials={CREDENTIAL_TENANT_ACCESS_TOKEN: "configured-secret"},
        transports={PROVIDER_FEISHU_BITABLE: transport},
    )
    adapter = feishu_bitable_cli_plugin().factory(context)

    adapter.inspect(
        parse_adapter_endpoint("feishu://app/table"), AdapterOptions(limit=1)
    )

    assert transport.calls[0].headers == {"Authorization": "Bearer configured-secret"}
    assert transport.calls[0].url.startswith("https://feishu.example.test/")
    assert transport.calls[0].timeout == 9


def test_feishu_adapter_preserves_provider_owned_record_id_policy() -> None:
    context = ProviderFactoryContext(
        ProviderConfig(PROVIDER_FEISHU_BITABLE),
        transports={PROVIDER_FEISHU_BITABLE: RecordingTransport({})},
    )
    adapter = feishu_bitable_cli_plugin().factory(context)
    assert adapter.provider_owned_fields == (FEISHU_RECORD_ID_FIELD,)
```

- [ ] **Step 2: Run the tests and verify the red phase**

Run:

```bash
uv run --frozen python -m pytest packages/feishu_bitable/tests/test_cli_adapter.py -q
```

Expected: collection fails because the provider-owned adapter is absent.

- [ ] **Step 3: Move Feishu adapter behavior and publish its CLI descriptor**

Move all Feishu-specific option translation, preflight write policy, record-ID
ownership, connector construction, and credentials into the provider package.
Use logical credential field `CREDENTIAL_TENANT_ACCESS_TOKEN`. Define
`FEISHU_RECORD_ID_FIELD = "_record_id"` once in the provider identity module
and replace all repeated literals in the connector and adapter.
`feishu_bitable_cli_plugin` advertises `(SCHEME_FEISHU,
PROVIDER_FEISHU_BITABLE)` and complete manifest metadata. The provider accepts
only `SETTING_ENDPOINT` in `environment` and `OPTION_TIMEOUT_SECONDS` in
`options`; credentials accept only `CREDENTIAL_TENANT_ACCESS_TOKEN`; unknown
keys or wrong types fail before transport I/O. Define one
provider-local `FEISHU_API_ENDPOINT` constant and parameterize connector URL
assembly without changing the default endpoint. The adapter's identity,
schemes, hosts, capabilities, and modes exactly match its descriptor metadata.

- [ ] **Step 4: Run Feishu and focused pipeline-policy tests**

Run:

```bash
uv run --frozen python -m pytest packages/feishu_bitable/tests/test_cli_adapter.py packages/cli/tests/test_pipeline.py -q
uv run --frozen ruff check packages/feishu_bitable/src packages/feishu_bitable/tests/test_cli_adapter.py
```

Expected: new adapter tests and existing provider-owned-field pipeline tests
pass; unrelated transport-baseline failures do not expand.

- [ ] **Step 5: Commit and push Feishu adapter ownership**

```bash
git add packages/feishu_bitable
git commit -m "feat: move feishu cli adapter to provider"
git push origin codex/critical-review-remediation
git push origin HEAD:main
```

### Task 7: Move MaybeSheet Adapter into `maybe_sheet`

**Files:**
- Create: `packages/maybe_sheet/src/open_table_connector/maybe_sheet/cli_adapter.py`
- Modify: `packages/maybe_sheet/src/open_table_connector/maybe_sheet/plugin.py`
- Modify: `packages/maybe_sheet/src/open_table_connector/maybe_sheet/process.py`
- Modify: `packages/maybe_sheet/src/open_table_connector/maybe_sheet/__init__.py`
- Create: `packages/maybe_sheet/tests/test_cli_adapter.py`
- Create: `packages/maybe_sheet/tests/test_process.py`
- Reference during migration: `packages/cli/src/open_table_connector/cli/adapters.py`

**Interfaces:**
- Consumes: `ProviderFactoryContext`, MaybeSheet connector/process types, and canonical MaybeSheet route constants.
- Produces: `MaybeSheetCliAdapter` and `maybe_sheet_cli_plugin`.

- [ ] **Step 1: Write failing provider-owned MaybeSheet tests**

```python
@dataclass(frozen=True)
class RecordedProcessCall:
    argv: tuple[str, ...]
    credentials: Mapping[str, str] | None
    stdin: str | None
    timeout: float | int | None


class RecordingProcess:
    def __init__(self, payload: Mapping[str, Any]) -> None:
        self._payload = payload
        self.calls: list[RecordedProcessCall] = []

    def run(self, argv, *, credentials=None, stdin=None, timeout=None):
        self.calls.append(
            RecordedProcessCall(argv, credentials, stdin, timeout)
        )
        return self._payload


def test_maybe_sheet_cli_adapter_passes_logical_credentials_per_request() -> None:
    process = RecordingProcess({"rows": [{"id": "1"}]})
    context = ProviderFactoryContext(
        ProviderConfig(PROVIDER_MAYBE_SHEET, credential_reference="work-maybe"),
        credentials={CREDENTIAL_ACCESS_TOKEN: "configured-secret"},
        transports={PROVIDER_MAYBE_SHEET: process},
    )
    adapter = maybe_sheet_cli_plugin().factory(context)

    result = adapter.read(
        parse_adapter_endpoint("maybe://doc/R_orders"), AdapterOptions(limit=1)
    )

    assert result.table.to_pylist() == [{"id": "1"}]
    assert process.calls[0].credentials == {
        CREDENTIAL_ACCESS_TOKEN: "configured-secret"
    }


def test_maybe_sheet_cli_adapter_rejects_bad_target_before_process_io() -> None:
    process = RecordingProcess({})
    context = ProviderFactoryContext(
        ProviderConfig(PROVIDER_MAYBE_SHEET),
        transports={PROVIDER_MAYBE_SHEET: process},
    )
    adapter = maybe_sheet_cli_plugin().factory(context)
    with pytest.raises(ConnectorError):
        adapter.read(parse_adapter_endpoint("maybe://doc/R/a"), AdapterOptions())
    assert process.calls == []
```

- [ ] **Step 2: Run the tests and verify the red phase**

Run:

```bash
uv run --frozen python -m pytest packages/maybe_sheet/tests/test_cli_adapter.py -q
```

Expected: collection fails because the provider-owned adapter is absent.

- [ ] **Step 3: Move MaybeSheet adapter behavior and publish its CLI descriptor**

Move MaybeSheet URI target mapping, capability metadata, process selection,
request credential mapping, and preflight write policy into the provider.
Factory precedence is injected transport, then provider-owned subprocess client
configured from logical non-secret environment/options. It must not inherit the
entire host environment implicitly. Use `CREDENTIAL_ACCESS_TOKEN` and
`PROVIDER_MAYBE_SHEET` for the logical credential and transport lookup keys.
The provider accepts only `SETTING_BINARY` in `environment` and
`OPTION_TIMEOUT_SECONDS` in `options`; unknown keys, a non-absolute configured
binary, a non-positive timeout, or any credential key other than
`CREDENTIAL_ACCESS_TOKEN` fails before process I/O. Keep `mbs` as the
no-config compatibility default. Change `SubprocessProcessClient` to build the
child environment from its explicit environment mapping plus scoped
credentials, rather than `os.environ.copy()`, and update its tests to prove an
unrelated sentinel host variable is absent. The adapter's identity, schemes,
hosts, capabilities, and modes exactly match its descriptor metadata.

- [ ] **Step 4: Run MaybeSheet tests and package-boundary checks**

Run:

```bash
uv run --frozen python -m pytest packages/maybe_sheet/tests -q
uv run --frozen python scripts/check_package_boundaries.py
uv run --frozen ruff check packages/maybe_sheet/src packages/maybe_sheet/tests/test_cli_adapter.py packages/maybe_sheet/tests/test_process.py
```

Expected: all MaybeSheet tests pass and the provider imports neither CLI nor
process host modules.

- [ ] **Step 5: Commit and push MaybeSheet adapter ownership**

```bash
git add packages/maybe_sheet
git commit -m "feat: move maybe sheet cli adapter to provider"
git push origin codex/critical-review-remediation
git push origin HEAD:main
```

### Task 8: Cut the CLI Over to Configured Provider-Owned Adapters

**Files:**
- Modify: `packages/cli/src/open_table_connector/cli/__main__.py`
- Modify: `packages/cli/src/open_table_connector/cli/model.py`
- Modify: `packages/cli/src/open_table_connector/cli/commands.py`
- Modify: `packages/cli/src/open_table_connector/cli/pipeline.py`
- Modify: `packages/cli/src/open_table_connector/cli/plugins.py`
- Modify: `packages/cli/src/open_table_connector/cli/registry.py`
- Delete: `packages/cli/src/open_table_connector/cli/adapters.py`
- Delete: `packages/cli/src/open_table_connector/cli/formats.py`
- Modify: `packages/cli/pyproject.toml`
- Modify: `packages/local_files/pyproject.toml`
- Modify: `packages/google_sheets/pyproject.toml`
- Modify: `packages/feishu_bitable/pyproject.toml`
- Modify: `packages/maybe_sheet/pyproject.toml`
- Modify: `packages/cli/tests/test_cli_e2e.py`
- Modify: `packages/cli/tests/test_commands.py`
- Modify: `packages/cli/tests/test_model.py`
- Modify: `packages/cli/tests/test_pipeline.py`
- Modify: `packages/cli/tests/test_plugins.py`
- Modify: `packages/cli/tests/test_registry.py`
- Delete or move: `packages/cli/tests/test_formats.py`
- Delete or move: `packages/cli/tests/test_local_format_adapters.py`

**Interfaces:**
- Consumes: all contract/config/registry/provider adapters produced by Tasks 1–7.
- Produces: the final provider-neutral `build_default_registry`, config-aware CLI startup, generic pipeline adapter leases, and provider-owned entry-point metadata.

- [ ] **Step 1: Update tests to require a provider-neutral CLI**

Add a static AST/source assertion and command-line behavior tests:

```python
ROOT = Path(__file__).resolve().parents[3]


def test_cli_source_has_no_provider_specific_names_or_imports() -> None:
    source_root = ROOT / "packages/cli/src/open_table_connector/cli"
    text = "\n".join(path.read_text() for path in source_root.glob("*.py"))
    for forbidden in (
        "GoogleSheetsAdapter",
        "FeishuBitableAdapter",
        "MaybeSheetAdapter",
        "LocalAdapter",
        "GOOGLE_SHEETS_ACCESS_TOKEN",
        "FEISHU_TENANT_ACCESS_TOKEN",
    ):
        assert forbidden not in text


def test_parser_accepts_references_and_rejects_removed_token_flag() -> None:
    override = f"{PROVIDER_GOOGLE_SHEETS}=work-google"
    args = build_parser().parse_args(
        ["--credential-key", override, "list"]
    )
    assert args.credential_key == [override]
    with pytest.raises(_ParserError):
        build_parser().parse_args(["read", "--from", "x", "--token", "secret"])
```

Update registry/pipeline tests to use `with registry.open_adapter(endpoint)` and
config credential bindings. Remove direct construction or imports of CLI-owned
adapter classes.

- [ ] **Step 2: Run CLI tests and verify the cutover red phase**

Run:

```bash
uv run --frozen python -m pytest packages/cli/tests -q
```

Expected: failures identify the legacy parser, registry, pipeline, entry points,
and CLI-owned adapter modules.

- [ ] **Step 3: Point every CLI entry point at its provider-owned adapter descriptor**

Remove CSV/Excel/Markdown entries from `packages/cli/pyproject.toml`. Publish
these exact provider-local entry points:

```toml
[project.entry-points."open_table_connector.cli_adapters"]
csv = "open_table_connector.local_files.cli_adapter:csv_cli_plugin"
excel = "open_table_connector.local_files.cli_adapter:excel_cli_plugin"
md = "open_table_connector.local_files.cli_adapter:markdown_cli_plugin"
local_files = "open_table_connector.local_files.cli_adapter:local_files_cli_plugin"
```

Google Sheets, Feishu Bitable, and MaybeSheet each point their CLI group at the
dedicated `*_cli_plugin` function while retaining separate neutral provider
entry points.

- [ ] **Step 4: Replace CLI models and registry with the neutral contract seam**

Make `cli.model` parse into `AdapterEndpoint` and re-export
`FormatName = AdapterFormat`, `CliOptions = AdapterOptions` only for source
compatibility. Also set `parse_endpoint = parse_adapter_endpoint` and
`parse_format = parse_adapter_format` as temporary source-compatibility aliases.
Derive parser values from enum members rather than scheme/provider constants:

```python
_FORMATS = tuple(item.value for item in AdapterFormat)
_OUTPUT_FORMATS = tuple(
    item.value
    for item in AdapterFormat
    if item in {
        AdapterFormat.CSV,
        AdapterFormat.JSON,
        AdapterFormat.JSONL,
        AdapterFormat.TABLE,
    }
)
```

Make `registry.py` expose the configured registry as `ConnectorRegistry` and
implement:

```python
def build_default_registry(
    *,
    config: CliConfig | None = None,
    config_path: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
    credential_resolver: CredentialResolver | None = None,
    transports: Mapping[str, Any] | None = None,
    credential_overrides: Mapping[str, str] | None = None,
) -> ConnectorRegistry: ...
```

The function loads config once, discovers descriptors, validates override
provider IDs against installed enabled descriptors, applies reference
overrides, registers routes, and returns without invoking a provider factory
or resolver.

- [ ] **Step 5: Make pipeline orchestration use descriptor metadata and adapter leases**

Replace `_is_local` scheme sets with `descriptor.local`. For each operation,
use `registry.require_capability` before I/O and hold adapters only for the
duration of their operation:

```python
def read_endpoint(endpoint, registry, options):
    registry.require_capability(endpoint, CAPABILITY_TABLE_READ_ARROW)
    with registry.open_adapter(endpoint) as adapter:
        return adapter.read(endpoint, options)


def import_endpoint(source, destination, registry, options):
    destination_descriptor = registry.require_capability(
        destination, CAPABILITY_TABLE_WRITE
    )
    if destination_descriptor.local:
        raise _unsupported(destination, "import destinations must be writable connectors")
    with registry.open_adapter(destination) as destination_adapter:
        if isinstance(destination_adapter, WritePreflightAdapter):
            destination_adapter.preflight_write(destination, options)
        result = read_endpoint(source, registry, options)
        table = _table_for_destination(result.table, result.receipt, destination_adapter)
        write_result = destination_adapter.write(destination, table, options)
    return _summary(result, write_result)
```

Conversion routes the destination through a provider-owned local adapter;
stdout remains redirected by the command host while local serialization lives
in `local_files`.

- [ ] **Step 6: Load config in `main` and remove secret CLI inputs**

Add global repeatable `--credential-key PROVIDER=REFERENCE`, remove `--token`
from parser flags and `AdapterOptions`, load config after parsing, and pass only
reference overrides to `build_default_registry`. Parser errors may expose the
provider ID/reference but never environment or credential values.

- [ ] **Step 7: Delete the legacy adapter/wrapper/fallback implementation**

Delete CLI `adapters.py`, CLI `formats.py`, `_wrap_provider_adapter`, all
provider-specific CLI factories, `build_adapters`, fallback provider imports,
and tests that were moved to provider packages. Update imports and `__all__`
exports so CLI-only installation imports successfully.

- [ ] **Step 8: Run the cutover test matrix**

Run:

```bash
uv lock
uv run --frozen python -m pytest packages/contract/tests packages/cli/tests packages/local_files/tests packages/google_sheets/tests/test_cli_adapter.py packages/feishu_bitable/tests/test_cli_adapter.py packages/maybe_sheet/tests/test_cli_adapter.py -q
uv run --frozen python scripts/check_package_boundaries.py
uv run --frozen ruff check packages/contract/src packages/cli/src packages/local_files/src/open_table_connector/local_files/cli_adapter.py packages/google_sheets/src/open_table_connector/google_sheets/cli_adapter.py packages/feishu_bitable/src/open_table_connector/feishu_bitable/cli_adapter.py packages/maybe_sheet/src/open_table_connector/maybe_sheet/cli_adapter.py
```

Expected: all focused tests and boundary checks pass; CLI source contains no
provider-specific construction or environment conventions.

- [ ] **Step 9: Commit and push the CLI cutover**

```bash
git add packages/contract packages/cli packages/local_files packages/google_sheets packages/feishu_bitable packages/maybe_sheet uv.lock
git commit -m "feat: configure provider owned cli adapters"
git push origin codex/critical-review-remediation
git push origin HEAD:main
```

### Task 9: Document, Audit, and Prove Independent Plug/Unplug Behavior

**Files:**
- Modify: `README.md`
- Modify: `packages/cli/README.md`
- Modify: `docs/getting-started.md`
- Modify: `docs/user-manual.md`
- Modify: `docs/demos.md`
- Modify: `docs/package-boundaries.md`
- Modify: `scripts/check_package_boundaries.py`
- Modify: `scripts/check_package_independence.py`
- Create: `scripts/check_canonical_literals.py`
- Modify: `packages/dbt/src/open_table_connector/dbt/connector.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/temporal_csv.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/temporal_excel.py`
- Modify: `packages/local_files/src/open_table_connector/local_files/temporal_json.py`
- Modify: `packages/maybe_sheet/src/open_table_connector/maybe_sheet/temporal.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `docs/reviews/2026-08-31-critical-review-remediation.md`
- Create: `packages/cli/tests/test_provider_independence.py`

**Interfaces:**
- Consumes: the completed configured provider adapter architecture.
- Produces: user-facing config instructions, automated source-boundary guards, wheel install/uninstall proof, and final remediation evidence.

- [ ] **Step 1: Add failing source and wheel independence assertions**

```python
from scripts.check_canonical_literals import check_canonical_literals


ROOT = Path(__file__).resolve().parents[3]
UNINSTALLED_PROVIDER_ID = "uninstalled_provider"


def read_python_tree(root: Path) -> str:
    return "\n".join(
        path.read_text()
        for path in sorted(root.rglob("*.py"))
        if "__pycache__" not in path.parts
    )


def run_cli(
    *args: str, env: Mapping[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    child_environment = os.environ.copy()
    if env is not None:
        child_environment.update(env)
    return subprocess.run(
        [sys.executable, "-m", "open_table_connector.cli", *args],
        capture_output=True,
        text=True,
        env=child_environment,
        check=False,
    )


def test_cli_has_no_provider_owned_tokens() -> None:
    cli_source = read_python_tree(ROOT / "packages/cli/src/open_table_connector/cli")
    for token in PROVIDER_IDS:
        assert repr(token) not in cli_source
    for token in (SCHEME_GSHEETS, SCHEME_FEISHU, SCHEME_MAYBE):
        assert repr(token) not in cli_source


def test_production_python_reuses_canonical_provider_and_route_constants() -> None:
    assert check_canonical_literals(ROOT) == []


def test_stale_disabled_or_missing_provider_config_does_not_break_list(tmp_path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        f'''schema_version = "{CLI_CONFIG_SCHEMA_VERSION}"
[[providers]]
id = "{UNINSTALLED_PROVIDER_ID}"
key = "removed-reference"
[credentials."removed-reference"]
{CREDENTIAL_ACCESS_TOKEN} = {{ env = "REMOVED_PROVIDER_SECRET" }}
'''
    )
    result = run_cli("list", env={CLI_CONFIG_ENV: str(config)})
    assert result.returncode == 0
    assert UNINSTALLED_PROVIDER_ID in result.stderr
    assert "credential" not in result.stderr.casefold()
```

Extend `check_package_boundaries.py` to reject CLI imports from every provider
namespace and `check_package_independence.py` to install the CLI plus exactly
one provider wheel, inspect its routes, then remove it while retaining config.
Derive provider names from canonical contract constants or built wheel
metadata; do not duplicate literal provider lists. Implement
`check_canonical_literals.py` with `ast`: read the values of `PROVIDER_*`,
`SCHEME_*`, and `HOST_*` assignments from `contract/names.py`, scan production
Python outside that file, and report any equal string literal with its file and
line. Replace every reported literal with its canonical import; do not add a
second constant with the same value.

- [ ] **Step 2: Run the new independence tests and verify the red phase**

Run:

```bash
uv run --frozen python -m pytest packages/cli/tests/test_provider_independence.py -q
```

Expected: failures identify missing source guards, stale-config diagnostics, or
wheel-matrix behavior.

- [ ] **Step 3: Update documentation with exact config and migration examples**

Document the default config path, `OTC_CONFIG`, the closed TOML example from
the spec, descriptor-owned routes, installed-by-default behavior, disablement,
environment credential bindings, injected resolvers, and repeatable
`--credential-key PROVIDER=REFERENCE`. Remove every `--token` example and every
claim that the CLI owns provider registration.

- [ ] **Step 4: Update automated boundary and independence gates**

Make CI run source-boundary checks, config tests, CLI-only tests, one-provider
wheel tests, stale-config uninstall tests, and the existing all-wheel matrix.
The scripts must exit nonzero with deterministic distribution/module names and
must not print environment or credential values.

- [ ] **Step 5: Run final focused and packaging verification**

Run:

```bash
uv run --frozen python -m pytest packages/contract/tests packages/cli/tests packages/local_files/tests packages/google_sheets/tests/test_cli_adapter.py packages/feishu_bitable/tests/test_cli_adapter.py packages/maybe_sheet/tests/test_cli_adapter.py -q
uv run --frozen python scripts/check_package_boundaries.py
uv run --frozen python scripts/check_canonical_literals.py
uv run --frozen python scripts/check_package_metadata.py
final_dist=$(mktemp -d /tmp/otc-config-adapters.XXXXXX)
uv run --frozen python scripts/check_package_independence.py --build "$final_dist"
uv run --frozen python scripts/verify_compatibility.py
uv run --frozen python scripts/smoke_wheels.py "$final_dist"
```

Expected: focused tests, boundary/metadata checks, independent wheel matrix,
compatibility verification, and wheel smoke tests all exit 0.

- [ ] **Step 6: Run the full suite and compare with the pre-task baseline**

Run:

```bash
uv run --frozen python -m pytest -q > /tmp/otc-config-adapters-full.txt 2>&1
test_rc=$?
tail -100 /tmp/otc-config-adapters-full.txt
echo "FULL_TEST_EXIT:$test_rc"
```

Expected: no failure is attributable to config loading, discovery, adapter
ownership, provider routing, credential references, or package boundaries. Any
remaining failures must be members of the recorded pre-task hosted-transport,
legacy parser/security, or PostgreSQL transaction baseline and must be reported
without claiming the full suite is green.

- [ ] **Step 7: Record remediation evidence and commit/push the final gate**

Update `docs/reviews/2026-08-31-critical-review-remediation.md` with commit IDs
and exact verification results, then run `git diff --check` and commit:

```bash
git add README.md packages/cli/README.md docs .github/workflows/ci.yml scripts packages/cli/tests/test_provider_independence.py packages/dbt/src/open_table_connector/dbt/connector.py packages/local_files/src/open_table_connector/local_files/temporal_csv.py packages/local_files/src/open_table_connector/local_files/temporal_excel.py packages/local_files/src/open_table_connector/local_files/temporal_json.py packages/maybe_sheet/src/open_table_connector/maybe_sheet/temporal.py
git commit -m "docs: verify config driven adapter plugins"
git push origin codex/critical-review-remediation
git push origin HEAD:main
```

## Final Verification Checklist

- [ ] `PluginDescriptor` is the only adapter discovery seam.
- [ ] Provider config uses canonical IDs and credential references only.
- [ ] Config cannot override routes or contain literal secrets.
- [ ] CLI source has no provider-specific adapter, route, host, ID, or env knowledge.
- [ ] All concrete adapters and CLI entry points live in provider packages.
- [ ] Exactly one enabled descriptor owns bare path/stdin fallback; local policy does not imply fallback ownership.
- [ ] `otc list` constructs no adapter and resolves no credential.
- [ ] `--token` is gone; reference-only overrides work.
- [ ] CLI imports and runs with no provider wheels.
- [ ] Each provider can be installed, configured, disabled, and removed independently.
- [ ] Focused tests and all package/build/compatibility gates pass.
- [ ] Full-suite status is reported accurately against the recorded unrelated baseline.
- [ ] Every task commit is present on both the feature branch and `origin/main`.
