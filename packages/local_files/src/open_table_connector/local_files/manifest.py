"""Capability declaration for the local-files Connector."""

from open_table_connector.contract import (
    PROVIDER_EXCEL,
    PROVIDER_JSON,
    PROVIDER_JSONL,
    SCHEME_FILE,
    CapabilityIdentity,
    CapabilityManifest,
    MaterializationCapability,
    TableMode,
)
from open_table_connector.formulas import GRID_READ, GRID_SET
from open_table_connector.sdk.materialization import (
    MATERIALIZE_CREATE_CAPABILITY,
    PORTABLE_TABLE_PROFILE_V1,
)

from .identity import (
    CONNECTOR_IDENTITY,
    TABLE_INSPECT_CAPABILITY,
    TABLE_READ_ARROW_CAPABILITY,
    TABLE_READ_POLARS_CAPABILITY,
    URI_RESOLVER_CAPABILITY,
    connector_identity,
)


def capability_manifest(
    *,
    connector,
    uri_schemes: tuple[str, ...],
    extra_capabilities: tuple = (),
) -> CapabilityManifest:
    return CapabilityManifest(
        connector=connector,
        capabilities=(
            URI_RESOLVER_CAPABILITY,
            TABLE_INSPECT_CAPABILITY,
            TABLE_READ_ARROW_CAPABILITY,
            TABLE_READ_POLARS_CAPABILITY,
            *extra_capabilities,
        ),
        modes=(TableMode.SHEET,),
        uri_schemes=uri_schemes,
    )


SPREADSHEET_CAPABILITIES = tuple(
    CapabilityIdentity("spreadsheet." + operation, "1.0")
    for operation in (
        "workbook.inspect",
        "workbook.write",
        "workbook.verify",
        "worksheet.list",
        "worksheet.create",
        "worksheet.rename",
        "worksheet.delete",
        "worksheet.move",
        "range.read",
        "range.write",
        "range.clear",
        "range.sort",
        "range.style",
        "range.format",
        "range.merge",
        "range.unmerge",
        "formula.set",
    )
)

CAPABILITY_MANIFEST = capability_manifest(
    connector=CONNECTOR_IDENTITY,
    uri_schemes=(SCHEME_FILE, PROVIDER_JSON, PROVIDER_JSONL),
    extra_capabilities=SPREADSHEET_CAPABILITIES,
)
CAPABILITY_MANIFEST = CapabilityManifest(
    connector=CAPABILITY_MANIFEST.connector,
    capabilities=(*CAPABILITY_MANIFEST.capabilities, MATERIALIZE_CREATE_CAPABILITY),
    modes=(TableMode.SHEET, TableMode.BASE),
    uri_schemes=CAPABILITY_MANIFEST.uri_schemes,
    materialization=(MaterializationCapability(MATERIALIZE_CREATE_CAPABILITY, (PORTABLE_TABLE_PROFILE_V1,), (TableMode.BASE, TableMode.SHEET)),),
)

EXCEL_CAPABILITY_MANIFEST = capability_manifest(
    connector=connector_identity(PROVIDER_EXCEL),
    uri_schemes=(PROVIDER_EXCEL,),
    extra_capabilities=(GRID_READ, GRID_SET),
)
