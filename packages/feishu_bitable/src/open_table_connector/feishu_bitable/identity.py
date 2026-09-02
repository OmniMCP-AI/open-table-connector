"""Canonical Feishu Bitable identity fields."""

from open_table_connector.formulas import (
    FIELD_READ as FORMULA_FIELD_READ_CAPABILITY,
)
from open_table_connector.formulas import (
    FIELD_SET as FORMULA_FIELD_SET_CAPABILITY,
)
from open_table_connector.formulas import (
    FIELD_VALUES_READ as FORMULA_FIELD_VALUES_READ_CAPABILITY,
)

FEISHU_RECORD_ID_FIELD = "_record_id"

__all__ = [
    "FEISHU_RECORD_ID_FIELD",
    "FORMULA_FIELD_READ_CAPABILITY",
    "FORMULA_FIELD_SET_CAPABILITY",
    "FORMULA_FIELD_VALUES_READ_CAPABILITY",
]
