from __future__ import annotations

import json

from open_table_connector.cli.__main__ import build_parser


def test_recipe_parser_has_explicit_actions(tmp_path):
    parser = build_parser()
    args = parser.parse_args(["spreadsheet", "apply", "--uri", "file:///tmp/book.xlsx", "--spec", str(tmp_path / "recipe.json")])
    assert args.action == "apply"
    assert args.spec.endswith("recipe.json")


def test_recipe_export_parser_accepts_export_after_recipe(tmp_path):
    parser = build_parser()
    args = parser.parse_args(
        [
            "spreadsheet",
            "recipe",
            "export",
            "--uri",
            "file:///tmp/book.xlsx",
            "--selectors",
            str(tmp_path / "selectors.json"),
        ]
    )
    assert args.action == "recipe"
    assert args.selectors.endswith("selectors.json")
