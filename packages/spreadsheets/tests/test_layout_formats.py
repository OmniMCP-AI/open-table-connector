import pytest

from open_table_connector.spreadsheets import CellFormat


DESCRIPTOR = {
    "formats": {
        "dialect": "excel",
        "version": "OOXML-ECMA-376",
        "locales": ["en-US", "zh-CN", "de-DE"],
        "builtins": {"14": {"code": "m/d/yy", "locales": ["en-US"]}},
        "custom_code": True,
        "unsupported_features": [],
    }
}


@pytest.mark.parametrize(
    "code",
    [
        "0.00 ",
        '#,##0.00;[Red](#,##0.00);"-";@',
        "[h]:mm:ss",
        "[$€-407] #,##0.00",
        "0.00E+00",
        r'0.00\ "units"',
        '_(* #,##0.00_);_(* (#,##0.00);_(* "-"??_);_(@_)',
    ],
)
def test_custom_pattern_is_not_trimmed_or_rewritten(code):
    assert CellFormat("custom", pattern=code).pattern == code


def test_new_cell_format_kinds_and_builtin_id_are_keyword_compatible():
    assert CellFormat("accounting", pattern='_($* #,##0.00_);_($* (#,##0.00);_($* "-"??_);_(@_)').kind == "accounting"
    assert CellFormat(builtin_id=14).builtin_id == 14


@pytest.mark.parametrize("kind", ["accounting", "special", "custom", "native"])
def test_pattern_required_for_non_default_kinds(kind):
    with pytest.raises(ValueError, match="pattern"):
        CellFormat(kind)


def test_normalize_format_preserves_code_and_does_not_change_data():
    from open_table_connector.spreadsheets.formats import normalize_format

    result = normalize_format(
        {"kind": "custom", "pattern": '#,##0.00;[Red](#,##0.00);"-";@', "locale": "en-US", "date_system": "1900"},
        descriptor=DESCRIPTOR,
    )
    assert result == {
        "kind": "custom",
        "code": '#,##0.00;[Red](#,##0.00);"-";@',
        "builtin_id": None,
        "locale": "en-US",
        "date_system": "1900",
        "storage_kind": "custom",
    }


def test_default_formats_are_deterministic_and_locale_is_explicit():
    from open_table_connector.spreadsheets.formats import normalize_format

    assert normalize_format({"kind": "date"}, descriptor=DESCRIPTOR)["code"] == "yyyy-mm-dd"
    assert normalize_format({"kind": "duration"}, descriptor=DESCRIPTOR)["code"] == "[h]:mm:ss"
    with pytest.raises(ValueError, match="locale"):
        normalize_format({"builtin_id": 14}, descriptor=DESCRIPTOR)


def test_builtin_and_pattern_are_mutually_exclusive():
    from open_table_connector.spreadsheets.formats import normalize_format

    with pytest.raises(ValueError, match="mutually exclusive"):
        normalize_format({"builtin_id": 14, "pattern": "m/d/yy"}, descriptor=DESCRIPTOR)


def test_unsupported_format_features_are_explicit():
    from open_table_connector.spreadsheets.formats import normalize_format

    descriptor = {"formats": {**DESCRIPTOR["formats"], "custom_code": False}}
    with pytest.raises(ValueError, match="custom"):
        normalize_format({"kind": "custom", "pattern": "0.00"}, descriptor=descriptor)
