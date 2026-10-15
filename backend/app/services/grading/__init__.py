import math
from dataclasses import dataclass

from app.services.normalization import AnswerType, answers_equivalent, normalize_answer


@dataclass(frozen=True)
class GradeDecision:
    normalized_answer: str | None
    system_grade: str
    final_grade: str | None
    grading_confidence: float
    review_status: str
    routing_reason: str


def grade_answer(
    raw: str,
    expected: str,
    answer_type: AnswerType,
    confidence: float,
    threshold: float = 0.995,
    alignment_verified: bool = True,
    auto_grade_enabled: bool = True,
    blank: bool = False,
) -> GradeDecision:
    normalize_answer(expected, answer_type)  # Bad answer keys fail before grading.
    normalized = None
    try:
        normalized = normalize_answer(raw, answer_type)
    except ValueError:
        pass
    valid_confidence = math.isfinite(confidence) and 0 <= confidence <= 1
    effective = (
        confidence
        if valid_confidence and alignment_verified and normalized is not None and not blank
        else 0.0
    )
    prediction = (
        "uncertain"
        if normalized is None or blank
        else ("correct" if answers_equivalent(raw, expected, answer_type) else "incorrect")
    )
    reason = (
        "blank_crop"
        if blank
        else "unverified_alignment"
        if not alignment_verified
        else "invalid_answer"
        if normalized is None
        else "template_requires_review"
        if not auto_grade_enabled
        else "low_ocr_confidence"
        if not valid_confidence or effective < threshold
        else "high_confidence"
    )
    accepted = reason == "high_confidence"
    return GradeDecision(
        normalized,
        prediction,
        prediction if accepted else None,
        effective,
        "auto_accepted" if accepted else "needs_review",
        reason,
    )


def grade_evidence(
    results,
    expected,
    answer_type,
    *,
    correct_threshold=0.995,
    incorrect_threshold=0.999,
    alignment_verified=True,
    alignment_confidence=1.0,
    alignment_minimum=0.8,
    quality_usable=True,
    auto_grade_enabled=True,
    blank=False,
    allow_unscored_agreement=False,
    min_agreeing_variants=3,
):
    """A rule score: never increase vendor confidence through correlated variants."""
    candidates = [r.normalized_candidate for r in results]
    failures = not results or any(r.error for r in results)
    ambiguous = any(
        r.provider_metadata.get("line_error") or r.provider_metadata.get("line_count", 1) > 1 for r in results
    )
    agreement = bool(candidates) and candidates[0] is not None and len(set(candidates)) == 1
    known_scores = [r.confidence for r in results if r.confidence is not None]
    scores_available = bool(results) and all(
        isinstance(r.confidence, (int, float))
        and not isinstance(r.confidence, bool)
        and math.isfinite(r.confidence)
        and 0 <= r.confidence <= 1
        for r in results
    )
    score = min(known_scores) if len(known_scores) == len(results) and known_scores else 0
    if not 2 <= min_agreeing_variants <= 3:
        raise ValueError("Agreement policy requires two or three variants")
    unscored = bool(results) and all(r.confidence is None for r in results)
    agreement_rule_score = min(1.0, len(results) / min_agreeing_variants) if agreement else 0.0
    experimental = allow_unscored_agreement and unscored
    if experimental:
        score = agreement_rule_score
    gates = alignment_verified and alignment_confidence >= alignment_minimum and quality_usable
    predicted_correct = agreement and answers_equivalent(candidates[0], expected, answer_type)
    decision = grade_answer(
        results[0].raw_text if results else "",
        expected,
        answer_type,
        score if agreement and not ambiguous and not failures else 0,
        correct_threshold if predicted_correct else incorrect_threshold,
        gates,
        auto_grade_enabled and (scores_available or (experimental and len(results) >= min_agreeing_variants)),
        blank,
    )
    reason = (
        "ocr_provider_error"
        if failures
        else "poor_photo_quality"
        if not quality_usable
        else "blank_crop"
        if blank
        else "ambiguous_ocr"
        if ambiguous
        else "variant_disagreement"
        if len(results) > 1 and not agreement
        else decision.routing_reason
        if not agreement
        else "missing_provider_confidence"
        if not scores_available and not experimental
        else "insufficient_variant_agreement"
        if experimental and len(results) < min_agreeing_variants
        else decision.routing_reason
    )
    if reason != decision.routing_reason:
        from dataclasses import replace

        decision = replace(
            decision,
            final_grade=None,
            review_status="needs_review",
            grading_confidence=0,
            routing_reason=reason,
        )
    outcome = (
        "PROCESSING_FAILED"
        if failures
        else "AUTO_CORRECT"
        if decision.final_grade == "correct"
        else "AUTO_INCORRECT"
        if decision.final_grade == "incorrect"
        else "NEEDS_REVIEW"
    )
    evidence = {
        "outcome": outcome,
        "variant_agreement": agreement,
        "quality_usable": quality_usable,
        "alignment_verified": alignment_verified,
        "alignment_confidence": alignment_confidence,
        "alignment_minimum": alignment_minimum,
        "correct_threshold": correct_threshold,
        "incorrect_threshold": incorrect_threshold,
        "confidence_calibrated": False,
        "strategy": "experimental_unscored_variant_agreement_v1"
        if experimental
        else "minimum_vendor_score_with_evidence_gates_v1",
        "experimental_auto_grade": experimental,
        "agreement_rule_score": agreement_rule_score if unscored else None,
        "required_agreeing_variants": min_agreeing_variants if experimental else None,
    }
    return decision, evidence
