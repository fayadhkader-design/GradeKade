"""Swappable OCR providers. Mock never claims to read an arbitrary image."""

import base64
import math
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.config import Settings
from app.services.ingestion import image_digest


@dataclass(frozen=True)
class OCRResult:
    raw_text: str
    confidence: float
    structured_math: dict | None = None


class OCRProvider(Protocol):
    name: str

    def recognize(self, image: bytes) -> OCRResult: ...


class MockOCRProvider:
    name = "mock"

    def recognize(self, image: bytes) -> OCRResult:
        return OCRResult("", 0.0)


class FixtureOCRProvider:
    """Explicit synthetic plumbing demo, separate from any answer key."""

    name = "synthetic_fixture"

    def __init__(self, predictions: dict[str, dict]):
        self.predictions = predictions

    def recognize(self, image: bytes) -> OCRResult:

        prediction = self.predictions.get(image_digest(image), {})
        return OCRResult(prediction.get("raw_text", ""), prediction.get("confidence", 0.0))


class MathpixOCRProvider:
    name = "mathpix"

    def __init__(self, app_id: str, app_key: str):
        self.app_id = app_id
        self.app_key = app_key

    def recognize(self, image: bytes) -> OCRResult:
        response = httpx.post(
            "https://api.mathpix.com/v3/text",
            timeout=25,
            headers={"app_id": self.app_id, "app_key": self.app_key},
            json={
                "src": "data:image/png;base64," + base64.b64encode(image).decode(),
                "formats": ["text"],
                "math_inline_delimiters": ["", ""],
            },
        )
        response.raise_for_status()
        data = response.json()
        if data.get("error"):
            raise ValueError("OCR provider could not recognize the crop")
        text = data.get("text", "")
        confidence = float(data.get("confidence", 0))
        if not math.isfinite(confidence) or not 0 <= confidence <= 1 or not isinstance(text, str):
            raise ValueError("OCR provider returned invalid data")
        return OCRResult(text[:1000], confidence)


def get_provider(config: Settings) -> OCRProvider:
    if (
        config.ocr_provider == "mathpix"
        and config.mathpix_app_id.get_secret_value()
        and config.mathpix_app_key.get_secret_value()
    ):
        return MathpixOCRProvider(
            config.mathpix_app_id.get_secret_value(), config.mathpix_app_key.get_secret_value()
        )
    return MockOCRProvider()
