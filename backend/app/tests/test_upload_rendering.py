from io import BytesIO

import pymupdf as fitz
import pytest
from PIL import Image, ImageDraw

from app.api import routes
from app.services.ingestion import png_bytes
from app.tests.test_api import setup


def test_pdf_template_upload_is_scaled_and_stored_within_pixel_limit(client, monkeypatch):
    api, _ = client
    monkeypatch.setattr(routes.settings, "max_image_pixels", 500_000)
    with fitz.open() as document:
        document.new_page(width=612, height=792)
        content = document.tobytes()
    response = api.post(
        "/templates",
        data={"name": "Original PDF practice"},
        files={"file": ("worksheet.pdf", content, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    template = response.json()
    stored = api.get(f"/templates/{template['id']}/image")
    assert stored.status_code == 200 and stored.headers["content-type"] == "image/png"
    with Image.open(BytesIO(stored.content)) as image:
        assert image.size == (template["width"], template["height"])
        assert 495_000 < image.width * image.height <= 500_000


@pytest.mark.parametrize("target", ["template", "submission"])
def test_transparent_upload_stores_white_paper_with_dark_ink(client, target):
    api, _ = client
    source = Image.new("RGBA", (200, 300), (0, 0, 0, 0))
    ImageDraw.Draw(source).rectangle((50, 50, 70, 90), fill=(0, 0, 0, 255))
    if target == "template":
        url, data = "/templates", {"name": "Transparent arithmetic worksheet"}
    else:
        ids = setup(api)
        url, data = "/submissions", {
            "student_id": ids["student_id"],
            "worksheet_template_id": ids["template_id"],
        }
    response = api.post(url, data=data, files={"file": ("page.png", png_bytes(source), "image/png")})
    assert response.status_code == 201, response.text
    identifier = response.json()["id"]
    image_url = (
        f"/templates/{identifier}/image"
        if target == "template"
        else f"/submissions/{identifier}/image/original"
    )
    stored = api.get(image_url)
    assert stored.status_code == 200
    with Image.open(BytesIO(stored.content)) as image:
        assert image.mode == "RGB"
        assert image.getpixel((0, 0)) == (255, 255, 255)
        assert image.getpixel((60, 60)) == (0, 0, 0)
