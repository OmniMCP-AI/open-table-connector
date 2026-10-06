"""Bounded JSON parsing shared by CLI, recipes and protocol adapters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, BinaryIO


class JsonInputError(ValueError):
    """Safe command-input error without raw payload details."""


def read_json_input(source: str, *, stdin: BinaryIO | None = None, max_bytes: int = 16 * 1024 * 1024) -> Any:
    if not isinstance(source, str) or not source:
        raise JsonInputError("JSON input source must be a non-empty string")
    if max_bytes < 1:
        raise JsonInputError("JSON input limit must be positive")
    try:
        stream = stdin if source == "-" else Path(source).open("rb")
    except OSError as exc:
        raise JsonInputError("could not open JSON input") from exc
    if source == "-" and stream is None:
        raise JsonInputError("stdin must be supplied explicitly for JSON input")
    try:
        data = stream.read(max_bytes + 1)
    except OSError as exc:
        raise JsonInputError("could not read JSON input") from exc
    finally:
        if source != "-":
            stream.close()
    if len(data) > max_bytes:
        raise JsonInputError("JSON input exceeds the configured byte limit")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise JsonInputError("JSON input must be UTF-8") from exc

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise JsonInputError("duplicate JSON property")
            result[key] = value
        return result

    def constant(_value):
        raise JsonInputError("non-finite JSON number")

    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except JsonInputError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise JsonInputError("invalid JSON input") from exc


__all__ = ["JsonInputError", "read_json_input"]
