"""Open Table Connector CLI package exports."""

from .configuration import CliConfig, CredentialBinding, load_cli_config, resolve_config_path
from .credentials import (
    CredentialLease,
    CredentialResolver,
    EnvironmentCredentialResolver,
    apply_credential_overrides,
    parse_credential_overrides,
)
from .formats import infer_format, read_local, write_local
from .model import CliOptions, Endpoint, FormatName, PipelineSummary, parse_endpoint, parse_format


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
