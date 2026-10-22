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


def test_factory_preserves_virtual_environment_python_symlink(tmp_path):
    interpreter = tmp_path / "venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.symlink_to(sys.executable)
    config = Settings(ocr_provider="paddle", paddle_python=interpreter)
    selected = get_provider(config)
    assert selected.python == str(interpreter.absolute())
    assert selected.python != str(interpreter.resolve())


def test_agreement_is_opt_in_and_never_a_provider_probability():
    results = [provider().parse_result({"raw_text": "42"}, "integer")] * 3
    decision, evidence = grade_evidence(results, "42", "integer")
    assert decision.final_grade is None
    decision, _ = grade_evidence(results, "42", "integer", correct_threshold=0)
    assert decision.final_grade is None and decision.routing_reason == "missing_provider_confidence"
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


def test_provider_keeps_one_real_worker_for_multiple_requests(tmp_path, monkeypatch):
    (tmp_path / "paddle.py").write_text('RUNTIME_MARKER = "isolated-paddle-runtime"\n')
    (tmp_path / "paddleocr.py").write_text("""
import paddle
assert paddle.RUNTIME_MARKER == "isolated-paddle-runtime"
print("third-party initialization progress")
class Result:
    json = {"res": {"rec_formula": "72"}}
class FormulaRecognition:
    def __init__(self, **kwargs): pass
    def predict(self, input, batch_size): return iter([Result()])
""")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    p = PaddleOCRProvider(sys.executable, cache_root=str(tmp_path / "cache"))
    try:
        assert p.initialize()
        pid = p._process.pid
        crop = png_bytes(Image.new("RGB", (40, 40), "white"))
        assert p.recognize_answer(crop, "integer").normalized_candidate == "72"
        assert p.recognize_answer(crop, "integer").normalized_candidate == "72"
        assert p._process.pid == pid
        assert p.initialization_seconds >= 0
    finally:
        p.close()
    assert not p.available


def test_paddle_page_pipeline_times_variants_and_preserves_unknown_confidence(client, monkeypatch):
    from app.services import pipeline
    from app.tests.test_api import setup, upload

    class FakePaddle:
        name, available = "paddle", True

        def recognize_answer(self, image, expected_answer_type, optional_context=None):
            return provider().parse_result(
                {"raw_text": "42", "inference_seconds": 0.01}, expected_answer_type
            )

    monkeypatch.setattr(pipeline, "get_provider", lambda config: FakePaddle())
    monkeypatch.setattr(
        pipeline,
        "settings",
        pipeline.settings.model_copy(
            update={
                "ocr_variants": "color,grayscale,contrast",
                "paddle_allow_experimental_auto_grade": True,
            }
        ),
    )
    api, _ = client
    ids = setup(api)
    page = upload(api, ids, synthetic=False)
    response = api.post(f"/submissions/{page['id']}/process")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["processing"]["ocr_mode"] == "REAL"
    assert data["processing"]["total_inference_seconds"] == pytest.approx(0.6)
    assert data["processing"]["average_inference_seconds_per_answer"] == pytest.approx(0.03)
    assert data["processing"]["total_ocr_seconds"] >= 0
    first = data["answers"][0]
    assert first["ocr_confidence"] is None
    assert first["decision"] == "AUTO_CORRECT"
    assert first["evidence"]["variants_run"] == 3
    records = api.get("/evaluation?source=synthetic").json()
    assert records["report"]["by_provider"]["paddle"][
        "average_inference_seconds_per_answer"
    ] == pytest.approx(0.03)


def test_missing_paddle_is_visibly_unavailable_in_health(client, monkeypatch):
    from app.api import routes

    missing = provider()
    missing.initialize()
    monkeypatch.setattr(routes, "get_provider", lambda config: missing)
    api, _ = client
    response = api.get("/health").json()
    assert response["ocr_provider"] == "paddle"
    assert response["status"] == "degraded" and not response["ocr_available"]
    assert "Paddle unavailable" in response["ocr_diagnostic"]


def test_real_gate_includes_paddle_recorded_results(tmp_path):
    (tmp_path / "records.json").write_text(
        json.dumps(
            [
                {
                    "answer_type": "integer",
                    "source": "real_handwriting",
                    "ocr_provider": "paddle",
                    "raw_ocr_text": "72",
                    "student_actual_answer": "72",
                    "expected_answer": "72",
                    "transcription_status": "readable",
                    "verified_grade": "correct",
                    "system_grade": "correct",
                    "automated": False,
                    "inference_seconds": 0.2,
                }
            ]
        )
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.evaluation.run",
            "--dataset",
            str(tmp_path),
            "--provider",
            "recorded",
            "--require-real",
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["real_handwriting_real_ocr_answers"] == 1
    assert report["by_provider"]["paddle"]["normalized_ocr_accuracy"] == 1
    assert report["average_inference_seconds_per_answer"] == 0.2


def test_model_initialization_failure_stays_explicit(tmp_path, monkeypatch):
    (tmp_path / "paddleocr.py").write_text("""
class FormulaRecognition:
    def __init__(self, **kwargs):
        raise RuntimeError("private-path-or-provider-detail")
""")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    p = PaddleOCRProvider(sys.executable, cache_root=str(tmp_path / "cache"))
    try:
        assert not p.initialize()
        assert p.name == "paddle" and not p.available
        assert p.diagnostic and "private-path-or-provider-detail" not in p.diagnostic
        assert p.recognize_answer(b"crop", "integer").error == "paddle_initialization_failed"
    finally:
        p.close()
