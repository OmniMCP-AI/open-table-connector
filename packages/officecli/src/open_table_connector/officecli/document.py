"""Native DOCX/PPTX table writer used by the optional adapter."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from open_table_connector.artifacts import ViewRequest, display_cell


def _docx(rows):
    table = "<w:tbl>" + "".join("<w:tr>" + "".join(f"<w:tc><w:p><w:r><w:t xml:space=\"preserve\">{escape(display_cell(cell))}</w:t></w:r></w:p></w:tc>" for cell in row) + "</w:tr>" for row in rows) + "</w:tbl>"
    document = f"<?xml version=\"1.0\" encoding=\"UTF-8\"?><w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"><w:body>{table}<w:sectPr/></w:body></w:document>"
    return {"[Content_Types].xml": "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/><Default Extension=\"xml\" ContentType=\"application/xml\"/><Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/></Types>", "word/document.xml": document}


def _pptx(rows):
    cells = "".join(f"<a:tc><a:txBody><a:p><a:r><a:t>{escape(display_cell(cell))}</a:t></a:r></a:p></a:txBody><a:tcPr/></a:tc>" for row in rows for cell in row)
    slide = f"<?xml version=\"1.0\" encoding=\"UTF-8\"?><p:sld xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\" xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\"><p:cSld><p:spTree><a:tbl><a:tblGrid/>{cells}</a:tbl></p:spTree></p:cSld></p:sld>"
    return {"[Content_Types].xml": "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/><Default Extension=\"xml\" ContentType=\"application/xml\"/></Types>", "ppt/slides/slide1.xml": slide}


class OfficeCliAdapter:
    def describe(self):
        return {"name": "officecli", "version": "1.0.154", "formats": ["docx", "pptx"], "modes": ["html", "screenshot", "text", "outline", "stats", "issues"]}

    def create_table(self, document_path: Path, rows, spec):
        suffix = document_path.suffix.casefold()
        if suffix not in {".docx", ".pptx"}:
            raise ValueError("OfficeCLI adapter accepts only DOCX or PPTX")
        members = _docx(rows) if suffix == ".docx" else _pptx(rows)
        with zipfile.ZipFile(document_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in members.items():
                archive.writestr(name, content)
        data = document_path.read_bytes()
        return {"uri": document_path.as_uri(), "media_type": "application/" + suffix[1:], "content_hash": "sha256:" + hashlib.sha256(data).hexdigest(), "engine": "officecli", "coverage": ["native_table"]}

    def observe_document(self, document_path: Path, selectors=()):
        with zipfile.ZipFile(document_path) as archive:
            names = [name for name in archive.namelist() if name.endswith("document.xml") or name.endswith("slide1.xml")]
            return {"parts": names, "size": document_path.stat().st_size}

    def render(self, snapshot_path: Path, request: ViewRequest):
        raise RuntimeError("OfficeCLI renderer is unavailable until a qualified binary is configured")


__all__ = ["OfficeCliAdapter"]
