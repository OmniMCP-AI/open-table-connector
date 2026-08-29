"""Content-addressed Arrow IPC artifact storage."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
import tempfile
import time
from typing import Callable

import pyarrow as pa

from open_table_connector.timeseries import (
    ArrowArtifactReference,
    ResourceBounds,
    TemporalErrorCode,
    TemporalExtensionError,
)


class ArtifactStore:
    def __init__(
        self,
        root: str | os.PathLike[str],
        *,
        ttl_seconds: int = 3600,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be a positive integer")
        self.root = Path(root).absolute()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.root.is_symlink():
            raise PermissionError("artifact root cannot be a symlink")
        self.root.chmod(0o700)
        self._verify_owner_and_mode(self.root.stat(), "artifact root", 0o077)
        self._directory = self.root / "sha256"
        self._directory.mkdir(mode=0o700, exist_ok=True)
        self._directory.chmod(0o700)
        self.ttl_seconds = ttl_seconds
        self._clock = clock

    def put_arrow(self, table: pa.Table) -> ArrowArtifactReference:
        if not isinstance(table, pa.Table):
            raise TypeError("table must be a pyarrow.Table")
        sink = pa.BufferOutputStream()
        with pa.ipc.new_stream(sink, table.schema) as writer:
            writer.write_table(table)
        data = sink.getvalue().to_pybytes()
        digest = hashlib.sha256(data).hexdigest()
        relative = f"sha256/{digest}.arrow"
        destination = self.root / relative
        descriptor, temporary = tempfile.mkstemp(prefix=f".{digest}.", dir=self._directory)
        temporary_path = Path(temporary)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb", closefd=True) as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, destination)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
        return ArrowArtifactReference(
            relative_path=relative,
            sha256=f"sha256:{digest}",
            size_bytes=len(data),
        )

    def get_arrow(
        self,
        reference: ArrowArtifactReference,
        bounds: ResourceBounds,
    ) -> pa.Table:
        if not isinstance(reference, ArrowArtifactReference):
            raise TypeError("reference must be an ArrowArtifactReference")
        if not isinstance(bounds, ResourceBounds):
            raise TypeError("bounds must be ResourceBounds")
        path = self._path(reference)
        try:
            before = path.lstat()
        except FileNotFoundError as exc:
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                "artifact is unavailable",
                {"sha256": reference.sha256},
            ) from exc
        if stat.S_ISLNK(before.st_mode):
            raise PermissionError("artifact path cannot be a symlink")
        self._verify_owner_and_mode(before, "artifact", 0o077)
        if before.st_size != reference.size_bytes:
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                "artifact size does not match its reference",
                {"sha256": reference.sha256},
            )
        if before.st_size > bounds.max_bytes:
            raise TemporalExtensionError(
                TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
                "artifact exceeds max_bytes",
                {"bytes": before.st_size, "max_bytes": bounds.max_bytes},
            )
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags)
        except OSError as exc:
            raise PermissionError("artifact path cannot be a symlink") from exc
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            current = os.fstat(stream.fileno())
            if (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino):
                raise PermissionError("artifact changed during secure open")
            data = stream.read(bounds.max_bytes + 1)
        if len(data) > bounds.max_bytes:
            raise TemporalExtensionError(
                TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
                "artifact exceeds max_bytes",
                {"max_bytes": bounds.max_bytes},
            )
        actual = "sha256:" + hashlib.sha256(data).hexdigest()
        if actual != reference.sha256:
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                "artifact hash verification failed",
                {"sha256": reference.sha256},
            )
        try:
            table = pa.ipc.open_stream(pa.BufferReader(data)).read_all()
        except (pa.ArrowInvalid, OSError) as exc:
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                "artifact is not a valid Arrow IPC stream",
                {"sha256": reference.sha256},
            ) from exc
        if table.num_rows > bounds.max_rows:
            raise TemporalExtensionError(
                TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
                "artifact exceeds max_rows",
                {"rows": table.num_rows, "max_rows": bounds.max_rows},
            )
        return table

    def cleanup_expired(self) -> int:
        cutoff = self._clock() - self.ttl_seconds
        removed = 0
        for path in self._directory.iterdir():
            try:
                metadata = path.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISREG(metadata.st_mode) and metadata.st_mtime < cutoff:
                path.unlink()
                removed += 1
        return removed

    def _path(self, reference: ArrowArtifactReference) -> Path:
        expected = f"sha256/{reference.sha256[7:]}.arrow"
        if reference.relative_path != expected:
            raise PermissionError("artifact path is not canonical for its hash")
        return self.root / expected

    @staticmethod
    def _verify_owner_and_mode(metadata: os.stat_result, name: str, forbidden: int) -> None:
        if hasattr(os, "getuid") and metadata.st_uid != os.getuid():
            raise PermissionError(f"{name} ownership is not trusted")
        if stat.S_IMODE(metadata.st_mode) & forbidden:
            raise PermissionError(f"{name} permissions are too broad")


__all__ = ["ArtifactStore"]
