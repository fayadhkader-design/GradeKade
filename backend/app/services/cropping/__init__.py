import numpy as np
from PIL import Image


def crop_region(image: Image.Image, x: float, y: float, width: float, height: float) -> Image.Image:
    if not (
        0 <= x < 1
        and 0 <= y < 1
        and width > 0
        and height > 0
        and x + width <= 1.000001
        and y + height <= 1.000001
    ):
        raise ValueError("Answer box must be inside the page")
    box = (
        round(x * image.width),
        round(y * image.height),
        min(image.width, round((x + width) * image.width)),
        min(image.height, round((y + height) * image.height)),
    )
    if box[2] - box[0] < 4 or box[3] - box[1] < 4:
        raise ValueError("Answer box is too small")
    return image.crop(box)


def is_blank(image: Image.Image) -> bool:
    # Ignore a thin edge to avoid treating a box outline as handwriting.
    gray = np.asarray(image.convert("L"))
    edge = max(2, min(gray.shape) // 12)
    interior = gray[edge:-edge, edge:-edge]
    return not interior.size or float((interior < 170).mean()) < 0.004
