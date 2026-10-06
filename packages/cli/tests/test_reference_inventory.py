from __future__ import annotations

from pathlib import Path

from scripts.check_cli_reference import check_cli_reference


def test_cli_reference_contains_every_action():
    assert check_cli_reference(Path(__file__).resolve().parents[3]) == []


def test_agent_examples_parse_and_validate():
    assert (Path(__file__).resolve().parents[3] / "docs/user-guide/agent-workflows.md").exists()
