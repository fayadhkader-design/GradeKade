import pytest

from app.services.grading import grade_answer, grade_evidence
from app.services.ocr import OCRResult


@pytest.mark.parametrize("score", ["0.999", {}, [], True, float("nan"), float("inf"), -1, 2, 10**1000])
def test_invalid_variant_score_never_crashes_or_enables_automation(score):
    results = [
        OCRResult("42", 1, normalized_candidate="42"),
        OCRResult("42", score, normalized_candidate="42"),
    ]
    decision, evidence = grade_evidence(results, "42", "integer", allow_unscored_agreement=True)
    assert decision.final_grade is None and decision.grading_confidence == 0
    assert decision.routing_reason == "missing_provider_confidence"
    assert evidence["outcome"] == "NEEDS_REVIEW"


def test_oversized_integer_confidence_does_not_overflow_direct_grading():
    assert grade_answer("42", "42", "integer", 10**1000).final_grade is None


def test_variant_order_does_not_change_conservative_score():
    results = [OCRResult("42", value, normalized_candidate="42") for value in [0.999, 0.998]]
    for observations in [results, list(reversed(results))]:
        decision, _ = grade_evidence(observations, "42", "integer")
        assert decision.final_grade == "correct"
        assert decision.grading_confidence == 0.998
