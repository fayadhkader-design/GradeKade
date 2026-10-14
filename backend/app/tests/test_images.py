import numpy as np
import pytest
from PIL import Image, ImageDraw
from app.services.ingestion import ingest, png_bytes
from app.services.cropping import crop_region, is_blank
from app.services.alignment import align_submission_to_template


def test_ingest_and_crop():
    image = Image.new("RGB", (600, 800), "white")
    assert ingest(png_bytes(image)).size == (600, 800)
    assert crop_region(image, .1, .1, .2, .2).size == (120, 160)
    assert is_blank(image)
    with pytest.raises(ValueError):
        crop_region(image, .9, 0, .2, .1)


def test_reject_input():
    for data in [b"", b"evil.exe", png_bytes(Image.new("RGB", (10, 10)))]:
        with pytest.raises(ValueError):
            ingest(data)
    with pytest.raises(ValueError):
        ingest(png_bytes(Image.new("RGB", (200, 200))), max_pixels=100)


def test_insufficient_alignment_forces_review():
    image = Image.new("RGB", (600, 800), "white")
    assert not align_submission_to_template(image, image).metadata["verified"]


def test_alignment_of_feature_rich_page():
    image = Image.new("RGB", (600, 800), "white")
    draw = ImageDraw.Draw(image)
    rng = np.random.default_rng(42)
    for x, y, size in rng.integers([10, 10, 4], [580, 780, 16], size=(150, 3)):
        draw.rectangle((int(x), int(y), int(x + size), int(y + size)), fill="black")
    result = align_submission_to_template(image, image.rotate(2, fillcolor="white"))
    assert result.metadata["verified"]
    assert result.image.size == image.size
