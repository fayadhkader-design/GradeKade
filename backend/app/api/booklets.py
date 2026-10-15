"""Ordered page batches. Each page uses its client UUID as an idempotency key."""

import json
from datetime import UTC
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api import routes
from app.api.routes import DB, owned, read_page, submission_json
from app.config import settings
from app.models import (
    Booklet,
    QuestionSubmission,
    QuestionTemplate,
    Student,
    WorksheetSubmission,
    WorksheetTemplate,
)
from app.schemas import BaselineCreate, BookletCreate
from app.services.ingestion import image_digest, png_bytes
from app.services.pipeline import SAMPLES

router = APIRouter()


def booklet_json(db, booklet):
    pages = db.scalars(
        select(WorksheetSubmission)
        .where(WorksheetSubmission.booklet_id == booklet.id)
        .order_by(WorksheetSubmission.page_number)
    ).all()
    answers = db.scalars(
        select(QuestionSubmission)
        .join(WorksheetSubmission)
        .where(WorksheetSubmission.booklet_id == booklet.id)
    ).all()
    complete = len(pages) == booklet.page_count and all(p.status == "completed" for p in pages)

    def utc(value):
        return value if value.tzinfo else value.replace(tzinfo=UTC)

    end_to_end = (
        booklet.capture_seconds
        + (max(utc(p.finalized_at) for p in pages) - utc(booklet.created_at)).total_seconds()
        if complete
        else None
    )
    auto = sum(a.review_status == "auto_accepted" for a in answers)
    waiting = sum(a.review_status == "needs_review" for a in answers)
    processed = sum(p.status in {"needs_review", "completed"} for p in pages)
    human = [a for a in answers if a.review_status == "human_reviewed"]
    measured = [a.review_seconds for a in human if a.review_seconds is not None]
    review_seconds = sum(measured)
    observed = booklet.capture_seconds + review_seconds
    # Only compare when every human decision has a timer and the booklet is finished.
    comparable = complete and len(measured) == len(human) and booklet.manual_baseline_seconds is not None
    return {
        "id": str(booklet.id),
        "student_id": str(booklet.student_id),
        "student_name": db.get(Student, booklet.student_id).first_name,
        "page_count": booklet.page_count,
        "uploaded_pages": len(pages),
        "processed_pages": processed,
        "status": "completed"
        if complete
        else "needs_review"
        if processed == booklet.page_count
        else "in_progress",
        "answers_total": len(answers),
        "auto_graded": auto,
        "waiting": waiting,
        "correct": sum(a.final_grade == "correct" for a in answers),
        "score_percent": round(100 * sum(a.final_grade == "correct" for a in answers) / len(answers), 1)
        if complete and answers
        else None,
        "synthetic_demo": booklet.synthetic_demo,
        "created_at": booklet.created_at,
        "pages": [submission_json(db, p, False) for p in pages],
        "timing": {
            "end_to_end_seconds": end_to_end,
            "capture_seconds": booklet.capture_seconds,
            "processing_seconds": sum(p.processing_seconds or 0 for p in pages),
            "review_seconds": review_seconds,
            "timed_reviews": len(measured),
            "human_reviews": len(human),
            "mean_review_seconds": review_seconds / len(measured) if measured else None,
            "observed_capture_and_review_seconds": observed,
            "manual_baseline_seconds": booklet.manual_baseline_seconds,
            "difference_seconds": booklet.manual_baseline_seconds - observed if comparable else None,
            "comparable": comparable,
        },
    }


@router.post("/booklets", status_code=201)
def create_booklet(payload: BookletCreate, db: DB):
    owned(db, Student, payload.student_id)
    existing = db.get(Booklet, payload.id)
    if existing:
        owned(db, Booklet, payload.id)
        if (existing.student_id, existing.page_count, existing.synthetic_demo) != (
            payload.student_id,
            payload.page_count,
            payload.synthetic_demo,
        ):
            raise HTTPException(409, "This booklet ID already has different settings")
        return booklet_json(db, existing)
    booklet = Booklet(organization_id=settings.organization_id, **payload.model_dump())
    db.add(booklet)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return create_booklet(payload, db)
    return booklet_json(db, booklet)


