"""Scalar values allowed in stable Base coordinates."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TypeAlias

Scalar: TypeAlias = str | int | float | bool | Decimal | date | datetime


def scalar_to_wire(value: Scalar) -> str | int | float | bool:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported coordinate scalar {type(value).__name__}")
