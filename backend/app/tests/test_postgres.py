"""Optional live PostgreSQL workflow; CI provides a disposable database service."""

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.api import routes
from app.db import Base, get_db
from app.main import app
from app.services.storage import LocalStorage


@pytest.mark.skipif(
    not os.getenv("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL not set; live PostgreSQL unavailable"
)
def test_live_postgres_grading_and_review(tmp_path, monkeypatch):
    engine = create_engine(os.environ["TEST_POSTGRES_URL"])
    schema = "test_" + uuid4().hex
    with engine.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {schema}"))
    scoped = engine.execution_options(schema_translate_map={None: schema})
    try:
        Base.metadata.create_all(scoped)
        factory = sessionmaker(scoped, expire_on_commit=False)
        with factory() as db:
            routes.ensure_demo_identity(db)

        def override():
            with factory() as db:
                yield db

        app.dependency_overrides[get_db] = override
        monkeypatch.setattr(routes, "storage", LocalStorage(tmp_path))
        api = TestClient(app)
        ids = api.post("/demo/setup").json()
        response = api.post(
            "/submissions",
            data={
                "student_id": ids["student_id"],
                "worksheet_template_id": ids["template_id"],
                "synthetic_demo": "true",
            },
            files={"file": ("completed.png", (routes.SAMPLES / "completed.png").read_bytes(), "image/png")},
        )
        assert response.status_code == 201, response.text
        submission_id = response.json()["id"]
        response = api.post(f"/submissions/{submission_id}/process")
        assert response.status_code == 200, response.text
        assert response.json()["waiting"] == 5
        for answer in api.get("/review-queue").json():
            grade = "incorrect" if answer["question_number"] in {12, 20} else "correct"
            assert (
                api.post(f"/question-submissions/{answer['id']}/review", json={"grade": grade}).status_code
                == 200
            )
        result = api.get(f"/submissions/{submission_id}").json()
        assert result["status"] == "completed" and result["score_percent"] == 85
    finally:
        app.dependency_overrides.clear()
        with engine.begin() as connection:
            connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        engine.dispose()
