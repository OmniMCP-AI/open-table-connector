import hashlib

import pytest
from open_table_connector.spreadsheets import (
    CellFormat,
    CellStyle,
    ImageSpec,
    RangeRef,
    SpreadsheetTarget,
    WorksheetRef,
)


def test_file_target_and_range_are_normalized():
    assert SpreadsheetTarget("file:///tmp/model.xlsx").to_wire() == {"uri": "file:///tmp/model.xlsx"}
    assert RangeRef("a1:b2").address == "A1:B2"


@pytest.mark.parametrize("value", ["file://relative.xlsx", "A:A", "B2:A1", "A0:B1", "A1:"])
def test_invalid_target_or_range_is_rejected(value):
    with pytest.raises(ValueError):
        (SpreadsheetTarget(value) if "://" in value else RangeRef(value))


def test_worksheet_requires_identity_and_style_validates():
    with pytest.raises(ValueError):
        WorksheetRef()
    with pytest.raises(ValueError):
        CellStyle(foreground="red")
    assert CellFormat("NUMBER").kind == "number"


def test_image_reports_content_hash_without_serializing_bytes():
    content = b"image"
    image = ImageSpec("image/png", content, "b2")
    assert image.sha256 == hashlib.sha256(content).hexdigest()
    assert image.to_wire()["byte_count"] == len(content)


def test_capability_is_versioned():
    from open_table_connector.spreadsheets import SPREADSHEET_RANGE_READ

    assert SPREADSHEET_RANGE_READ.to_reference() == "spreadsheet.range.read/1.0"
