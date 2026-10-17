from uuid import UUID, uuid4

from PIL import Image
from sqlalchemy import select

from app.models import CorrectionPageSlot, CorrectionRound, QuestionSubmission, WorksheetSubmission
from app.services.ingestion import png_bytes
from app.services.ocr import OCRResult
from app.tests.test_api import SAMPLES, setup
from app.tests.test_booklets import create, page


def initial(api, count=1, synthetic=True):
    ids = setup(api)
    booklet = create(api, ids, count=count, synthetic=synthetic)
    captures = []
    for number in range(1, count + 1):
        capture = page(api, booklet, ids["template_id"], number).json()
        assert api.post(f"/submissions/{capture['id']}/process").status_code == 200
        captures.append(capture)
    for answer in api.get(f"/review-queue?booklet_id={booklet['id']}").json():
        grade = (
            "incorrect"
            if answer["question_number"] in {3, 12, 20} and answer["page_number"] == 1
            else "correct"
        )
        assert (
            api.post(
                f"/question-submissions/{answer['id']}/review", json={"grade": grade, "review_seconds": 1}
            ).status_code
            == 200
        )
    return booklet, captures


def start(api, booklet):
    response = api.post(f"/booklets/{booklet['id']}/correction-rounds")
    assert response.status_code == 201, response.text
    return response.json()


def capture(api, round_, source, content=None):
    return api.post(
        f"/correction-rounds/{round_['id']}/pages/{source['id']}",
        files={"file": ("correction.png", content or (SAMPLES / "completed.png").read_bytes(), "image/png")},
    )


class SequenceOCR:
    name = "workflow_test"

    def __init__(self, values):
        self.values = iter(values)
        self.calls = 0

    def recognize_answer(self, image, expected_answer_type, optional_context=None):
        from app.services.normalization import normalize_answer

        self.calls += 1
        raw, confidence = next(self.values)
        return OCRResult(raw, confidence, normalized_candidate=normalize_answer(raw, expected_answer_type))


def test_two_rounds_only_unresolved_and_full_history(client, monkeypatch):
    from app.services import pipeline

    api, _ = client
    booklet, originals = initial(api)
    before = api.get(f"/submissions/{originals[0]['id']}").json()
    state = api.get(f"/booklets/{booklet['id']}").json()
    assert state["status"] == "needs_correction"
    assert state["workflow"]["initial_accuracy"] == 85 and state["workflow"]["unresolved_count"] == 3
    r1 = start(api, booklet)
    assert r1["pages"][0]["question_numbers"] == [3, 12, 20]
    assert start(api, booklet)["id"] == r1["id"]
    assert api.post(f"/correction-rounds/{r1['id']}/finalize").status_code == 409
    scan = capture(api, r1, originals[0]).json()
    assert capture(api, r1, originals[0]).json()["id"] == scan["id"]
    provider = SequenceOCR([("42", 0.9999), ("8", 0.7), ("2", 0.9999)])
    monkeypatch.setattr(pipeline, "get_provider", lambda config: provider)
    processed = api.post(f"/submissions/{scan['id']}/process").json()
    assert provider.calls == 3 and [a["question_number"] for a in processed["answers"]] == [3, 12, 20]
    assert processed["answers"][0]["review_status"] == "auto_accepted"
    queue = api.get(f"/review-queue?correction_round_id={r1['id']}").json()
    assert {a["question_number"] for a in queue} == {12, 20}
    assert len(api.get(f"/review-queue?booklet_id={booklet['id']}").json()) == 2
    for answer in queue:
        api.post(
            f"/question-submissions/{answer['id']}/review",
            json={
                "grade": "correct" if answer["question_number"] == 12 else "incorrect",
                "review_seconds": 2,
            },
        )
    final = api.post(f"/correction-rounds/{r1['id']}/finalize").json()
    assert final["unresolved_before"] == 3 and final["unresolved_after"] == 1 and final["corrected"] == 2
    assert final["auto_graded"] == 1 and final["human_reviews"] == 2
    assert api.get(f"/booklets/{booklet['id']}").json()["status"] == "needs_correction"
    r2 = start(api, booklet)
    assert r2["round_number"] == 2 and r2["pages"][0]["question_numbers"] == [20]
    scan2 = capture(api, r2, originals[0]).json()
    provider = SequenceOCR([("1", 0.7)])
    api.post(f"/submissions/{scan2['id']}/process")
    assert provider.calls == 1
    answer = api.get(f"/review-queue?correction_round_id={r2['id']}").json()[0]
    api.post(f"/question-submissions/{answer['id']}/review", json={"grade": "correct", "review_seconds": 1})
    # Processing/review alone cannot finish an open correction round.
    assert api.get(f"/booklets/{booklet['id']}").json()["status"] == "correction_in_progress"
    assert api.post(f"/correction-rounds/{r2['id']}/finalize").status_code == 200
    result = api.get(f"/booklets/{booklet['id']}").json()
    assert result["status"] == "completed" and result["score_percent"] == 100
    assert result["workflow"]["total_correction_attempts"] == 4
    assert result["workflow"]["completed_at"] and result["workflow"]["time_to_completion_seconds"] >= 0
    history = api.get(f"/booklets/{booklet['id']}/question-history").json()
    by_number = {h["question_number"]: h for h in history}
    assert [a["final_grade"] for a in by_number[20]["attempts"]] == ["incorrect", "incorrect", "correct"]
    assert all(len(h["attempts"]) == 1 for h in history if h["question_number"] not in {3, 12, 20})
    assert api.get(f"/submissions/{originals[0]['id']}").json()["answers"] == before["answers"]
    assert api.post(f"/booklets/{booklet['id']}/correction-rounds").status_code == 409
    assert api.post(f"/submissions/{scan['id']}/process").status_code == 409
    assert capture(api, r1, originals[0]).status_code == 409


