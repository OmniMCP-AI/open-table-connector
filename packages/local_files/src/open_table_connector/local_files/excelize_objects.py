"""Closed adapter around the existing workbook object operation compiler."""

from .spreadsheet_workbook import _apply


def apply_excelize_object(book, change, binding=None):
    return _apply(book, change, binding or {"profile": "rich-artifact/1.0"}) or {}


__all__ = ["apply_excelize_object"]
