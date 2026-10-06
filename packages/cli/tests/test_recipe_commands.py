from __future__ import annotations

import json

from open_table_connector.cli.__main__ import build_parser


def test_recipe_parser_has_explicit_actions(tmp_path):
    parser = build_parser()
    args = parser.parse_args(["spreadsheet", "apply", "--uri", "file:///tmp/book.xlsx", "--spec", str(tmp_path / "recipe.json")])
    assert args.action == "apply"
    assert args.spec.endswith("recipe.json")
