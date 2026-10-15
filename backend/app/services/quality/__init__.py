"""Simple measurable rejection gates, not a calibrated camera-quality model."""

import cv2
import numpy as np
from PIL import Image


def assess_photo(image: Image.Image, blur_minimum: float = 3) -> dict:
    preview = image.convert("L").copy()
    preview.thumbnail((1200, 1200))
    gray = np.asarray(preview)
    brightness = float(gray.mean())
    ink_fraction = float((gray < 180).mean())
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    reasons = []
    if brightness < 30:
        reasons.append("extremely_dark")
    # White paper is normal: require almost no visible marks as well.
    if brightness > 253 and ink_fraction < 0.0005:
        reasons.append("overexposed_or_empty")
    if blur < blur_minimum:
        reasons.append("severe_blur")
    if min(image.size) < 300:
        reasons.append("low_resolution")
    return {
        "usable": not reasons,
        "reasons": reasons,
        "brightness": brightness,
        "ink_fraction": ink_fraction,
        "laplacian_variance": blur,
        "measurement_max_dimension": 1200,
        "blur_minimum": blur_minimum,
    }
