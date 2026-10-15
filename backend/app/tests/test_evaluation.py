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


def test_denominators_false_grades_and_unknown_alignment():
    from app.evaluation.report import report

    rows = [
        {
            "answer_type": "integer",
            "automated": True,
            "system_grade": "correct",
            "verified_grade": "incorrect",
            "transcription_status": "readable",
            "raw_ocr_text": "42",
            "student_actual_answer": "47",
            "grading_confidence": 0.999,
            "source": "real_handwriting",
            "ocr_provider": "mathpix",
        },
        {
            "answer_type": "fraction",
            "automated": True,
            "system_grade": "incorrect",
            "verified_grade": "correct",
            "transcription_status": "readable",
            "raw_ocr_text": "3/4",
            "student_actual_answer": "1/2",
            "grading_confidence": 0.999,
        },
        {"answer_type": "integer", "automated": True, "system_grade": "correct"},
        {"answer_type": "decimal", "automated": False, "system_grade": "uncertain", "ocr_error": True},
    ]
    result = report(rows)
    assert result["auto_grade_precision"] == 0
    assert result["verified_automated_answers"] == 2
    assert result["unverified_automated_answers"] == 1
    assert result["false_auto_correct_count"] == result["false_auto_incorrect_count"] == 1
    assert result["auto_grade_coverage"] == 0.75
    assert result["ocr_failure_rate"] == 0.25
    assert result["alignment_failure_rate"] is None
    assert result["by_answer_type"]["decimal"]["auto_grade_precision"] is None


def test_recorded_evaluation_never_calls_provider(tmp_path):
    from app.evaluation.run import evaluate_records

    (tmp_path / "records.json").write_text('[{"answer_type":"integer","source":"unknown"}]')
    assert evaluate_records(tmp_path)[0]["source"] == "unknown"