def test_invalid_round_capture_and_superseded_retakes(client):
    api, factory = client
    ids = setup(api)
    booklet = create(api, ids, count=1)
    assert api.post(f"/booklets/{booklet['id']}/correction-rounds").status_code == 409
    booklet, originals = initial(api)
    round_ = start(api, booklet)
    assert capture(api, round_, {"id": str(uuid4())}).status_code == 404
    _other, other_pages = initial(api)
    assert capture(api, round_, other_pages[0]).status_code == 422
    dark = png_bytes(Image.new("RGB", (600, 800), "black"))
    failed = capture(api, round_, originals[0], dark).json()
    assert api.post(f"/submissions/{failed['id']}/process").json()["status"] == "failed"
    retake = capture(api, round_, originals[0]).json()
    assert retake["id"] != failed["id"]
    assert api.post(f"/submissions/{failed['id']}/process").status_code == 409
    assert api.get(f"/submissions/{failed['id']}").json()["status"] == "failed"
    api.post(f"/submissions/{retake['id']}/process")
    assert capture(api, round_, originals[0], dark).status_code == 409
    with factory() as db:
        assert (
            len(
                db.scalars(
                    select(WorksheetSubmission).where(
                        WorksheetSubmission.correction_round_id == UUID(round_["id"])
                    )
                ).all()
            )
            == 2
        )
        assert (
            len(
                db.scalars(
                    select(CorrectionRound).where(CorrectionRound.booklet_id == UUID(booklet["id"]))
                ).all()
            )
            == 1
        )


def test_only_pages_with_unresolved_answers_are_requested(client):
    api, _ = client
    booklet, pages = initial(api, count=2, synthetic=False)
    round_ = start(api, booklet)
    assert len(round_["pages"]) == 1
    assert round_["pages"][0]["source_submission_id"] == pages[0]["id"]
    assert capture(api, round_, pages[1]).status_code == 422


