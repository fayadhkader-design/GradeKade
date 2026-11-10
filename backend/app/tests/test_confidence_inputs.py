import pytest

from app.services.grading import grade_answer


@pytest.mark.parametrize(
    "confidence", [None, True, False, "1.0", {}, [], float("nan"), float("inf"), -1, 1.1]
)
def test_invalid_confidence_abstains_without_crashing(confidence):
    decision = grade_answer("42", "42", "integer", confidence)
    assert decision.system_grade == "correct"
    assert decision.final_grade is None
    assert decision.review_status == "needs_review"
    assert decision.grading_confidence == 0


@pytest.mark.parametrize("confidence", [0, 0.5, 0.995, 1])
def test_valid_numeric_confidence_retains_threshold_behavior(confidence):
    decision = grade_answer("42", "42", "integer", confidence)
    assert decision.final_grade == ("correct" if confidence >= 0.995 else None)
