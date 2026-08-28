from __future__ import annotations

import csv
import io
import json
import re
from typing import Any, Iterable, Mapping

import pyarrow as pa

from open_connectors.contract import (
    CapabilityIdentity,
    CapabilityManifest,
    ConnectorError,
    ConnectorIdentity,
    NeutralReceipt,
    TableMode,
    TableURI,
)
from open_connectors.contract.fingerprints import (
    arrow_content_fingerprint,
    arrow_schema_fingerprint,
)


_RECEIPT_WIRE_KEYS = {
    "contract_version",
    "connector",
    "capability",
    "operation_id",
    "safe_uri",
    "mode",
    "source_revision",
    "schema_fingerprint",
    "content_fingerprint",
    "coordinate_convention",
    "row_count",
    "batch_count",
    "vendor_receipt_ref",
}
_SECRET_DETAIL_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
}
_MARKDOWN_SEPARATOR = re.compile(r"-{3,}")


def strict_json_loads(text: str) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-standard JSON constant: {value}")

    return json.loads(text, parse_constant=reject_constant)


def parse_json_lines(text: str) -> tuple[Any, ...]:
    if not text:
        return ()
    lines = text.splitlines()
    assert lines, "JSONL output must contain at least one record"
    assert all(line.strip() for line in lines), "JSONL output contains a blank record"
    return tuple(strict_json_loads(line) for line in lines)


def parse_csv_records(text: str) -> tuple[dict[str, str | None], ...]:
    reader = csv.DictReader(io.StringIO(text, newline=""))
    assert reader.fieldnames is not None, "CSV output is missing a header"
    assert len(reader.fieldnames) == len(set(reader.fieldnames)), "CSV headers must be unique"
    rows: list[dict[str, str | None]] = []
    for row in reader:
        assert None not in row, "CSV row has more values than the header"
        assert set(row) == set(reader.fieldnames), "CSV row does not match the header"
        assert all(row[name] is not None for name in reader.fieldnames), (
            "CSV row has fewer values than the header"
        )
        rows.append(
            {
                name: None if row[name] == "" else row[name]
                for name in reader.fieldnames
            }
        )
    return tuple(rows)


def _split_markdown_cells(line: str) -> tuple[str, ...]:
    assert line.startswith("| ") and line.endswith(" |"), (
        f"Markdown table row is not pipe-delimited: {line!r}"
    )
    content = line[2:-2]
    cells: list[str] = []
    cell: list[str] = []
    index = 0
    while index < len(content):
        character = content[index]
        if character == "\\" and index + 1 < len(content):
            cell.extend((character, content[index + 1]))
            index += 2
            continue
        if character == "|":
            cells.append("".join(cell).strip())
            cell = []
        else:
            cell.append(character)
        index += 1
    cells.append("".join(cell).strip())
    return tuple(cells)


def _unescape_markdown_cell(value: str) -> str:
    characters: list[str] = []
    index = 0
    while index < len(value):
        if value[index] != "\\" or index + 1 == len(value):
            characters.append(value[index])
            index += 1
            continue
        escaped = value[index + 1]
        if escaped == "n":
            characters.append("\n")
        elif escaped in {"\\", "|"}:
            characters.append(escaped)
        else:
            characters.extend(("\\", escaped))
        index += 2
    return "".join(characters)


def parse_markdown_table(
    text: str,
) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    lines = text.splitlines()
    assert len(lines) >= 2, "Markdown table requires a header and separator"
    assert len({len(line) for line in lines}) == 1, "Markdown table rows are not aligned"
    raw_header = _split_markdown_cells(lines[0])
    separator = _split_markdown_cells(lines[1])
    assert raw_header and all(raw_header), "Markdown table headers must be non-empty"
    assert len(separator) == len(raw_header), "Markdown separator width mismatch"
    assert all(_MARKDOWN_SEPARATOR.fullmatch(cell) for cell in separator), (
        "Markdown table separator is malformed"
    )
    raw_rows = tuple(_split_markdown_cells(line) for line in lines[2:])
    assert all(len(row) == len(raw_header) for row in raw_rows), (
        "Markdown table body width mismatch"
    )
    return (
        tuple(_unescape_markdown_cell(cell) for cell in raw_header),
        tuple(
            tuple(_unescape_markdown_cell(cell) for cell in row)
            for row in raw_rows
        ),
    )


