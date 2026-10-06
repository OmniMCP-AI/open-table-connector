from __future__ import annotations

from open_table_connector.cli.__main__ import build_parser


def test_invalid_format_selector_rejected():
    parser = build_parser()
    args = parser.parse_args(["artifact", "view", "--uri", "file:///tmp/report.xlsx", "--mode", "html"])
    assert args.mode == "html"