@router.get("/booklets")
def list_booklets(db: DB):
    return [
        booklet_json(db, b)
        for b in db.scalars(
            select(Booklet)
            .where(Booklet.organization_id == settings.organization_id)
            .order_by(Booklet.created_at.desc())
            .limit(50)
        )
    ]


@router.get("/booklets/{booklet_id}")
def get_booklet(booklet_id: UUID, db: DB):
    return booklet_json(db, owned(db, Booklet, booklet_id))


@router.post("/booklets/{booklet_id}/baseline")
def baseline(booklet_id: UUID, payload: BaselineCreate, db: DB):
    booklet = owned(db, Booklet, booklet_id)
    booklet.manual_baseline_seconds = payload.seconds
    db.commit()
    return booklet_json(db, booklet)


@router.post("/booklets/{booklet_id}/pages/{page_id}", status_code=201)
async def upload_page(
    booklet_id: UUID,
    page_id: UUID,
    db: DB,
    template_id: Annotated[UUID, Form()],
    page_number: Annotated[int, Form(ge=1, le=30)],
    file: Annotated[UploadFile, File()],
):
    booklet = owned(db, Booklet, booklet_id)
    if page_number > booklet.page_count:
        raise HTTPException(422, "Page number exceeds the booklet size")
    template = owned(db, WorksheetTemplate, template_id)
    if not db.scalar(
        select(QuestionTemplate.id).where(QuestionTemplate.worksheet_template_id == template.id).limit(1)
    ):
        raise HTTPException(422, "Configure answer boxes before scanning this worksheet")
    image = await read_page(file)
    content = png_bytes(image)
    if booklet.synthetic_demo:
        manifest = json.loads((SAMPLES / "manifest.json").read_text())
        if (
            image_digest(content) != manifest["submission_sha256"]
            or image_digest(routes.storage.read(template.template_image_path)) != manifest["template_sha256"]
        ):
            raise HTTPException(
                422,
                "Synthetic OCR only accepts the original supplied sample pages. Turn it off for camera captures.",
            )

    def existing_page():
        existing = db.get(WorksheetSubmission, page_id)
        if existing:
            owned(db, WorksheetSubmission, page_id)
            if (existing.booklet_id, existing.page_number, existing.worksheet_template_id) != (
                booklet_id,
                page_number,
                template_id,
            ) or image_digest(routes.storage.read(existing.uploaded_file_path)) != image_digest(content):
                raise HTTPException(409, "This page ID already contains a different capture")
        return existing

    existing = existing_page()
    if existing:
        return submission_json(db, existing)
    # Serialize slots and template use against concurrent page/key changes on PostgreSQL.
    db.scalar(select(Booklet).where(Booklet.id == booklet_id).with_for_update())
    db.scalar(select(WorksheetTemplate).where(WorksheetTemplate.id == template_id).with_for_update())
    if db.scalar(
        select(WorksheetSubmission.id).where(
            WorksheetSubmission.booklet_id == booklet_id, WorksheetSubmission.page_number == page_number
        )
    ):
        raise HTTPException(409, "That page position is already occupied")
    page = WorksheetSubmission(
        id=page_id,
        organization_id=settings.organization_id,
        student_id=booklet.student_id,
        worksheet_template_id=template_id,
        uploaded_file_path=routes.storage.save(content),
        booklet_id=booklet_id,
        page_number=page_number,
        fixture_id="arithmetic-a" if booklet.synthetic_demo else None,
    )
    db.add(page)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = existing_page()
        if existing:
            return submission_json(db, existing)
        raise HTTPException(409, "Page position already occupied; refresh the booklet") from None
    return submission_json(db, page)
