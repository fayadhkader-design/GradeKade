import json

from app.evaluation.run import DEFAULT_DATA, EvaluationMetrics, evaluate
from app.services.ocr import FixtureOCRProvider, MockOCRProvider


def test_fixture_evaluation_and_truth_independence():
    predictions = json.loads((DEFAULT_DATA / "mock_predictions.json").read_text())
    metrics = evaluate(DEFAULT_DATA, FixtureOCRProvider(predictions), 0.995).summary()
    assert metrics["total_answers"] == 20
    assert metrics["ocr_accuracy"] == 0.95
    assert metrics["auto_grade_precision"] == 1
    assert metrics["auto_grade_coverage"] == 0.75
    assert metrics["human_review_rate"] == 0.25


def test_no_automated_decisions_is_undefined_precision():
    metrics = evaluate(DEFAULT_DATA, MockOCRProvider(), 0.995).summary()
    assert metrics["auto_grade_precision"] is None and metrics["auto_grade_coverage"] == 0
    assert metrics["human_review_rate"] == 1
    assert EvaluationMetrics(0, 0, 0, 0).summary()["ocr_accuracy"] is None
