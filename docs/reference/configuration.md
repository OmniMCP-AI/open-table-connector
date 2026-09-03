# Configuration reference

OTC CLI configuration is TOML with schema version `otc.cli-config/v1`.

## Top-level document

```toml
schema_version = "otc.cli-config/v1"

[[providers]]
id = "google_sheets"
enabled = true
key = "work-google"
env = { endpoint = "GOOGLE_SHEETS_ENDPOINT" }
options = { timeout_seconds = 30 }

[credentials.work-google]
access_token = { env = "GOOGLE_SHEETS_ACCESS_TOKEN" }
```

Allowed top-level fields are `schema_version`, `providers`, and `credentials`.

## Provider fields

Each provider entry accepts:

- `id` — installed provider identity;
- `enabled` — optional boolean, defaulting to `true`;
- `key` — optional credential reference;
- `env` — logical provider environment fields mapped to variable names; and
- `options` — provider options, excluding secret-like names.

## Credential fields

Each credential reference maps logical field names to exactly one environment
variable:

```toml
[credentials.work-google]
access_token = { env = "GOOGLE_SHEETS_ACCESS_TOKEN" }
```

Literal values are not accepted. The parser rejects unknown fields, duplicate
provider IDs, invalid environment names, secret-like options, empty files,
files over 1 MiB, and non-regular or symlinked configuration files.

## SDK equivalent

The SDK exposes `ClientConfig`, `CredentialBinding`, `load_client_config`, and
`resolve_config_path` for callers that need to load configuration themselves.
