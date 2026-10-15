"""Local-only evaluation tools; organization scope applies to images and truth."""

import csv
import json
from io import BytesIO, StringIO
from typing import Literal
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from app.api import routes
from app.api.routes import DB, answer_json, owned_question
from app.config import settings
from app.evaluation.report import report
from app.models import EvaluationAnnotation, QuestionSubmission, QuestionTemplate, WorksheetSubmission, now
from app.services.normalization import answers_equivalent, normalize_answer

router = APIRouter()


class TruthCreate(BaseModel):
    actual_answer: str | None = Field(default=None, max_length=100)
    transcription_status: Literal["readable", "blank", "unreadable"]
    verified_grade: Literal["correct", "incorrect"]
    source: Literal["real_handwriting", "synthetic", "unknown"] = "unknown"
    annotation_seconds: float | None = Field(default=None, ge=0, le=3600)

    @model_validator(mode="after")
    def valid_truth(self):
        if self.transcription_status == "readable" and not (self.actual_answer or "").strip():
            raise ValueError("Transcribe the actual handwritten answer")
        if self.transcription_status == "blank":
            self.actual_answer = ""
        if self.transcription_status == "unreadable":
            self.actual_answer = None
        return self


def records(db):
    answers = db.scalars(
        select(QuestionSubmission)
        .join(WorksheetSubmission)
        .where(
            WorksheetSubmission.organization_id == settings.organization_id,
            WorksheetSubmission.status.in_(["needs_review", "completed"]),
        )
        .order_by(QuestionSubmission.created_at, QuestionSubmission.id)
    ).all()
    truths = {
        t.question_submission_id: t
        for t in db.scalars(
            select(EvaluationAnnotation)
            .join(QuestionSubmission, EvaluationAnnotation.question_submission_id == QuestionSubmission.id)
            .join(WorksheetSubmission)
            .where(WorksheetSubmission.organization_id == settings.organization_id)
        )
    }
    result = []
    for answer in answers:
        page = db.get(WorksheetSubmission, answer.worksheet_submission_id)
        question = db.get(QuestionTemplate, answer.question_template_id)
        truth = truths.get(answer.id)
        # Human grade alone is useful evaluation truth; transcription requires explicit annotation.
        verified = (
            truth.verified_grade
            if truth
            else answer.final_grade
            if answer.review_status == "human_reviewed"
            else None
        )
        evidence = answer.evidence or {}
        result.append(
            {
                "id": str(answer.id),
                "worksheet_id": str(page.id),
                "question_id": str(question.id),
                "question_number": question.question_number,
                "initial_question_submission_id": str(answer.initial_question_submission_id)
                if answer.initial_question_submission_id
                else None,
                "correction_round_id": str(page.correction_round_id) if page.correction_round_id else None,
                "source_submission_id": str(page.source_submission_id) if page.source_submission_id else None,
                "answer_type": question.answer_type,
                "expected_answer": answer.expected_answer,
                "student_actual_answer": truth.actual_answer if truth else None,
                "transcription_status": truth.transcription_status if truth else "unverified",
                "verified_grade": verified,
                "source": "synthetic"
                if page.fixture_id or (page.processing_metadata or {}).get("data_origin") == "synthetic"
                else truth.source
                if truth
                else "unknown",
                "raw_ocr_text": answer.raw_ocr_text,
                "normalized_answer": answer.normalized_answer,
                "ocr_confidence": evidence.get("provider_confidence", answer.ocr_confidence),
                "grading_confidence": answer.grading_confidence,
                "ocr_provider": answer.ocr_provider,
                "ocr_seconds": evidence.get("ocr_seconds"),
                "inference_seconds": evidence.get("inference_seconds"),
                "variants_run": evidence.get("variants_run"),
                "grading_strategy": evidence.get("strategy"),
                "system_grade": answer.system_grade,
                "automated": evidence.get("outcome", "").startswith("AUTO_")
                or answer.review_status == "auto_accepted",
                "decision": evidence.get("outcome"),
                "human_final_grade": answer.final_grade if answer.review_status == "human_reviewed" else None,
                "review_seconds": answer.review_seconds,
                "annotation_seconds": truth.annotation_seconds if truth else None,
                "ocr_error": any(v.get("error") for v in evidence.get("variants", {}).values()),
                "alignment_verified": (page.alignment_metadata or {}).get(
                    "accepted_for_cropping", (page.alignment_metadata or {}).get("verified")
                ),
                "alignment": page.alignment_metadata,
                "preprocessing_variants": evidence.get("selected_variants", []),
                "routing_reason": answer.routing_reason,
            }
        )
    return result


def page_records(db):
    pages = db.scalars(
        select(WorksheetSubmission).where(
            WorksheetSubmission.organization_id == settings.organization_id,
            WorksheetSubmission.status != "uploaded",
        )
    )
    return [
        {
            "worksheet_id": str(p.id),
            "status": p.status,
            "source": "synthetic"
            if p.fixture_id or (p.processing_metadata or {}).get("data_origin") == "synthetic"
            else "unknown",
            "alignment_verified": (p.alignment_metadata or {}).get(
                "accepted_for_cropping", (p.alignment_metadata or {}).get("verified")
            ),
            "photo_usable": (p.processing_metadata or {}).get("photo_quality", {}).get("usable"),
        }
        for p in pages
    ]


def scoped_pages(db, rows, source):
    pages = page_records(db)
    if source == "all":
        return pages
    if source == "synthetic":
        return [p for p in pages if p["source"] == "synthetic"]
    if source == "unknown":
        return [p for p in pages if p["source"] == "unknown"]
    ids = {r["worksheet_id"] for r in rows}
    return [p for p in pages if p["worksheet_id"] in ids]


