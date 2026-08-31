from __future__ import annotations

import os
from pathlib import Path

import pytest
from open_table_connector.cli.configuration import (
    CLI_CONFIG_MAX_BYTES,
    CliConfig,
    load_cli_config,
    resolve_config_path,
)
from open_table_connector.contract import (
    CLI_CONFIG_ENV,
    CLI_CONFIG_FILENAME,
    CLI_CONFIG_SCHEMA_VERSION,
    CREDENTIAL_ACCESS_TOKEN,
    PROVIDER_GOOGLE_SHEETS,
    XDG_CONFIG_HOME_ENV,
    ConnectorError,
    ConnectorErrorCode,
)


def test_explicit_config_path_wins_over_environment(tmp_path: Path) -> None:
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


def test_load_cli_config_parses_references_without_secret_values(tmp_path: Path) -> None:
    path = tmp_path / CLI_CONFIG_FILENAME
    path.write_text(
        f'''schema_version = "{CLI_CONFIG_SCHEMA_VERSION}"
[[providers]]
id = "{PROVIDER_GOOGLE_SHEETS}"
key = "work-google"
[credentials."work-google"]
{CREDENTIAL_ACCESS_TOKEN} = {{ env = "GOOGLE_SHEETS_ACCESS_TOKEN" }}
''',
        encoding="utf-8",
    )
    config = load_cli_config(path, environ={})
    assert config.providers[PROVIDER_GOOGLE_SHEETS].credential_reference == "work-google"
    assert config.credentials["work-google"][CREDENTIAL_ACCESS_TOKEN].env == (
        "GOOGLE_SHEETS_ACCESS_TOKEN"
    )


@pytest.mark.parametrize("field", ["token", "password", "api_key", "secret"])
def test_provider_options_reject_secret_like_fields(tmp_path: Path, field: str) -> None:
    path = tmp_path / CLI_CONFIG_FILENAME
    path.write_text(
        f'''schema_version = "{CLI_CONFIG_SCHEMA_VERSION}"
[[providers]]
id = "fixture"
options = {{ {field} = "literal-secret" }}
''',
        encoding="utf-8",
    )
    with pytest.raises(ConnectorError, match="secret-like option"):
        load_cli_config(path, environ={})


def test_invalid_schema_is_a_credential_safe_configuration_error(tmp_path: Path) -> None:
    path = tmp_path / CLI_CONFIG_FILENAME
    path.write_text('schema_version = "wrong"\n', encoding="utf-8")

    with pytest.raises(ConnectorError) as raised:
        load_cli_config(path, environ={})

    assert raised.value.code is ConnectorErrorCode.CONFIGURATION
    assert "wrong" not in repr(raised.value)


def test_literal_credentials_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / CLI_CONFIG_FILENAME
    path.write_text(
        f'''schema_version = "{CLI_CONFIG_SCHEMA_VERSION}"
[credentials.work]
{CREDENTIAL_ACCESS_TOKEN} = "secret-value"
''',
        encoding="utf-8",
    )

    with pytest.raises(ConnectorError, match="environment"):
        load_cli_config(path, environ={})


def test_missing_default_candidates_mean_empty_config(tmp_path: Path) -> None:
    config = load_cli_config(
        None,
        environ={XDG_CONFIG_HOME_ENV: str(tmp_path / "xdg")},
        home=tmp_path / "home",
    )

    assert config == CliConfig.empty()


def test_explicit_missing_path_is_a_configuration_error(tmp_path: Path) -> None:
    with pytest.raises(ConnectorError, match="does not exist"):
        load_cli_config(tmp_path / "missing.toml", environ={})


def test_symlink_config_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target.toml"
    target.write_text(f'schema_version = "{CLI_CONFIG_SCHEMA_VERSION}"\n', encoding="utf-8")
    link = tmp_path / CLI_CONFIG_FILENAME
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")

    with pytest.raises(ConnectorError, match="regular"):
        load_cli_config(link, environ={})


def test_config_file_size_is_bounded(tmp_path: Path) -> None:
    path = tmp_path / CLI_CONFIG_FILENAME
    path.write_bytes(b"x" * (CLI_CONFIG_MAX_BYTES + 1))

    with pytest.raises(ConnectorError, match="size"):
        load_cli_config(path, environ={})


def test_environment_argument_does_not_mutate_process_environment(tmp_path: Path) -> None:
    path = tmp_path / CLI_CONFIG_FILENAME
    path.write_text(f'schema_version = "{CLI_CONFIG_SCHEMA_VERSION}"\n', encoding="utf-8")
    before = os.environ.get(CLI_CONFIG_ENV)

    load_cli_config(path, environ={CLI_CONFIG_ENV: str(path)})

    assert os.environ.get(CLI_CONFIG_ENV) == before