def test_correction_pages_follow_booklet_order_not_slot_insertion_order(client):
    api, factory = client
    booklet, pages = initial(api, count=2, synthetic=False)
    with factory() as db:
        answer = db.scalar(
            select(QuestionSubmission).where(
                QuestionSubmission.worksheet_submission_id == UUID(pages[1]["id"])
            )
        )
        answer.final_grade = "incorrect"
        db.commit()
    round_ = start(api, booklet)
    with factory() as db:
        slots = db.scalars(
            select(CorrectionPageSlot).where(
                CorrectionPageSlot.correction_round_id == UUID(round_["id"])
            )
        ).all()
        for slot in slots:
            db.delete(slot)
        db.flush()
        # Deliberately store page 2 before page 1, independent of random UUIDs.
        for source in reversed(pages):
            db.add(
                CorrectionPageSlot(
                    correction_round_id=UUID(round_["id"]),
                    source_submission_id=UUID(source["id"]),
                )
            )
            db.flush()
        db.commit()
    for url in [
        f"/correction-rounds/{round_['id']}",
        f"/booklets/{booklet['id']}/corrections",
    ]:
        result = api.get(url).json()
        ordered = result["pages"] if "pages" in result else result["rounds"][0]["pages"]
        assert [slot["page_number"] for slot in ordered] == [1, 2]
        assert [slot["source_submission_id"] for slot in ordered] == [p["id"] for p in pages]


def test_standalone_assignment_attachment_is_idempotent(client):
    from app.tests.test_api import upload

    api, _ = client
    ids = setup(api)
    submission = upload(api, ids)
    response = api.post(f"/submissions/{submission['id']}/assignment")
    assert response.status_code == 200
    assert api.post(f"/submissions/{submission['id']}/assignment").json() == response.json()
    assert api.get(f"/submissions/{submission['id']}").json()["booklet_id"] == response.json()["booklet_id"]


def test_round_target_snapshot_cannot_include_correct_answers_or_another_org(client):
    from sqlalchemy.exc import IntegrityError

    from app.models import Booklet, Organization

    api, factory = client
    booklet, _ = initial(api)
    round_ = start(api, booklet)
    with factory() as db:
        # Database enforces one active round even if a caller bypasses the API guard.
        db.add(
            CorrectionRound(
                organization_id=UUID("00000000-0000-4000-8000-000000000001"),
                booklet_id=UUID(booklet["id"]),
                round_number=2,
                unresolved_before=3,
            )
        )
        import pytest

        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        org = Organization(name="Other organization")
        db.add(org)
        db.flush()
        other = Booklet(organization_id=org.id, student_id=UUID(booklet["student_id"]), page_count=1)
        db.add(other)
        db.flush()
        foreign_round = CorrectionRound(
            organization_id=org.id, booklet_id=other.id, round_number=1, unresolved_before=1
        )
        db.add(foreign_round)
        db.commit()
        foreign_id = foreign_round.id
    assert api.get(f"/correction-rounds/{foreign_id}").status_code == 404
    assert api.post(f"/correction-rounds/{foreign_id}/finalize").status_code == 404
    assert api.get(f"/review-queue?correction_round_id={foreign_id}").status_code == 404
    assert (
        api.get(f"/review-queue?correction_round_id={round_['id']}&booklet_id={other.id}").status_code == 404
    )


def test_initial_all_correct_is_complete_and_cannot_be_corrected(client):
    api, _ = client
    ids = setup(api)
    booklet = create(api, ids, count=1, synthetic=False)
    submission = page(api, booklet, ids["template_id"], 1).json()
    api.post(f"/submissions/{submission['id']}/process")
    for answer in api.get(f"/review-queue?booklet_id={booklet['id']}").json():
        api.post(f"/question-submissions/{answer['id']}/review", json={"grade": "correct"})
    result = api.get(f"/booklets/{booklet['id']}").json()
    assert result["status"] == "completed" and result["workflow"]["unresolved_count"] == 0
    assert api.post(f"/booklets/{booklet['id']}/correction-rounds").status_code == 409
    assert all(len(q["attempts"]) == 1 for q in api.get(f"/booklets/{booklet['id']}/question-history").json())
