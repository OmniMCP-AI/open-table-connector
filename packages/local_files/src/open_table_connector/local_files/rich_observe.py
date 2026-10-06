"""Independent, bounded observation of serialized XLSX image relationships."""

from __future__ import annotations

import hashlib
from io import BytesIO
from zipfile import ZipFile

from open_table_connector.spreadsheets import ObjectObservation


def observe_rich_xlsx(data: bytes, selectors=(), limits=None):
    observations = []
    with ZipFile(BytesIO(data)) as archive:
        for name in archive.namelist():
            if name.startswith("xl/media/"):
                content = archive.read(name)
                observations.append(ObjectObservation(name, "image", {"path": name, "byte_count": len(content)}, ("content_hash",), "sha256:" + hashlib.sha256(content).hexdigest()))
    return tuple(observations)


__all__ = ["observe_rich_xlsx"]
