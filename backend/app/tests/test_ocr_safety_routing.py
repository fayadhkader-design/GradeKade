import pytest

from app.services import pipeline
from app.services.ocr import OCRResult
from app.tests.test_api import setup, upload


@pytest.mark.parametrize(
    "raw,candidate,reason",
    [("$42", None, "invalid_answer"), ("47", "42", "invalid_ocr_candidate")],
)
def test_unsafe_ocr_enters_review_and_keeps_original_evidence(client, monkeypatch, raw, candidate, reason):
    class InconsistentProvider:
        name = "safety_test"

        def recognize_answer(self, image, expected_answer_type, optional_context=None):
            return OCRResult(raw, 0.998, normalized_candidate=candidate)

    api, _ = client
    ids = setup(api)
    submission = upload(api, ids, synthetic=False)
    monkeypatch.setattr(pipeline, "get_provider", lambda config: InconsistentProvider())
    response = api.post(f"/submissions/{submission['id']}/process")
    assert response.status_code == 200, response.text
    result = response.json()
    answer = next(a for a in result["answers"] if a["question_number"] == 3)
    assert answer["expected_answer"] == "42"
    assert answer["raw_ocr_text"] == raw
    assert answer["routing_reason"] == reason
    assert answer["final_grade"] is None
    assert answer["decision"] == "NEEDS_REVIEW"
    assert answer["evidence"]["variants"]["color"]["normalized_candidate"] == candidate
    assert answer["id"] in {a["id"] for a in api.get("/review-queue").json()}
    assert (
        api.post(f"/question-submissions/{answer['id']}/review", json={"grade": "incorrect"}).status_code
        == 200
    )
    reviewed = next(
        a for a in api.get(f"/submissions/{submission['id']}").json()["answers"] if a["id"] == answer["id"]
    )
    assert reviewed["final_grade"] == "incorrect" and reviewed["review_status"] == "human_reviewed"
    for key in ["raw_ocr_text", "system_grade", "evidence", "routing_reason"]:
        assert reviewed[key] == answer[key]
