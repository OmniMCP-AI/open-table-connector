"""Internal resource limits for bounded spreadsheet operations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ArtifactLimits:
    sheets: int = 128
    cells: int = 250_000
    text_bytes: int = 64 * 1024 * 1024
    member_bytes: int = 128 * 1024 * 1024
    image_pixels: int = 40_000_000
    images: int = 128
    image_bytes: int = 16 * 1024 * 1024
    total_image_bytes: int = 128 * 1024 * 1024
    archive_bytes: int = 256 * 1024 * 1024
    zip_members: int = 10_000
    decompressed_bytes: int = 512 * 1024 * 1024

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")


__all__ = ["ArtifactLimits"]
