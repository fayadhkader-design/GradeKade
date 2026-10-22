import pytest

from app.services.grading import grade_answer
from app.services.normalization import answers_equivalent, normalize_answer


@pytest.mark.parametrize("raw", ["$42", "42$", "$$42$", "$42$$", r"\(42", r"42\)", r"\[42\)"])
def test_incomplete_or_mismatched_delimiters_require_review(raw):
    with pytest.raises(ValueError):
        normalize_answer(raw, "integer")
    assert not answers_equivalent(raw, "42", "integer")
    decision = grade_answer(raw, "42", "integer", 1)
    assert decision.system_grade == "uncertain"
    assert decision.final_grade is None
    assert decision.review_status == "needs_review"
    assert decision.routing_reason == "invalid_answer"


@pytest.mark.parametrize("kind,answer", [("integer", "42"), ("decimal", ".5"), ("fraction", "2/4")])
@pytest.mark.parametrize("opening,closing", [("$", "$"), ("$$", "$$"), (r"\(", r"\)"), (r"\[", r"\]")])
def test_one_balanced_math_wrapper_preserves_numeric_meaning(kind, answer, opening, closing):
    wrapped = f"{opening} {answer} {closing}"
    assert normalize_answer(wrapped, kind) == normalize_answer(answer, kind)


@pytest.mark.parametrize("raw", ["$1/2", "1/2$", "$1$ $2$", "$$$42$$$", "$2+2$", r"\(42\]", "$42 dollars$"])
def test_wrappers_never_turn_ambiguous_math_into_a_number(raw):
    with pytest.raises(ValueError):
        normalize_answer(raw, "fraction")
