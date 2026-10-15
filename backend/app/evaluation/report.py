"""Reports immutable decisions against independently verified truth.

Unlabeled answers contribute to coverage, never accuracy denominators.
"""

from collections import defaultdict
from math import sqrt
from app.services.normalization import normalize_answer


def ratio(a, b):
    return a / b if b else None


def wilson(successes, n):
    if not n:
        return None
    z = 1.95996398454
    p = successes / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return [max(0, center - half), min(1, center + half)]


def same(raw, actual, kind):
    if not raw.strip() or not actual.strip():
        return not raw.strip() and not actual.strip()
    try:
        return normalize_answer(raw, kind) == normalize_answer(actual, kind)
    except ValueError:
        return False


def summarize(rows):
    total = len(rows)
    auto = [r for r in rows if r.get("automated")]
    labeled = [r for r in rows if r.get("verified_grade") in {"correct", "incorrect"}]
    verified_auto = [r for r in auto if r.get("verified_grade") in {"correct", "incorrect"}]
    readable = [r for r in labeled if r.get("transcription_status") in {"readable", "blank"}]
    predictions = [r for r in labeled if r.get("system_grade") in {"correct", "incorrect"}]
    correct_auto = sum(r["system_grade"] == r["verified_grade"] for r in verified_auto)
    raw_matches = sum(r.get("raw_ocr_text", "") == (r.get("student_actual_answer") or "") for r in readable)
    normalized_matches = sum(
        same(r.get("raw_ocr_text", ""), r.get("student_actual_answer") or "", r["answer_type"])
        for r in readable
    )
    alignment = [r for r in rows if r.get("alignment_verified") is not None]
    timed = [r["review_seconds"] for r in labeled if r.get("review_seconds") is not None]
    return {
        "total_answers": total,
        "verified_answers": len(labeled),
        "transcribed_answers": len(readable),
        "automated_answers": len(auto),
        "verified_automated_answers": len(verified_auto),
        "unverified_automated_answers": len(auto) - len(verified_auto),
        "ocr_exact_match_accuracy": ratio(raw_matches, len(readable)),
        "normalized_ocr_accuracy": ratio(normalized_matches, len(readable)),
        "grade_decision_accuracy": ratio(
            sum(r["system_grade"] == r["verified_grade"] for r in predictions), len(predictions)
        ),
        "grade_decision_denominator": len(predictions),
        "auto_grade_precision": ratio(correct_auto, len(verified_auto)),
        "auto_grade_precision_95ci": wilson(correct_auto, len(verified_auto)),
        "auto_grade_coverage": ratio(len(auto), total),
        "human_review_rate": ratio(total - len(auto), total),
        "false_auto_correct_count": sum(
            r["system_grade"] == "correct" and r["verified_grade"] == "incorrect" for r in verified_auto
        ),
        "false_auto_incorrect_count": sum(
            r["system_grade"] == "incorrect" and r["verified_grade"] == "correct" for r in verified_auto
        ),
        "ocr_failure_rate": ratio(sum(bool(r.get("ocr_error")) for r in rows), total),
        "alignment_failure_rate": ratio(sum(not r["alignment_verified"] for r in alignment), len(alignment)),
        "alignment_denominator": len(alignment),
        "average_human_review_seconds": ratio(sum(timed), len(timed)),
        "timed_verified_answers": len(timed),
    }


def report(rows):
    by_type = defaultdict(list)
    by_confidence = defaultdict(list)
    cohorts = defaultdict(list)
    for row in rows:
        by_type[row["answer_type"]].append(row)
        value = row.get("grading_confidence") or 0
        bucket = (
            ">=0.999"
            if value >= 0.999
            else "0.99–0.999"
            if value >= 0.99
            else "0.95–0.99"
            if value >= 0.95
            else "<0.95"
        )
        by_confidence[bucket].append(row)
        cohorts[f"{row.get('source', 'unknown')}/{row.get('ocr_provider', 'unknown')}"].append(row)
    return {
        **summarize(rows),
        "by_answer_type": {k: summarize(v) for k, v in by_type.items()},
        "by_confidence_bucket": {k: summarize(v) for k, v in by_confidence.items()},
        "cohorts": {k: summarize(v) for k, v in cohorts.items()},
        "notes": [
            "Accuracy excludes missing human truth; coverage includes all answers.",
            "Grade decision accuracy excludes abstentions; see its denominator.",
            "Confidence is an uncalibrated rule score. Variants are correlated.",
            "Alignment rates count answer records with known alignment, not unique pages.",
            "No aggregate of mixed synthetic/mock/real cohorts establishes real OCR accuracy.",
        ],
    }
