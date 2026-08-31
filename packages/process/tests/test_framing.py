from __future__ import annotations

import json
import struct
from io import BytesIO

import pytest
from open_table_connector.process import FrameError, read_frame, write_frame


class OneByteStream(BytesIO):
    def read(self, size: int = -1) -> bytes:
        return super().read(1 if size < 0 else min(size, 1))


def test_frame_is_big_endian_length_followed_by_one_json_object() -> None:
    stream = BytesIO()
    write_frame(stream, {"hello": "世界"})
    raw = stream.getvalue()
    size = struct.unpack(">I", raw[:4])[0]

    assert size == len(raw[4:])
    assert json.loads(raw[4:].decode("utf-8")) == {"hello": "世界"}
    assert read_frame(BytesIO(raw), 1024) == {"hello": "世界"}
    assert read_frame(BytesIO(), 1024) is None


def test_frame_header_may_arrive_one_byte_at_a_time() -> None:
    stream = BytesIO()
    write_frame(stream, {"ok": True})
    assert read_frame(OneByteStream(stream.getvalue()), 1024) == {"ok": True}


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (b"\x00\x00", "truncated frame header"),
        (struct.pack(">I", 5) + b"{}", "truncated frame payload"),
        (struct.pack(">I", 2) + b"\xff\xff", "UTF-8"),
        (struct.pack(">I", 13) + b'{"a":1,"a":2}', "duplicate JSON key"),
    ],
)
def test_frame_rejects_truncation_encoding_and_duplicate_keys(raw, message) -> None:
    with pytest.raises(FrameError, match=message):
        read_frame(BytesIO(raw), 1024)


class ReadTracker(BytesIO):
    payload_read = False

    def read(self, size=-1):
        if self.tell() >= 4:
            self.payload_read = True
        return super().read(size)


def test_oversized_frame_is_rejected_before_payload_read() -> None:
    stream = ReadTracker(struct.pack(">I", 4097) + b"x" * 4097)
    with pytest.raises(FrameError, match="maximum"):
        read_frame(stream, 4096)
    assert stream.payload_read is False
