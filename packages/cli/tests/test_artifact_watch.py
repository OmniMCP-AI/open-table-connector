from __future__ import annotations

from open_table_connector.cli.__main__ import build_parser


def test_watch_parser_explicit_lifecycle():
    parser = build_parser()
    args = parser.parse_args(["artifact", "watch", "start", "--uri", "file:///tmp/book.xlsx"])
    assert args.action == "watch"
    assert args.watch_action == "start"
