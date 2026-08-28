"""Native inspection facts for local files."""

from __future__ import annotations

from open_table_connector.contract import InspectRequest, SheetConvention, TableInspection


def inspection_from_read(
    request: InspectRequest,
    *,
    table,
    sheet: str,
    header_row: int = 1,
    worksheets: tuple[str, ...],
    mode,
    formula_text_captured: bool = False,
    formula_calculated: bool = False,
) -> TableInspection:
    from open_table_connector.contract.fingerprints import arrow_schema_fingerprint

    facts = {"worksheets": list(worksheets)}
    if formula_text_captured or formula_calculated or len(worksheets) > 1:
        facts["formula_text_captured"] = formula_text_captured
        facts["formula_calculated"] = formula_calculated
    return TableInspection(
        safe_uri=request.uri,
        mode=mode,
        columns=tuple(str(name) for name in table.column_names),
        schema_fingerprint=arrow_schema_fingerprint(table.schema),
        row_count=table.num_rows,
        coordinate_convention=SheetConvention(
            sheet=sheet,
            header_rows=header_row,
            first_data_row=header_row + 1,
        ),
        facts=facts,
    )
