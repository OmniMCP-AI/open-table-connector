from __future__ import annotations

import json

import pytest

from open_connectors.contract.errors import ConnectorError, ConnectorErrorCode


def test_error_codes_are_closed_and_stable() -> None:
    assert tuple(code.value for code in ConnectorErrorCode) == (
        "invalid_uri",
        "unsupported_capability",
        "authentication",
        "conflict",
        "timeout",
        "cancelled",
        "execution_failed",
        "readback_mismatch",
    )


def test_error_wire_contains_only_safe_details() -> None:
    error = ConnectorError.authentication(
        "authentication failed",
        safe_details={"host": "db.example", "token": "must-not-appear"},
    )

    assert "must-not-appear" not in json.dumps(error.to_wire())
    assert error.to_wire()["code"] == "authentication"


def test_error_rejects_exception_objects_in_safe_details() -> None:
    with pytest.raises(ValueError, match="safe details"):
        ConnectorError(
            code=ConnectorErrorCode.EXECUTION_FAILED,
            message="failed",
            safe_details={"cause": RuntimeError("secret")},
        )
