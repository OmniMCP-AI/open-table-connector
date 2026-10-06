from __future__ import annotations

from open_table_connector.local_files import LocalFilesConnector
from open_table_connector.sdk import Client, ConnectorRegistry


def test_png_jpeg_original_bytes_and_anchor(tmp_path):
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (2, 2), "red").save(buffer, format="PNG")
    content = buffer.getvalue()
    client = Client(registry=ConnectorRegistry([LocalFilesConnector()]))
    book = client.workbook.create((tmp_path / "images.xlsx").as_uri(), profile="rich-artifact/1.0")
    sheet = book.worksheet.create("Report")
    sheet.image(type("Image", (), {"content": content, "mime_type": "image/png", "anchor": "B2", "sha256": "sha256:" + __import__("hashlib").sha256(content).hexdigest()})())
    assert book.write().commit.value == "committed"
    reopened = client.workbook((tmp_path / "images.xlsx").as_uri())
    assert reopened.worksheet("Report").images().outcome.value == "succeeded"
