from dataclasses import dataclass
import math
from app.services.normalization import AnswerType, answers_equivalent, normalize_answer


@dataclass(frozen=True)
class GradeDecision:
    normalized_answer: str | None
    system_grade: str
    final_grade: str | None
    grading_confidence: float
    review_status: str
    routing_reason: str


def grade_answer(raw: str, expected: str, answer_type: AnswerType, confidence: float,
                 threshold: float = 0.995, alignment_verified: bool = True,
                 auto_grade_enabled: bool = True, blank: bool = False) -> GradeDecision:
    normalize_answer(expected, answer_type)  # Bad answer keys fail before grading.
    normalized = None
    try:
        normalized = normalize_answer(raw, answer_type)
    except ValueError:
        pass
    valid_confidence = math.isfinite(confidence) and 0 <= confidence <= 1
    effective = confidence if valid_confidence and alignment_verified and normalized is not None and not blank else 0.0
    prediction = "uncertain" if normalized is None or blank else (
        "correct" if answers_equivalent(raw, expected, answer_type) else "incorrect")
    reason = ("blank_crop" if blank else "unverified_alignment" if not alignment_verified else
              "invalid_answer" if normalized is None else "template_requires_review" if not auto_grade_enabled else
              "low_ocr_confidence" if not valid_confidence or effective < threshold else "high_confidence")
    accepted = reason == "high_confidence"
    return GradeDecision(normalized, prediction, prediction if accepted else None, effective,
                         "auto_accepted" if accepted else "needs_review", reason)
