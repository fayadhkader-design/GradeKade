import json
from io import BytesIO
from zipfile import ZipFile
from PIL import Image
from app.tests.test_api import setup, upload
from app.services.ingestion import png_bytes


def test_truth_export_preserves_ai_and_rejects_fixture_as_real(client):
    api, _ = client
    ids = setup(api)
    submission = upload(api, ids)
    result = api.post(f"/submissions/{submission['id']}/process").json()
    answer = result["answers"][0]
    truth = {
        "actual_answer": answer["expected_answer"],
        "transcription_status": "readable",
        "verified_grade": "correct",
        "source": "real_handwriting",
        "annotation_seconds": 1.5,
    }
    url = f"/question-submissions/{answer['id']}/ground-truth"
    assert api.post(url, json=truth).status_code == 422
    truth["source"] = "synthetic"
    assert api.post(url, json=truth).status_code == 200
    after = api.get(f"/submissions/{submission['id']}").json()["answers"][0]
    for key in ("raw_ocr_text", "system_grade", "grading_confidence", "final_grade"):
        assert answer[key] == after[key]
    data = api.get("/evaluation?source=synthetic").json()
    assert data["report"]["verified_answers"] == 1
    assert data["report"]["unverified_automated_answers"] == 14
    assert api.get(after["variant_urls"]["color"]).status_code == 200
    assert api.get(f"/question-submissions/{answer['id']}/variant/unknown").status_code == 404
    zipped = api.get("/evaluation/export?source=synthetic")
    with ZipFile(BytesIO(zipped.content)) as archive:
        records = json.loads(archive.read("records.json"))
        assert len(records) == 20
        assert "student_name" not in records[0]
        assert "crop_image_path" not in str(records)
        assert records[0]["image_file"] in archive.namelist()
    assert api.get("/evaluation?limit=1000").status_code == 422


def test_unusable_page_requests_retake_without_ocr(client, monkeypatch):
    from app.services import pipeline

    api, _ = client
    ids = setup(api)
    response = api.post(
        "/submissions",
        data={"student_id": ids["student_id"], "worksheet_template_id": ids["template_id"]},
        files={"file": ("dark.png", png_bytes(Image.new("RGB", (600, 800), "black")))},
    )

    def forbidden(*args):
        raise AssertionError("Poor photo must not call OCR")

    monkeypatch.setattr(pipeline, "get_provider", forbidden)
    response = api.post(f"/submissions/{response.json()['id']}/process")
    assert response.status_code == 200
    page = response.json()
    assert page["status"] == "failed"
    assert page["processing"]["retake_required"] is True
    assert "Retake this page" in page["error"]
    assert page["answers"] == []
    assert len(api.get("/evaluation/page-failures").json()) == 1
