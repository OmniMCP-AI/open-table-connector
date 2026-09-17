import pytest

from open_table_connector.cli import __main__ as cli_main
from open_table_connector.cli import version


def test_machine_and_human_labels_share_one_commit_metadata(monkeypatch) -> None:
    monkeypatch.setattr(version, "_package_version", lambda: "0.1.0")
    monkeypatch.setattr(version, "_git_metadata", lambda: ("2026-09-18", "df9467c"))

    assert version.get_machine_version() == "0.1.0+git.20260918.gdf9467c"
    assert version.get_version_label() == "OTC 0.1.0 · 2026-09-18 · df9467c"


def test_labels_fall_back_when_git_metadata_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(version, "_package_version", lambda: "0.1.0")
    monkeypatch.setattr(version, "_git_metadata", lambda: None)

    assert version.get_machine_version() == "0.1.0"
    assert version.get_version_label() == "OTC 0.1.0 · commit metadata unavailable"


def test_top_level_parser_prints_version_without_a_subcommand(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli_main, "get_version_label", lambda: "OTC 0.1.0 · 2026-09-18 · df9467c")

    with pytest.raises(SystemExit) as error:
        cli_main.build_parser().parse_args(["--version"])

    assert error.value.code == 0
    assert capsys.readouterr().out == "OTC 0.1.0 · 2026-09-18 · df9467c\n"
