import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from app.config import Settings
from app.services.grading import grade_evidence
from app.services.ingestion import png_bytes
from app.services.ocr import get_provider
from app.services.ocr.paddle import PaddleOCRProvider


def provider():
    return PaddleOCRProvider("/missing/python")


@pytest.mark.parametrize(
    ("raw", "kind", "candidate"),
    [
        ("72", "integer", "72"),
        ("-3", "integer", "-3"),
        ("0.50", "decimal", "0.5"),
        (r"\frac{1}{2}", "fraction", "1/2"),
        (r"\(\frac { 2 } { 4 }\)", "fraction", "1/2"),
        (r"\tfrac{1}{2}", "fraction", "1/2"),
        ("1/2", "integer", None),
        ("x+2", "integer", None),
        ("42 or 47", "integer", None),
        ("", "integer", None),
    ],
)
def test_parsing(raw, kind, candidate):
    result = provider().parse_result({"raw_text": raw, "inference_seconds": 0.12}, kind)
    assert result.raw_text == raw and result.normalized_candidate == candidate
    assert result.confidence is None and result.provider_name == "paddle"
    assert result.provider_metadata["inference_seconds"] == 0.12
    assert result.structured_math["format"] == "latex"


def test_invalid_output_and_failure():
    assert provider().parse_result({"raw_text": 72}, "integer").error == "paddle_invalid_output"
    result = provider().parse_result({"error": "paddle_timeout"}, "integer")
    assert result.raw_text == "" and result.confidence is None and result.error
    result = provider().recognize_answer(b"image", "integer")
    assert result.error == "paddle_initialization_failed" and result.provider_metadata["diagnostic"]
    assert (
        provider()
        .parse_result({"raw_text": "72", "inference_seconds": float("nan")}, "integer")
        .provider_metadata.get("inference_seconds")
        is None
    )


def test_factory_does_not_silently_fall_back():
    config = Settings(ocr_provider="paddle", paddle_python=Path("/missing/paddle"))
    first, second = get_provider(config), get_provider(config)
    assert first is second and first.name == "paddle"
    assert not first.initialize() and first.diagnostic


def test_agreement_is_opt_in_and_never_a_provider_probability():
    results = [provider().parse_result({"raw_text": "42"}, "integer")] * 3
    decision, evidence = grade_evidence(results, "42", "integer")
    assert decision.final_grade is None
    decision, evidence = grade_evidence(results, "42", "integer", allow_unscored_agreement=True)
    assert decision.final_grade == "correct" and evidence["experimental_auto_grade"]
    assert evidence["strategy"] == "experimental_unscored_variant_agreement_v1"
    assert all(r.confidence is None for r in results)
    bad = provider().parse_result({"raw_text": "47"}, "integer")
    decision, _ = grade_evidence([*results[:2], bad], "42", "integer", allow_unscored_agreement=True)
    assert decision.final_grade is None and decision.routing_reason == "variant_disagreement"
    # Even a lowered threshold cannot waive the minimum-variant evidence gate.
    decision, _ = grade_evidence(
        results[:1], "42", "integer", allow_unscored_agreement=True, correct_threshold=0
    )
    assert decision.final_grade is None
    decision, _ = grade_evidence(
        results, "42", "integer", allow_unscored_agreement=True, alignment_verified=False
    )
    assert decision.final_grade is None


def test_isolated_cpu_worker_protocol_without_model_download(tmp_path):
    """Exercise the actual worker using a tiny fake paddleocr package in its env."""
    fake = tmp_path / "paddleocr.py"
    fake.write_text("""
class Result:
    json = {"res": {"rec_formula": r"\\frac{1}{2}", "input_path": "/private/path"}}
class FormulaRecognition:
    def __init__(self, **kwargs):
        assert kwargs["device"] == "cpu"
        assert kwargs["model_name"] == "PP-FormulaNet-S"
    def predict(self, input, batch_size):
        assert input.shape[2] == 3 and batch_size == 1
        return iter([Result()])
""")
    import os

    worker = Path(__file__).parents[1] / "services/ocr/paddle_worker.py"
    image = Image.new("RGB", (100, 60), "white")
    ImageDraw.Draw(image).text((10, 10), "1/2", fill="black")
    import base64

    result = subprocess.run(
        [
            sys.executable,
            str(worker),
            "--model-name",
            "PP-FormulaNet-S",
            "--cache-root",
            str(tmp_path / "cache"),
            "--cpu-threads",
            "2",
        ],
        check=False,
        input=json.dumps({"image": base64.b64encode(png_bytes(image)).decode()}) + "\n",
        env={**os.environ, "PYTHONPATH": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr
    responses = [json.loads(line.split(":", 1)[1]) for line in result.stdout.splitlines()]
    assert responses[0]["ready"] and responses[1]["raw_text"] == r"\frac{1}{2}"
    assert responses[1]["inference_seconds"] >= 0
    assert "/private/path" not in result.stdout


def test_worker_timeout_stops_before_next_crop(monkeypatch, tmp_path):
    p = PaddleOCRProvider(sys.executable)
    monkeypatch.setattr(p, "_initialize", lambda: True)

    class Pipe:
        def write(self, value):
            pass

        def flush(self):
            pass

    class Process:
        stdin = Pipe()

    p._process = Process()
    stopped = []
    monkeypatch.setattr(p, "_receive", lambda timeout: {"error": "paddle_timeout"})
    monkeypatch.setattr(p, "_stop", lambda: stopped.append(True))
    result = p.recognize_answer(b"image", "integer")
    assert stopped and result.error == "paddle_inference_failed"
