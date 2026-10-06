from __future__ import annotations

from open_table_connector.cli.__main__ import build_parser


def test_artifact_export_parser():
    parser = build_parser()
    args = parser.parse_args(["artifact", "export", "--from", "rows.csv", "--to", "out.docx"])
    assert args.command == "artifact"
    assert args.action == "export"
