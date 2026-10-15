import pytest

from app.services.grading import grade_answer
from app.services.normalization import answers_equivalent, normalize_answer


@pytest.mark.parametrize(
    "raw,kind,want",
    [
        ("042", "integer", "42"),
        ("42.0", "integer", "42"),
        ("1 / 2", "fraction", "1/2"),
        ("2/4", "fraction", "1/2"),
        (".5", "decimal", "0.5"),
        ("- 3", "integer", "-3"),
        ("−3", "integer", "-3"),
        ("-0.000", "decimal", "0"),
        ("0.1250", "decimal", "0.125"),
        (r"\frac{2}{4}", "fraction", "1/2"),
        ("$3$", "integer", "3"),
    ],
)
def test_normalize(raw, kind, want):
    assert normalize_answer(raw, kind) == want


@pytest.mark.parametrize(
    "raw", ["1 2", "1/0", "", "__import__('os')", "2+2", "1e3", "NaN", "Infinity", "3?", "1,000"]
)
def test_reject_ambiguous_or_unsafe(raw):
    with pytest.raises(ValueError):
        normalize_answer(raw, "fraction")


def test_exact_equivalence():
    assert answers_equivalent("2/4", ".5", "fraction")
    assert not answers_equivalent(".50000000000000001", ".5", "decimal")
    assert not answers_equivalent("1.2", "1", "integer")


def test_threshold_and_predictions():
    assert grade_answer("8", "8", "integer", 0.995).final_grade == "correct"
    assert grade_answer("9", "8", "integer", 1).final_grade == "incorrect"
    decision = grade_answer("8", "8", "integer", 0.9949)
    assert decision.system_grade == "correct" and decision.final_grade is None
    assert decision.review_status == "needs_review"


@pytest.mark.parametrize(
    "options", [{"alignment_verified": False}, {"auto_grade_enabled": False}, {"blank": True}]
)
def test_safety_gates(options):
    assert grade_answer("8", "8", "integer", 1, **options).final_grade is None


@pytest.mark.parametrize("confidence", [float("nan"), float("inf"), -1, 1.1])
def test_invalid_confidence(confidence):
    assert grade_answer("8", "8", "integer", confidence).final_grade is None


def test_unparseable_is_uncertain():
    assert grade_answer("8?", "8", "integer", 1).system_grade == "uncertain"


@pytest.mark.parametrize(
    "raw,kind,want",
    [
        ("７２", "integer", "72"),
        ("72.\n", "integer", "72"),
        ("½", "fraction", "1/2"),
        ("−½", "fraction", "-1/2"),
        ("⅜", "fraction", "3/8"),
        ("０．５０", "decimal", "0.5"),
    ],
)
def test_handwriting_unicode_and_harmless_ocr_formatting(raw, kind, want):
    assert normalize_answer(raw, kind) == want


@pytest.mark.parametrize("raw", ["1½", "42\n47", "42 or 47", "1 1/2", "42=42"])
def test_never_choose_between_multiple_answers(raw):
    with pytest.raises(ValueError):
        normalize_answer(raw, "fraction")
