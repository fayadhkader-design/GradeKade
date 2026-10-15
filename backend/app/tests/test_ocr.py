import httpx
import pytest

from app.config import Settings
from app.services.ocr import MathpixOCRProvider, MockOCRProvider, get_provider


def test_mock_never_reads_answer_key():
    assert MockOCRProvider().recognize(b"anything").confidence == 0
    assert MockOCRProvider().recognize(b"anything").raw_text == ""


def test_missing_keys_fall_back():
    assert (
        get_provider(Settings(ocr_provider="mathpix", mathpix_app_id="", mathpix_app_key="")).name == "mock"
    )


def test_mathpix_request_and_result(monkeypatch):
    def post(url, **kwargs):
        assert url == "https://api.mathpix.com/v3/text"
        assert kwargs["headers"]["app_key"] == "test-key"
        assert kwargs["json"]["src"].startswith("data:image/png;base64,")
        return httpx.Response(
            200,
            request=httpx.Request("POST", "https://api.mathpix.com/v3/text"),
            json={"text": r"\frac{1}{2}", "confidence": 0.999},
        )

    monkeypatch.setattr(httpx, "post", post)
    result = MathpixOCRProvider("test-id", "test-key").recognize(b"png")
    assert result.confidence == 0.999


def test_mathpix_errors_are_not_success(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **k: httpx.Response(
            200, request=httpx.Request("POST", "https://api.mathpix.com/v3/text"), json={"error": "bad image"}
        ),
    )
    with pytest.raises(ValueError):
        MathpixOCRProvider("test-id", "test-key").recognize(b"png")


def test_missing_confidence_remains_unknown(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **k: httpx.Response(
            200, request=httpx.Request("POST", "https://api.mathpix.com/v3/text"), json={"text": "７２"}
        ),
    )
    result = MathpixOCRProvider("id", "key").recognize_answer(b"png", "integer")
    assert result.provider_confidence is None
    assert result.normalized_candidate == "72"


def test_failure_result_never_contains_provider_response_or_credentials(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **k: httpx.Response(
            401,
            request=httpx.Request("POST", "https://api.mathpix.com/v3/text"),
            json={"error": "sensitive text"},
        ),
    )
    result = MathpixOCRProvider("id", "secret").recognize_answer(b"png", "integer")
    assert result.error == "ocr_provider_error"
    assert result.raw_text == ""
    assert "secret" not in str(result)


def test_transient_retry_and_privacy_option(monkeypatch):
    calls = []

    def post(*args, **kwargs):
        calls.append(kwargs)
        assert kwargs["json"]["metadata"] == {"improve_mathpix": False}
        assert "expected_answer" not in kwargs["json"]
        return httpx.Response(
            503 if len(calls) == 1 else 200,
            request=httpx.Request("POST", "https://api.mathpix.com/v3/text"),
            json={"text": "42", "confidence": 0.999},
        )

    monkeypatch.setattr(httpx, "post", post)
    assert MathpixOCRProvider("id", "key").recognize_answer(b"png", "integer").raw_text == "42"
    assert len(calls) == 2
