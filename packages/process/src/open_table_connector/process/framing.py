"""Length-prefixed, duplicate-safe JSON framing."""

from __future__ import annotations

import json
import struct
from typing import BinaryIO, Mapping


class FrameError(ValueError):
    """A process-fatal framing or JSON encoding error."""


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise FrameError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_exact(stream: BinaryIO, size: int, description: str) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise FrameError(f"truncated {description}")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_frame(stream: BinaryIO, max_frame_bytes: int) -> Mapping[str, object] | None:
    if isinstance(max_frame_bytes, bool) or not isinstance(max_frame_bytes, int):
        raise TypeError("max_frame_bytes must be an integer")
    if max_frame_bytes <= 0:
        raise ValueError("max_frame_bytes must be positive")
    header = stream.read(4)
    if header == b"":
        return None
    if len(header) != 4:
        raise FrameError("truncated frame header")
    size = struct.unpack(">I", header)[0]
    if size == 0:
        raise FrameError("frame payload cannot be empty")
    if size > max_frame_bytes:
        raise FrameError("frame exceeds maximum size")
    payload = _read_exact(stream, size, "frame payload")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FrameError("frame payload is not valid UTF-8") from exc
    try:
        value = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except FrameError:
        raise
    except json.JSONDecodeError as exc:
        raise FrameError("frame payload is not valid JSON") from exc
    if not isinstance(value, Mapping):
        raise FrameError("frame payload must be one JSON object")
    return value


def write_frame(stream: BinaryIO, envelope: Mapping[str, object] | object) -> None:
    value = envelope.to_wire() if hasattr(envelope, "to_wire") else envelope
    if not isinstance(value, Mapping):
        raise TypeError("envelope must be an object")
    try:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise FrameError("envelope is not JSON serializable") from exc
    if len(payload) > 0xFFFFFFFF:
        raise FrameError("frame exceeds unsigned 32-bit length")
    stream.write(struct.pack(">I", len(payload)))
    stream.write(payload)
    flush = getattr(stream, "flush", None)
    if flush is not None:
        flush()


__all__ = ["FrameError", "read_frame", "write_frame"]
