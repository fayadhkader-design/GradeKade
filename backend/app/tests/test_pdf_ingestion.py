import pymupdf as fitz
import pytest

from app.services.ingestion import ingest


@pytest.mark.parametrize("size", [(612, 792), (1000, 1000), (595, 842), (841.89, 595.28)])
@pytest.mark.parametrize("max_pixels", [500_000, 20_000_000])
def test_pdf_render_respects_budget_without_rejecting_rounding(size, max_pixels):
    with fitz.open() as document:
        page = document.new_page(width=size[0], height=size[1])
        page.insert_text((30, 40), "Original GradeKade arithmetic worksheet")
        content = document.tobytes()
    image = ingest(content, max_pixels=max_pixels)
    assert image.mode == "RGB"
    assert image.width * image.height <= max_pixels
    if max_pixels == 500_000:
        assert image.width * image.height > max_pixels * 0.99
    assert image.width / image.height == pytest.approx(size[0] / size[1], rel=0.005)
    assert image.getextrema()[0][0] < 255  # Printed content survives rendering.


def test_pdf_uses_only_first_page_and_keeps_normal_resolution():
    with fitz.open() as document:
        document.new_page(width=200, height=300)
        second = document.new_page(width=600, height=800)
        second.draw_rect(second.rect, fill=(0, 0, 0))
        image = ingest(document.tobytes())
    assert image.size == (400, 600)
    assert image.getextrema() == ((255, 255),) * 3
