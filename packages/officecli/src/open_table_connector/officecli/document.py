"""Native DOCX/PPTX table writer used by the optional adapter."""

from __future__ import annotations

import hashlib
import os
import socket
import subprocess
import tempfile
import time
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen
from xml.sax.saxutils import escape

from open_table_connector.artifacts import ViewRequest, display_cell

from .capabilities import check_officecli
from .process import run_officecli, runtime_environment, stop_process


class _Assets(HTMLParser):
    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in {"src", "href"} and value and not value.startswith(("#", "data:")):
                raise RuntimeError("renderer external asset reference is not qualified")


def _local_path(uri):
    parsed = urlsplit(uri)
    if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"} or not parsed.path.startswith("/"):
        raise RuntimeError("renderer requires a canonical local file URL")
    return Path(unquote(parsed.path))


def _docx(rows):
    table = "<w:tbl>" + "".join("<w:tr>" + "".join(f"<w:tc><w:p><w:r><w:t xml:space=\"preserve\">{escape(display_cell(cell))}</w:t></w:r></w:p></w:tc>" for cell in row) + "</w:tr>" for row in rows) + "</w:tbl>"
    document = f"<?xml version=\"1.0\" encoding=\"UTF-8\"?><w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"><w:body>{table}<w:sectPr/></w:body></w:document>"
    return {"[Content_Types].xml": "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/><Default Extension=\"xml\" ContentType=\"application/xml\"/><Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/></Types>", "word/document.xml": document}


def _pptx(rows):
    cells = "".join(f"<a:tc><a:txBody><a:p><a:r><a:t>{escape(display_cell(cell))}</a:t></a:r></a:p></a:txBody><a:tcPr/></a:tc>" for row in rows for cell in row)
    slide = f"<?xml version=\"1.0\" encoding=\"UTF-8\"?><p:sld xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\" xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\"><p:cSld><p:spTree><a:tbl><a:tblGrid/>{cells}</a:tbl></p:spTree></p:cSld></p:sld>"
    return {"[Content_Types].xml": "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/><Default Extension=\"xml\" ContentType=\"application/xml\"/></Types>", "ppt/slides/slide1.xml": slide}


class OfficeCliAdapter:
    def __init__(self, *, binary: str | None = None, browser: str | None = None):
        self.binary = binary or os.environ.get("OTC_OFFICECLI_BINARY", "")
        self.browser = browser or os.environ.get("OTC_OFFICECLI_BROWSER")

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
        capability = check_officecli(self.binary, renderer=request.mode, browser=self.browser)
        if not capability.supported:
            raise RuntimeError(capability.reason)
        if snapshot_path.suffix.lower().lstrip(".") not in capability.formats:
            raise RuntimeError("renderer format is not qualified")
        allowed = {"page", "range", "max_lines"}
        if set(request.selector) - allowed:
            raise RuntimeError("renderer selector is not qualified")
        if "page" in request.selector and snapshot_path.suffix.lower() == ".xlsx":
            raise RuntimeError("page is not a worksheet selector")
        digest = "sha256:" + hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
        suffix, media = {"html": (".html", "text/html"), "screenshot": (".png", "image/png")}.get(request.mode, (".txt", "text/plain"))
        destination = _local_path(request.destination_uri) if request.destination_uri else Path(tempfile.mkdtemp(prefix="otc-view-")) / ("view" + suffix)
        if destination.exists():
            raise FileExistsError(destination)
        with tempfile.TemporaryDirectory(prefix="otc-render-") as directory:
            output = Path(directory) / ("view" + suffix)
            argv = [self.binary, "view", str(snapshot_path), request.mode]
            if request.mode in {"html", "screenshot"}:
                argv += ["--out", str(output)]
            if request.mode == "screenshot":
                argv += ["--render", "html"]
            for key, value in request.selector.items():
                argv += ["--" + key.replace("_", "-"), str(value)]
            result = run_officecli(argv, input_json=None)
            if result.returncode or result.truncated or result.timed_out:
                raise RuntimeError("renderer execution failed or exceeded its limits")
            if request.mode not in {"html", "screenshot"}:
                output.write_text(result.stdout, encoding="utf-8")
            if not output.is_file() or output.stat().st_size > 16 * 1024 * 1024:
                raise RuntimeError("renderer output is unavailable or exceeds its limit")
            data = output.read_bytes()
            if not data.strip():
                raise RuntimeError("renderer output is blank")
            if request.mode == "html":
                _Assets().feed(data.decode("utf-8"))
            if request.mode == "screenshot" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise RuntimeError("renderer output is not PNG")
            if "sha256:" + hashlib.sha256(snapshot_path.read_bytes()).hexdigest() != digest:
                raise RuntimeError("renderer modified its snapshot")
            with destination.open("xb") as stream:
                stream.write(data)
        return {"outputs": [{"uri": destination.as_uri(), "media_type": media, "content_hash": "sha256:" + hashlib.sha256(data).hexdigest()}],
                "source_hash": digest, "renderer": {"name": "officecli", "version": capability.version, "browser": capability.browser, "fonts": "runtime-dependent"}}

    def start_watch(self, snapshot_path: Path):
        capability = check_officecli(self.binary, renderer="watch", browser=self.browser)
        if not capability.supported:
            raise RuntimeError(capability.reason)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        process = subprocess.Popen([self.binary, "watch", str(snapshot_path), "--port", str(port)],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   shell=False, env=runtime_environment(), start_new_session=True)
        url = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and process.poll() is None:
            try:
                with urlopen(url, timeout=0.2) as response:
                    if response.status == 200:
                        return process, url
            except OSError:
                time.sleep(0.05)
        stop_process(process)
        raise RuntimeError("watch runtime did not become ready on its owned port")


__all__ = ["OfficeCliAdapter"]
