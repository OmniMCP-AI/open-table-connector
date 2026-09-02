from open_table_connector.contract import (
    PROVIDER_MAYBE_SHEET,
    CapabilityIdentity,
    ConnectorIdentity,
)
from open_table_connector.formulas import (
    FIELD_READ as FORMULA_FIELD_READ_CAPABILITY,
)
from open_table_connector.formulas import (
    FIELD_RECALCULATE as FORMULA_FIELD_RECALCULATE_CAPABILITY,
)
from open_table_connector.formulas import (
    FIELD_SET as FORMULA_FIELD_SET_CAPABILITY,
)
from open_table_connector.formulas import (
    FIELD_VALUES_READ as FORMULA_FIELD_VALUES_READ_CAPABILITY,
)
from open_table_connector.formulas import (
    GRID_READ as FORMULA_GRID_READ_CAPABILITY,
)
from open_table_connector.formulas import (
    GRID_RECALCULATE as FORMULA_GRID_RECALCULATE_CAPABILITY,
)
from open_table_connector.formulas import (
    GRID_SET as FORMULA_GRID_SET_CAPABILITY,
)
from open_table_connector.formulas import (
    GRID_VALUES_READ as FORMULA_GRID_VALUES_READ_CAPABILITY,
)

CONNECTOR_IDENTITY = ConnectorIdentity(PROVIDER_MAYBE_SHEET, "0.1.0", "1.0")
BASE_READ_CAPABILITY = CapabilityIdentity("base.read", "1.0")
SHEET_READ_CAPABILITY = CapabilityIdentity("sheet.read", "1.0")
BASE_INSPECT_CAPABILITY = CapabilityIdentity("base.inspect", "1.0")
SHEET_INSPECT_CAPABILITY = CapabilityIdentity("sheet.inspect", "1.0")
TABLE_WRITE_CAPABILITY = CapabilityIdentity("table.write", "1.0")

__all__ = [
    "BASE_INSPECT_CAPABILITY",
    "BASE_READ_CAPABILITY",
    "CONNECTOR_IDENTITY",
    "FORMULA_FIELD_READ_CAPABILITY",
    "FORMULA_FIELD_RECALCULATE_CAPABILITY",
    "FORMULA_FIELD_SET_CAPABILITY",
    "FORMULA_FIELD_VALUES_READ_CAPABILITY",
    "FORMULA_GRID_READ_CAPABILITY",
    "FORMULA_GRID_RECALCULATE_CAPABILITY",
    "FORMULA_GRID_SET_CAPABILITY",
    "FORMULA_GRID_VALUES_READ_CAPABILITY",
    "SHEET_INSPECT_CAPABILITY",
    "SHEET_READ_CAPABILITY",
    "TABLE_WRITE_CAPABILITY",
]
