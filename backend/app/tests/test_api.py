import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes
from app.db import Base, get_db
from app.main import app
from app.models import Organization, QuestionSubmission, Student
from app.services.storage import LocalStorage

SAMPLES = Path(__file__).resolve().parents[3] / "sample_data"


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(engine, expire_on_commit=False)
    with session_factory() as db:
        routes.ensure_demo_identity(db)

    def override():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override
    monkeypatch.setattr(routes, "storage", LocalStorage(tmp_path))
    # No lifespan: test database has its own identity, not the development database.
    yield TestClient(app), session_factory
    app.dependency_overrides.clear()
    engine.dispose()


def setup(client):
    response = client.post("/demo/setup")
    assert response.status_code == 200, response.text
    return response.json()


def upload(client, ids, synthetic=True, filename="completed.png"):
    response = client.post(
        "/submissions",
        data={
            "student_id": ids["student_id"],
            "worksheet_template_id": ids["template_id"],
            "synthetic_demo": str(synthetic).lower(),
        },
        files={"file": (filename, (SAMPLES / filename).read_bytes(), "image/png")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_end_to_end_synthetic_and_audit(client):
    api, factory = client
    ids = setup(api)
    submission = upload(api, ids)
    response = api.post(f"/submissions/{submission['id']}/process")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["alignment"]["verified"]
    assert result["status"] == "needs_review"
    assert result["total"] == 20 and result["waiting"] == 5
    assert result["processing"]["ocr_provider"] == "synthetic_fixture"
    assert result["score_percent"] is None
    assert (
        api.post(
            f"/templates/{ids['template_id']}/questions",
            json={"questions": json.loads((SAMPLES / "template.json").read_text())["questions"]},
        ).status_code
        == 409
    )
    assert api.post(f"/submissions/{submission['id']}/process").json()["total"] == 20
    queue = api.get("/review-queue").json()
    assert len(queue) == 5
    for answer in queue:
        assert api.get(answer["crop_url"].removeprefix("/api")).status_code == 200
        grade = "incorrect" if answer["question_number"] in {12, 20} else "correct"
        response = api.post(
            f"/question-submissions/{answer['id']}/review",
            json={"grade": grade, "recognized_answer": "2/4" if answer["question_number"] == 7 else None},
        )
        assert response.status_code == 200, response.text
    final = api.get(f"/submissions/{submission['id']}").json()
    assert final["status"] == "completed" and final["correct"] == 17 and final["score_percent"] == 85
    assert api.get("/review-queue").json() == []
    metrics = api.get("/metrics").json()
    assert metrics["auto_graded_percent"] == 75 and metrics["human_review_percent"] == 25
    assert metrics["waiting_for_review"] == 0
    assert (
        api.post(f"/question-submissions/{queue[0]['id']}/review", json={"grade": "incorrect"}).status_code
        == 409
    )
    with factory() as db:
        q = db.scalar(
            select(QuestionSubmission).where(QuestionSubmission.id == __import__("uuid").UUID(queue[1]["id"]))
        )
        assert q.raw_ocr_text == "1/4" and q.reviewed_answer == "2/4" and q.human_override


def test_arbitrary_mock_does_not_autograde(client):
    api, _ = client
    ids = setup(api)
    submission = upload(api, ids, synthetic=False)
    result = api.post(f"/submissions/{submission['id']}/process").json()
    assert result["waiting"] == 20
    assert all(q["raw_ocr_text"] == "" and q["final_grade"] is None for q in result["answers"])


def test_scope_validation_and_no_path_leaks(client):
    api, factory = client
    ids = setup(api)
    with factory() as db:
        org = Organization(name="Another center")
        db.add(org)
        db.flush()
        student = Student(organization_id=org.id, first_name="Other demo")
        db.add(student)
        db.commit()
        student_id = str(student.id)
    assert student_id not in str(api.get("/students").json())
    response = api.post(
        "/submissions",
        data={"student_id": student_id, "worksheet_template_id": ids["template_id"]},
        files={"file": ("a.png", (SAMPLES / "completed.png").read_bytes())},
    )
    assert response.status_code == 404
    assert api.get(f"/templates/{uuid4()}").status_code == 404
    assert (
        api.post("/templates", data={"name": "Bad"}, files={"file": ("a.png", b"not an image")}).status_code
        == 422
    )
    assert api.post("/students", json={"first_name": "   "}).status_code == 422
    assert "template_image_path" not in str(api.get("/templates").json())
    bad = json.loads((SAMPLES / "template.json").read_text())["questions"]
    bad[0]["width"] = 2
    assert api.post(f"/templates/{ids['template_id']}/questions", json={"questions": bad}).status_code == 422


def test_manual_template_pdf_and_student_workflow(client):
    api, _ = client
    student = api.post("/students", json={"first_name": "Demo learner"}).json()
    response = api.post(
        "/templates",
        data={"name": "Manual PDF"},
        files={"file": ("blank.pdf", (SAMPLES / "blank.pdf").read_bytes(), "application/pdf")},
    )
    assert response.status_code == 201, response.text
    template = response.json()
    questions = json.loads((SAMPLES / "template.json").read_text())["questions"][:10]
    assert (
        api.post(f"/templates/{template['id']}/questions", json={"questions": questions}).status_code == 200
    )
    response = api.post(
        "/submissions",
        data={"student_id": student["id"], "worksheet_template_id": template["id"]},
        files={"file": ("page.png", (SAMPLES / "completed.png").read_bytes())},
    )
    assert response.status_code == 201, response.text
    result = api.post(f"/submissions/{response.json()['id']}/process").json()
    assert result["total"] == 10 and result["waiting"] == 10


def test_spoofed_fixture_and_upload_limit(client):
    api, _ = client
    ids = setup(api)
    response = api.post(
        "/submissions",
        data={
            "student_id": ids["student_id"],
            "worksheet_template_id": ids["template_id"],
            "synthetic_demo": "true",
        },
        files={"file": ("blank.png", (SAMPLES / "blank.png").read_bytes())},
    )
    assert response.status_code == 422
    response = api.post(
        "/templates",
        data={"name": "Large"},
        files={"file": ("big.png", b"x" * (routes.settings.max_upload_bytes + 1))},
    )
    assert response.status_code == 413


def test_failed_processing_can_retry_without_duplicate_answers(client, monkeypatch):
    from app.services import pipeline

    api, _ = client
    ids = setup(api)
    submission = upload(api, ids)
    align = pipeline.align_submission_to_template

    def broken(*args):
        raise RuntimeError("private-internal-detail")

    monkeypatch.setattr(pipeline, "align_submission_to_template", broken)
    response = api.post(f"/submissions/{submission['id']}/process")
    assert response.status_code == 422 and "private-internal-detail" not in response.text
    assert api.get(f"/submissions/{submission['id']}").json()["status"] == "failed"
    monkeypatch.setattr(pipeline, "align_submission_to_template", align)
    result = api.post(f"/submissions/{submission['id']}/process").json()
    assert result["total"] == 20 and result["waiting"] == 5


def test_provider_failure_routes_to_review(client, monkeypatch):
    import httpx

    from app.services import pipeline

    class FailingProvider:
        name = "test_failure"

        def recognize(self, image):
            raise httpx.ReadTimeout("private-provider-detail")

    api, _ = client
    ids = setup(api)
    submission = upload(api, ids, synthetic=False)
    monkeypatch.setattr(pipeline, "get_provider", lambda config: FailingProvider())
    response = api.post(f"/submissions/{submission['id']}/process")
    assert response.status_code == 200
    result = response.json()
    assert result["waiting"] == 20 and "private-provider-detail" not in response.text
    assert all(a["routing_reason"] == "ocr_provider_error" for a in result["answers"])
