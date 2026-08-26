"""Native inspection facts for local files."""

from __future__ import annotations

from open_connectors.contract import InspectRequest, TableInspection


def inspection_from_read(
    request: InspectRequest,
    *,
    table,
    sheet: str,
    worksheets: tuple[str, ...],
    mode,
) -> TableInspection:
    from open_connectors.contract.fingerprints import arrow_schema_fingerprint
    from open_connectors.contract import SheetConvention

    facts = {
        "worksheets": list(worksheets),
        "formula_text_captured": False,
        "formula_calculated": False,
    }
    return TableInspection(
        safe_uri=request.uri,
        mode=mode,
        columns=tuple(str(name) for name in table.column_names),
        schema_fingerprint=arrow_schema_fingerprint(table.schema),
        row_count=table.num_rows,
        coordinate_convention=SheetConvention(sheet=sheet, header_rows=1, first_data_row=2),
        facts=facts,
    )
