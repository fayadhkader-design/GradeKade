"""Swappable OCR providers. Mock never claims to read an arbitrary image."""

import base64
import math
from dataclasses import dataclass, field
from time import sleep
from typing import Protocol

import httpx

from app.config import Settings
from app.services.ingestion import image_digest
from app.services.normalization import AnswerType, normalize_answer


@dataclass(frozen=True)
class OCRResult:
    raw_text: str
    confidence: float | None
    structured_math: dict | None = None
    normalized_candidate: str | None = None
    provider_metadata: dict = field(default_factory=dict)
    error: str | None = None
    provider_name: str | None = None

    @property
    def provider_confidence(self):
        return self.confidence


class OCRProvider(Protocol):
    name: str

    def recognize_answer(
        self, image: bytes, expected_answer_type: AnswerType, optional_context: dict | None = None
    ) -> OCRResult: ...


class AnswerRecognition:
    """Context supplies type, never the answer key. Legacy recognize remains supported."""

    def recognize_answer(self, image, expected_answer_type, optional_context=None):
        try:
            result = self.recognize(image)
            try:
                candidate = normalize_answer(result.raw_text, expected_answer_type)
            except ValueError:
                candidate = None
            from dataclasses import replace

            return replace(result, normalized_candidate=candidate, provider_name=self.name)
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            return OCRResult("", None, error="ocr_provider_error", provider_name=self.name)


class MockOCRProvider(AnswerRecognition):
    name = "mock"

    def recognize(self, image: bytes) -> OCRResult:
        return OCRResult("", 0.0)


class FixtureOCRProvider(AnswerRecognition):
    """Explicit synthetic plumbing demo, separate from any answer key."""

    name = "synthetic_fixture"

    def __init__(self, predictions: dict[str, dict]):
        self.predictions = predictions

    def recognize(self, image: bytes) -> OCRResult:

        prediction = self.predictions.get(image_digest(image), {})
        return OCRResult(prediction.get("raw_text", ""), prediction.get("confidence", 0.0))


class MathpixOCRProvider(AnswerRecognition):
    name = "mathpix"

    def __init__(self, app_id: str, app_key: str, timeout: float = 8, retries: int = 1):
        self.app_id = app_id
        self.app_key = app_key
        self.timeout, self.retries = timeout, retries

    def recognize(self, image: bytes) -> OCRResult:
        encoded = base64.b64encode(image).decode()
        if len(encoded) > 2_000_000:
            raise ValueError("OCR crop exceeds provider image limit")
        for attempt in range(self.retries + 1):
            try:
                response = httpx.post(
                    "https://api.mathpix.com/v3/text",
                    timeout=self.timeout,
                    headers={"app_id": self.app_id, "app_key": self.app_key},
                    json={
                        "src": "data:image/png;base64," + encoded,
                        "formats": ["text"],
                        "math_inline_delimiters": ["", ""],
                        "include_line_data": True,
                        "metadata": {"improve_mathpix": False},
                    },
                )
                if response.status_code not in {429, 500, 502, 503, 504} or attempt == self.retries:
                    break
            except httpx.TransportError:
                if attempt == self.retries:
                    raise
            sleep(0.25 * (attempt + 1))
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise TypeError("OCR provider returned invalid response")
        if data.get("error"):
            raise ValueError("OCR provider could not recognize the crop")
        text = data.get("text", "")
        confidence = data.get("confidence")
        if confidence is not None:
            if isinstance(confidence, bool):
                raise ValueError("Invalid confidence")
            confidence = float(confidence)
        if (
            confidence is not None and (not math.isfinite(confidence) or not 0 <= confidence <= 1)
        ) or not isinstance(text, str):
            raise ValueError("OCR provider returned invalid data")
        lines = data.get("line_data") or []
        if not isinstance(lines, list):
            raise TypeError("Invalid line data")
        metadata = {
            key: data[key]
            for key in ("confidence_rate", "is_handwritten", "is_printed", "version")
            if key in data
        }
        metadata["line_count"] = len(lines)
        metadata["line_error"] = any(isinstance(line, dict) and line.get("error_id") for line in lines)
        return OCRResult(text[:1000], confidence, provider_metadata=metadata)


REAL_OCR_PROVIDERS = frozenset({"mathpix", "paddle"})


def get_provider(config: Settings) -> OCRProvider:
    if config.ocr_provider == "paddle":
        from app.services.ocr.paddle import cached_paddle_provider

        return cached_paddle_provider(
            # Resolving a venv's Python symlink selects the base interpreter instead.
            str(config.paddle_python.absolute()),
            config.paddle_model_name,
            str(config.paddle_model_dir.resolve()) if config.paddle_model_dir else None,
            str(config.paddle_cache_root.resolve()),
            config.paddle_cpu_threads,
            config.paddle_initialization_timeout_seconds,
            config.paddle_inference_timeout_seconds,
        )
    if (
        config.ocr_provider == "mathpix"
        and config.mathpix_app_id.get_secret_value()
        and config.mathpix_app_key.get_secret_value()
    ):
        return MathpixOCRProvider(
            config.mathpix_app_id.get_secret_value(),
            config.mathpix_app_key.get_secret_value(),
            config.ocr_timeout_seconds,
            config.ocr_retries,
        )
    return MockOCRProvider()
