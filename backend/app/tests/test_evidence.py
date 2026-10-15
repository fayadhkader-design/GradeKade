from PIL import Image, ImageDraw

from app.services.cropping import prepare_variants
from app.services.grading import grade_evidence
from app.services.ocr import OCRResult
from app.services.quality import assess_photo


def result(value="42", confidence=0.999, **kw):
    return OCRResult(value, confidence, normalized_candidate=value, **kw)


def test_variant_disagreement_and_missing_score_abstain():
    d, _ = grade_evidence([result(), result("47")], "42", "integer")
    assert d.final_grade is None and d.routing_reason == "variant_disagreement"
    d, _ = grade_evidence([result(confidence=None)], "42", "integer")
    assert d.final_grade is None


def test_no_confidence_inflation_and_separate_reject_threshold():
    d, _ = grade_evidence([result(confidence=0.998)] * 3, "42", "integer")
    assert d.grading_confidence == 0.998 and d.final_grade == "correct"
    d, _ = grade_evidence([result("47", 0.998)], "42", "integer")
    assert d.final_grade is None


def test_failure_and_bad_alignment_never_automatic():
    d, e = grade_evidence([result(error="unavailable")], "42", "integer")
    assert e["outcome"] == "PROCESSING_FAILED" and d.final_grade is None
    d, _ = grade_evidence([result()], "42", "integer", alignment_confidence=0.7)
    assert d.final_grade is None
    d, _ = grade_evidence([result(provider_metadata={"line_count": 2})], "42", "integer")
    assert d.routing_reason == "ambiguous_ocr"


def test_severe_quality_gates_and_padding():
    assert not assess_photo(Image.new("RGB", (600, 800), "black"))["usable"]
    assert not assess_photo(Image.new("RGB", (600, 800), "white"))["usable"]
    image = Image.new("RGB", (600, 800), "white")
    for y in range(20, 750, 30):
        ImageDraw.Draw(image).text((20, y), "Arithmetic 42 " * 8, fill="black")
    assert assess_photo(image)["usable"]
    variants = prepare_variants(image, 0, 0, 0.1, 0.1, 6)
    assert variants["color"].size == (66, 86)
    assert variants["grayscale"].mode == "L"


def test_blank_and_invalid_single_result_keep_specific_diagnostics():
    d, _ = grade_evidence([result()], "42", "integer", blank=True)
    assert d.final_grade is None and d.routing_reason == "blank_crop"
    d, _ = grade_evidence([OCRResult("42 or 47", 0.999)], "42", "integer")
    assert d.final_grade is None and d.routing_reason == "invalid_answer"
