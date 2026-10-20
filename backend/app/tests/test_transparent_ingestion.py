from io import BytesIO

import pytest
from PIL import Image, ImageDraw

from app.services.ingestion import ingest, png_bytes


@pytest.mark.parametrize("mode", ["RGBA", "LA", "P"])
def test_transparent_png_preserves_ink_on_white_paper(mode):
    if mode == "P":
        source = Image.new(mode, (200, 300), 0)
        source.putpalette([0, 0, 0, 0, 0, 0] + [0] * 762)
        source.info["transparency"] = 0
        ink = 1
    else:
        source = Image.new(mode, (200, 300), (0, 0) if mode == "LA" else (0, 0, 0, 0))
        ink = (0, 255) if mode == "LA" else (0, 0, 0, 255)
    ImageDraw.Draw(source).rectangle((50, 50, 70, 90), fill=ink)
    image = ingest(png_bytes(source))
    assert image.mode == "RGB" and image.size == source.size
    assert image.getpixel((0, 0)) == (255, 255, 255)
    assert image.getpixel((60, 60)) == (0, 0, 0)


def test_partial_transparency_is_composited_and_opaque_pixels_are_unchanged():
    source = Image.new("RGBA", (200, 200), (0, 0, 0, 128))
    source.putpixel((10, 10), (30, 60, 90, 255))
    image = ingest(png_bytes(source))
    assert image.getpixel((0, 0)) == (127, 127, 127)
    assert image.getpixel((10, 10)) == (30, 60, 90)


def test_opaque_png_keeps_original_pixels():
    source = Image.new("RGB", (200, 300), (10, 20, 30))
    assert ingest(png_bytes(source)).tobytes() == source.tobytes()


def test_exif_orientation_is_applied_before_alpha_flattening():
    source = Image.new("RGBA", (200, 300), (0, 0, 0, 0))
    source.putpixel((20, 30), (0, 0, 0, 255))
    exif = Image.Exif()
    exif[274] = 6  # Rotate 90 degrees clockwise.
    encoded = BytesIO()
    source.save(encoded, format="PNG", exif=exif)
    image = ingest(encoded.getvalue())
    assert image.size == (300, 200)
    assert image.getpixel((269, 20)) == (0, 0, 0)
    assert image.getpixel((0, 0)) == (255, 255, 255)
