import httpx
import pytest
from app.config import Settings
from app.services.ocr import MathpixOCRProvider, MockOCRProvider, get_provider


def test_mock_never_reads_answer_key():
    assert MockOCRProvider().recognize(b"anything").confidence == 0
    assert MockOCRProvider().recognize(b"anything").raw_text == ""


def test_missing_keys_fall_back():
    assert get_provider(Settings(ocr_provider="mathpix", mathpix_app_id="", mathpix_app_key="")).name == "mock"


def test_mathpix_request_and_result(monkeypatch):
    def post(url, **kwargs):
        assert url == "https://api.mathpix.com/v3/text"
        assert kwargs["headers"]["app_key"] == "test-key"
        assert kwargs["json"]["src"].startswith("data:image/png;base64,")
        return httpx.Response(200, request=httpx.Request("POST", "https://api.mathpix.com/v3/text"), json={"text": r"\frac{1}{2}", "confidence": .999})
    monkeypatch.setattr(httpx, "post", post)
    result = MathpixOCRProvider("test-id", "test-key").recognize(b"png")
    assert result.confidence == .999


def test_mathpix_errors_are_not_success(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Response(200, request=httpx.Request("POST", "https://api.mathpix.com/v3/text"), json={"error": "bad image"}))
    with pytest.raises(ValueError):
        MathpixOCRProvider("test-id", "test-key").recognize(b"png")