def _assert_closed_wire(payload: Mapping[str, Any], expected_keys: set[str], label: str) -> None:
    assert set(payload) == expected_keys, f"{label} wire keys mismatch: {set(payload)!r}"


def _iter_mapping_items(value: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            yield str(raw_key), item
            yield from _iter_mapping_items(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_mapping_items(item)


def assert_identity_round_trip(identity: ConnectorIdentity) -> None:
    wire = identity.to_wire()

    _assert_closed_wire(
        wire,
        {"connector_id", "connector_version", "contract_version"},
        "ConnectorIdentity",
    )
    assert ConnectorIdentity.from_wire(wire) == identity


def assert_capabilities_are_unique(
    capabilities: tuple[CapabilityIdentity, ...],
    *,
    expected_connector: ConnectorIdentity,
    expected_capabilities: frozenset[str],
    expected_modes: frozenset[TableMode],
    expected_schemes: frozenset[str],
    manifest: CapabilityManifest | None = None,
) -> None:
    capability_ids = tuple(item.capability_id for item in capabilities)

    assert set(capability_ids) == set(expected_capabilities)
    assert len(capability_ids) == len(set(capability_ids))
    assert all(isinstance(mode, TableMode) for mode in expected_modes)
    if manifest is not None:
        wire = manifest.to_wire()

        _assert_closed_wire(
            wire,
            {"connector", "capabilities", "modes", "uri_schemes"},
            "CapabilityManifest",
        )
        assert CapabilityManifest.from_wire(wire) == manifest
        assert manifest.connector == expected_connector
        assert tuple(manifest.capabilities) == capabilities
        assert set(manifest.modes) == set(expected_modes)
        assert set(manifest.uri_schemes) == {item.casefold() for item in expected_schemes}
        assert tuple(manifest.uri_schemes) == tuple(dict.fromkeys(manifest.uri_schemes))


def assert_safe_uri(uri: TableURI, *, allowed_schemes: frozenset[str]) -> None:
    wire = uri.to_wire()
    encoded = json.dumps(wire, ensure_ascii=False, sort_keys=True).casefold()

    _assert_closed_wire(wire, {"value"}, "TableURI")
    assert TableURI.from_wire(wire) == uri
    assert uri.scheme in {item.casefold() for item in allowed_schemes}
    assert "token=" not in encoded
    assert "password=" not in encoded
    assert "access_token=" not in encoded


def assert_receipt_matches_table(
    receipt: NeutralReceipt,
    table: pa.Table,
    *,
    expected_connector: ConnectorIdentity,
    expected_capability: str,
    expected_mode: TableMode,
    expected_safe_uri: TableURI,
    forbidden_values: tuple[str, ...] = ("fixture-token", "fixture-secret"),
) -> None:
    wire = receipt.to_wire()
    encoded = json.dumps(wire, ensure_ascii=False, sort_keys=True)

    _assert_closed_wire(wire, _RECEIPT_WIRE_KEYS, "NeutralReceipt")
    assert NeutralReceipt.from_wire(wire) == receipt
    assert receipt.connector == expected_connector
    assert receipt.capability.capability_id == expected_capability
    assert receipt.safe_uri == expected_safe_uri
    assert receipt.mode == expected_mode
    assert wire["contract_version"] == expected_connector.contract_version
    assert receipt.schema_fingerprint == arrow_schema_fingerprint(table.schema)
    assert receipt.content_fingerprint == arrow_content_fingerprint(table)
    assert receipt.row_count == table.num_rows
    assert receipt.batch_count is None or receipt.batch_count >= 0
    for forbidden in forbidden_values:
        assert forbidden not in encoded


def assert_error_is_safe(
    error: ConnectorError,
    *,
    forbidden_values: tuple[str, ...] = ("fixture-token", "fixture-secret"),
) -> None:
    wire = error.to_wire()
    encoded = json.dumps(wire, ensure_ascii=False, sort_keys=True)

    _assert_closed_wire(wire, {"code", "message", "safe_details"}, "ConnectorError")
    for key, _ in _iter_mapping_items(wire["safe_details"]):
        assert key.casefold() not in _SECRET_DETAIL_KEYS
    for forbidden in forbidden_values:
        assert forbidden not in encoded
