"""Bounded, precision-aware Arrow artifact verification."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa

from .descriptor import TemporalTableDescriptor
from .plan import ResourceBounds
from .precision import arrow_time_bounds
from .receipts import TimeRange
from .storage import ArrowArtifactReference, TemporalErrorCode, TemporalExtensionError


@dataclass(frozen=True)
class VerifiedArtifact:
    data: bytes
    table: pa.Table
    observed_range: TimeRange | None = None


def read_verified_artifact(
    reference: ArrowArtifactReference,
    artifact_root: Path,
    bounds: ResourceBounds,
    descriptor: TemporalTableDescriptor | None = None,
) -> VerifiedArtifact:
    if not isinstance(reference, ArrowArtifactReference):
        raise TypeError("reference must be an ArrowArtifactReference")
    root = Path(artifact_root).resolve()
    relative = Path(reference.relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise TemporalExtensionError(
            TemporalErrorCode.SNAPSHOT_UNAVAILABLE, "artifact path is invalid"
        )
    path = (root / relative).resolve()
    if root not in path.parents or path.is_symlink():
        raise TemporalExtensionError(
            TemporalErrorCode.SNAPSHOT_UNAVAILABLE, "artifact path is unsafe"
        )
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode):
            raise OSError("artifact is not a regular file")
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as exc:
        raise TemporalExtensionError(
            TemporalErrorCode.SNAPSHOT_UNAVAILABLE, "artifact is unavailable"
        ) from exc
    try:
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE, "artifact changed during open"
            )
        with os.fdopen(fd, "rb") as stream:
            data = stream.read(bounds.max_bytes + 1)
    except Exception:
        os.close(fd)
        raise
    if len(data) > bounds.max_bytes:
        raise TemporalExtensionError(
            TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED, "artifact exceeds max_bytes"
        )
    if "sha256:" + hashlib.sha256(data).hexdigest() != reference.sha256:
        raise TemporalExtensionError(
            TemporalErrorCode.SNAPSHOT_UNAVAILABLE, "artifact hash verification failed"
        )
    try:
        table = pa.ipc.open_stream(pa.BufferReader(data)).read_all()
    except (pa.ArrowInvalid, OSError) as exc:
        raise TemporalExtensionError(
            TemporalErrorCode.SNAPSHOT_UNAVAILABLE, "artifact is not valid Arrow IPC"
        ) from exc
    if table.num_rows > bounds.max_rows:
        raise TemporalExtensionError(
            TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED, "artifact exceeds max_rows"
        )
    observed = None
    if descriptor is not None:
        values = arrow_time_bounds(table, descriptor.time_field, descriptor.timestamp_precision)
        if values is not None:
            observed = TimeRange(values[0], values[1])
    return VerifiedArtifact(data, table, observed)
