"""Open Table Connector CLI package exports."""

from .configuration import CliConfig, CredentialBinding, load_cli_config, resolve_config_path
from .credentials import (
    CredentialLease,
    CredentialResolver,
    EnvironmentCredentialResolver,
    apply_credential_overrides,
    parse_credential_overrides,
)
from .model import CliOptions, Endpoint, FormatName, PipelineSummary, parse_endpoint, parse_format


def infer_format(*args, **kwargs):
    from open_table_connector.local_files.cli_adapter import infer_format as infer

    return infer(*args, **kwargs)


def read_local(*args, **kwargs):
    from open_table_connector.local_files.cli_adapter import read_local as read

    return read(*args, **kwargs)


def write_local(*args, **kwargs):
    from open_table_connector.local_files.cli_adapter import write_local as write

    return write(*args, **kwargs)


def build_parser():
    from .__main__ import build_parser as _build_parser

    return _build_parser()


def main(argv=None):
    from .__main__ import main as _main

    return _main(argv)

__all__ = [
    "CliOptions",
    "Endpoint",
    "FormatName",
    "infer_format",
    "PipelineSummary",
    "read_local",
    "parse_endpoint",
    "parse_format",
    "write_local",
    "build_parser",
    "main",
    "CliConfig",
    "CredentialBinding",
    "CredentialLease",
    "CredentialResolver",
    "EnvironmentCredentialResolver",
    "apply_credential_overrides",
    "load_cli_config",
    "parse_credential_overrides",
    "resolve_config_path",
]
