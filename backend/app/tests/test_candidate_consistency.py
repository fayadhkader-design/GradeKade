import pytest

from app.services.grading import grade_evidence
from app.services.ocr import OCRResult


@pytest.mark.parametrize("raw,candidate", [("47", "42"), ("42", "47"), ("42 or 47", "42"), ("$42", "42")])
@pytest.mark.parametrize("confidence", [0.998, 1.0])
def test_conflicting_candidate_and_raw_text_never_auto_grade(raw, candidate, confidence):
    result = OCRResult(raw, confidence, normalized_candidate=candidate)
    decision, evidence = grade_evidence([result], "42", "integer")
    assert decision.final_grade is None
    assert decision.review_status == "needs_review"
    assert decision.routing_reason == "invalid_ocr_candidate"
    assert decision.grading_confidence == 0
    assert evidence["outcome"] == "NEEDS_REVIEW"
    assert evidence["candidate_raw_text_consistent"] is False


def test_one_inconsistent_variant_blocks_otherwise_agreeing_candidates():
    results = [
        OCRResult("42", 1, normalized_candidate="42"),
        OCRResult("47", 1, normalized_candidate="42"),
    ]
    decision, evidence = grade_evidence(results, "42", "integer")
    assert decision.final_grade is None
    assert decision.routing_reason == "invalid_ocr_candidate"
    assert evidence["variant_agreement"] is False


def test_unscored_experimental_agreement_cannot_override_candidate_conflict():
    results = [OCRResult("47", None, normalized_candidate="42")] * 3
    decision, _ = grade_evidence(results, "42", "integer", allow_unscored_agreement=True)
    assert decision.final_grade is None
    assert decision.routing_reason == "invalid_ocr_candidate"


@pytest.mark.parametrize(
    "raw,candidate,kind", [("042", "42", "integer"), ("2/4", "1/2", "fraction"), ("$.5$", "0.5", "decimal")]
)
def test_canonical_equivalent_text_still_auto_grades(raw, candidate, kind):
    decision, evidence = grade_evidence([OCRResult(raw, 1, normalized_candidate=candidate)], candidate, kind)
    assert decision.final_grade == "correct"
    assert evidence["candidate_raw_text_consistent"] is True


def test_coherent_wrong_answer_keeps_stricter_incorrect_threshold():
    result = OCRResult("47", 0.998, normalized_candidate="47")
    decision, _ = grade_evidence([result], "42", "integer")
    assert decision.system_grade == "incorrect"
    assert decision.final_grade is None and decision.routing_reason == "low_ocr_confidence"
