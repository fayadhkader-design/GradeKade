from uuid import uuid4

from app.models import Booklet, Organization
from app.tests.test_api import SAMPLES, setup


def create(api, ids, count=2, synthetic=True):
    payload = {
        "id": str(uuid4()),
        "student_id": ids["student_id"],
        "page_count": count,
        "capture_seconds": 12.5,
        "synthetic_demo": synthetic,
    }
    result = api.post("/booklets", json=payload)
    assert result.status_code == 201, result.text
    return payload


def page(api, booklet, template, number, page_id=None, filename="completed.png"):
    return api.post(
        f"/booklets/{booklet['id']}/pages/{page_id or uuid4()}",
        data={"template_id": template, "page_number": number},
        files={"file": (filename, (SAMPLES / filename).read_bytes(), "image/png")},
    )


def test_order_retry_review_scope_and_observed_timing(client):
    api, _ = client
    ids = setup(api)
    booklet = create(api, ids)
    assert api.post("/booklets", json=booklet).json()["id"] == booklet["id"]
    # Capture/upload arrival may differ from page order.
    ids_by_page = {2: str(uuid4()), 1: str(uuid4())}
    for number, page_id in ids_by_page.items():
        response = page(api, booklet, ids["template_id"], number, page_id)
        assert response.status_code == 201, response.text
        assert page(api, booklet, ids["template_id"], number, page_id).json()["id"] == page_id
        assert api.post(f"/submissions/{page_id}/process").status_code == 200
    result = api.get(f"/booklets/{booklet['id']}").json()
    assert [p["page_number"] for p in result["pages"]] == [1, 2]
    assert result["answers_total"] == 40 and result["auto_graded"] == 30 and result["waiting"] == 10
    assert len(result["pages"]) == 2 and result["timing"]["capture_seconds"] == 12.5
    assert page(api, booklet, ids["template_id"], 1).status_code == 409
    other = create(api, ids, count=1)
    other_page = page(api, other, ids["template_id"], 1).json()
    api.post(f"/submissions/{other_page['id']}/process")
    queue = api.get(f"/review-queue?booklet_id={booklet['id']}").json()
    assert len(queue) == 10
    assert queue[0]["page_number"] == 1
    for answer in queue:
        grade = "incorrect" if answer["question_number"] in {12, 20} else "correct"
        response = api.post(
            f"/question-submissions/{answer['id']}/review", json={"grade": grade, "review_seconds": 1.5}
        )
        assert response.status_code == 200, response.text
    final = api.get(f"/booklets/{booklet['id']}").json()
    assert final["status"] == "needs_correction" and final["score_percent"] == 85
    assert final["timing"]["review_seconds"] == 15 and final["timing"]["mean_review_seconds"] == 1.5
    assert len(api.get(f"/review-queue?booklet_id={other['id']}").json()) == 5
    final = api.post(f"/booklets/{booklet['id']}/baseline", json={"seconds": 60}).json()
    assert final["timing"]["difference_seconds"] == 32.5 and final["timing"]["comparable"]


def test_validation_and_tenant_isolation(client):
    api, factory = client
    ids = setup(api)
    booklet = create(api, ids, count=1)
    assert page(api, booklet, ids["template_id"], 2).status_code == 422
    assert page(api, booklet, ids["template_id"], 1, filename="blank.png").status_code == 422
    assert api.post("/booklets", json={**booklet, "page_count": 2}).status_code == 409
    assert api.post("/booklets", json={**booklet, "page_count": 31}).status_code == 422
    assert api.post(f"/booklets/{booklet['id']}/baseline", json={"seconds": -1}).status_code == 422
    with factory() as db:
        org = Organization(name="Other center")
        db.add(org)
        db.flush()
        other = Booklet(
            organization_id=org.id,
            student_id=__import__("uuid").UUID(ids["student_id"]),
            page_count=1,
            capture_seconds=0,
        )
        db.add(other)
        db.commit()
        other_id = other.id
    assert api.get(f"/booklets/{other_id}").status_code == 404
    assert api.get(f"/review-queue?booklet_id={other_id}").status_code == 404
    assert str(other_id) not in str(api.get("/booklets").json())


def test_timer_missing_never_claims_savings(client):
    api, _ = client
    ids = setup(api)
    booklet = create(api, ids, count=1, synthetic=False)
    submission = page(api, booklet, ids["template_id"], 1).json()
    assert api.post(f"/submissions/{submission['id']}/process").status_code == 200
    for answer in api.get(f"/review-queue?booklet_id={booklet['id']}").json():
        assert (
            api.post(f"/question-submissions/{answer['id']}/review", json={"grade": "correct"}).status_code
            == 200
        )
    result = api.post(f"/booklets/{booklet['id']}/baseline", json={"seconds": 60}).json()
    assert not result["timing"]["comparable"] and result["timing"]["difference_seconds"] is None