@router.get("/evaluation")
def evaluation(
    db: DB,
    source: Literal["all", "real_handwriting", "synthetic", "unknown"] = "all",
    offset: int = 0,
    limit: int = 100,
):
    if offset < 0 or not 1 <= limit <= 200:
        raise HTTPException(422, "Invalid page")
    rows = records(db)
    if source != "all":
        rows = [r for r in rows if r["source"] == source]
    details = []
    for row in rows[offset : offset + limit]:
        answer, page = owned_question(db, UUID(row["id"]))
        details.append(
            {
                **row,
                **answer_json(db, answer),
                "automated_decision_correct": row["system_grade"] == row["verified_grade"]
                if row["automated"] and row["verified_grade"]
                else None,
                "original_url": f"/api/submissions/{page.id}/image/original",
                "aligned_url": f"/api/submissions/{page.id}/image/aligned"
                if page.aligned_file_path
                else None,
            }
        )
    return {
        "report": report(rows, scoped_pages(db, rows, source)),
        "items": details,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
    }


@router.post("/question-submissions/{answer_id}/ground-truth")
def verify(answer_id: UUID, payload: TruthCreate, db: DB):
    answer, page = owned_question(db, answer_id)
    if page.status not in {"completed", "needs_review"}:
        raise HTTPException(409, "Process the page first")
    if (
        page.fixture_id or (page.processing_metadata or {}).get("data_origin") == "synthetic"
    ) and payload.source != "synthetic":
        raise HTTPException(422, "Synthetic fixture answers cannot be labeled real handwriting")
    question = db.get(QuestionTemplate, answer.question_template_id)
    if payload.transcription_status == "readable":
        try:
            normalize_answer(payload.actual_answer, question.answer_type)
        except ValueError:
            raise HTTPException(422, "Use unreadable for ambiguous or unsupported answers") from None
        correct = answers_equivalent(payload.actual_answer, answer.expected_answer, question.answer_type)
        if correct != (payload.verified_grade == "correct"):
            raise HTTPException(422, "Verified grade conflicts with the transcription and answer key")
    if payload.transcription_status == "blank" and payload.verified_grade == "correct":
        raise HTTPException(422, "A blank arithmetic answer cannot be correct")
    truth = db.scalar(
        select(EvaluationAnnotation).where(EvaluationAnnotation.question_submission_id == answer_id)
    )
    if truth is None:
        truth = EvaluationAnnotation(question_submission_id=answer_id)
        db.add(truth)
    for key, value in payload.model_dump().items():
        setattr(truth, key, value)
    truth.verified_at = now()
    db.commit()
    return {"saved": True}


@router.get("/question-submissions/{answer_id}/variant/{variant}")
def variant_image(answer_id: UUID, variant: str, db: DB):
    answer, _ = owned_question(db, answer_id)
    key = (answer.evidence or {}).get("crop_variants", {}).get(variant)
    if not key:
        raise HTTPException(404, "Variant not available")
    return FileResponse(
        routes.storage.path(key), media_type="image/png", headers={"Cache-Control": "no-store"}
    )


@router.get("/evaluation/export")
def export(db: DB, source: Literal["all", "real_handwriting", "synthetic", "unknown"] = "real_handwriting"):
    rows = records(db)
    if source != "all":
        rows = [r for r in rows if r["source"] == source]
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for row in rows:
            answer, _ = owned_question(db, UUID(row["id"]))
            row["image_file"] = f"images/{answer.id}.png"
            archive.writestr(row["image_file"], routes.storage.read(answer.crop_image_path))
        archive.writestr("records.json", json.dumps(rows, indent=2))
        fields = [
            "id",
            "worksheet_id",
            "question_id",
            "question_number",
            "initial_question_submission_id",
            "correction_round_id",
            "source_submission_id",
            "image_file",
            "expected_answer",
            "student_actual_answer",
            "answer_type",
            "transcription_status",
            "verified_grade",
            "source",
            "raw_ocr_text",
            "normalized_answer",
            "ocr_confidence",
            "grading_confidence",
            "ocr_provider",
            "ocr_seconds",
            "inference_seconds",
            "variants_run",
            "grading_strategy",
            "system_grade",
            "automated",
            "decision",
            "human_final_grade",
            "review_seconds",
            "annotation_seconds",
            "ocr_error",
            "alignment_verified",
            "routing_reason",
        ]
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        archive.writestr("ground_truth.csv", output.getvalue())
        archive.writestr("page_records.json", json.dumps(scoped_pages(db, rows, source), indent=2))
        archive.writestr("report.json", json.dumps(report(rows, scoped_pages(db, rows, source)), indent=2))
        archive.writestr(
            "README.txt",
            "Contains answer crops, not full pages or student names. Inspect pixels for identifiers before sharing. UUIDs retain local linkage. Source and OCR provider identify synthetic/mock/real cohorts. Ground truth is independent of AI predictions. Missing truth is excluded from accuracy denominators.\n",
        )
    return Response(
        buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="gradekade-evaluation.zip"'},
    )


@router.get("/evaluation/page-failures")
def page_failures(db: DB):
    pages = db.scalars(
        select(WorksheetSubmission)
        .where(
            WorksheetSubmission.organization_id == settings.organization_id,
            WorksheetSubmission.status == "failed",
        )
        .order_by(WorksheetSubmission.created_at.desc())
        .limit(100)
    )
    return [
        {
            "worksheet_id": str(p.id),
            "error": p.error,
            "alignment": p.alignment_metadata,
            "processing": p.processing_metadata,
            "original_url": f"/api/submissions/{p.id}/image/original",
        }
        for p in pages
    ]
