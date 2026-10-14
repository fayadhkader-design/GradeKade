import json
from dataclasses import asdict
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import QuestionSubmission, QuestionTemplate, WorksheetSubmission, WorksheetTemplate, now
from app.services.alignment import align_submission_to_template
from app.services.cropping import crop_region, is_blank
from app.services.grading import grade_answer
from app.services.ingestion import image_digest, png_bytes
from app.services.ocr import FixtureOCRProvider, OCRResult, get_provider
from app.services.storage import LocalStorage

SAMPLES = Path(__file__).resolve().parents[3] / "sample_data"


def process_submission(db: Session, submission: WorksheetSubmission, storage: LocalStorage):
    template = db.get(WorksheetTemplate, submission.worksheet_template_id)
    questions = db.scalars(
        select(QuestionTemplate)
        .where(QuestionTemplate.worksheet_template_id == template.id)
        .order_by(QuestionTemplate.question_number)
    ).all()
    if not questions:
        raise ValueError("Configure at least one answer box before processing")
    original = storage.read(submission.uploaded_file_path)
    template_bytes = storage.read(template.template_image_path)
    alignment = align_submission_to_template(
        Image.open(BytesIO(template_bytes)).convert("RGB"), Image.open(BytesIO(original)).convert("RGB")
    )
    submission.aligned_file_path = storage.save(png_bytes(alignment.image))
    submission.alignment_metadata = alignment.metadata
    provider = get_provider(settings)
    if submission.fixture_id:
        manifest = json.loads((SAMPLES / "manifest.json").read_text())
        if (
            image_digest(original) != manifest["submission_sha256"]
            or image_digest(template_bytes) != manifest["template_sha256"]
        ):
            raise ValueError("Synthetic OCR only supports the exact supplied demo pages")
        provider = FixtureOCRProvider(json.loads((SAMPLES / "ocr_predictions.json").read_text()))
    submission.processing_metadata = {
        "ocr_provider": provider.name,
        "threshold": settings.auto_grade_confidence_threshold,
        "confidence_calibrated": False,
        "pipeline_version": "0.1",
    }
    db.execute(delete(QuestionSubmission).where(QuestionSubmission.worksheet_submission_id == submission.id))
    for question in questions:
        crop = crop_region(alignment.image, question.x, question.y, question.width, question.height)
        content = png_bytes(crop)
        key = storage.save(content)
        provider_error = False
        try:
            ocr = provider.recognize(content)
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            ocr, provider_error = OCRResult("", 0), True
        decision = grade_answer(
            ocr.raw_text,
            question.expected_answer,
            question.answer_type,
            ocr.confidence,
            settings.auto_grade_confidence_threshold,
            alignment.metadata["verified"],
            question.auto_grade_enabled,
            is_blank(crop),
        )
        record = asdict(decision)
        if provider_error:
            record["routing_reason"] = "ocr_provider_error"
        db.add(
            QuestionSubmission(
                worksheet_submission_id=submission.id,
                question_template_id=question.id,
                crop_image_path=key,
                raw_ocr_text=ocr.raw_text,
                expected_answer=question.expected_answer,
                ocr_confidence=ocr.confidence,
                ocr_provider=provider.name,
                **record,
            )
        )
    db.flush()
    finalize_submission(db, submission)


def finalize_submission(db: Session, submission: WorksheetSubmission):
    decisions = db.scalars(
        select(QuestionSubmission).where(QuestionSubmission.worksheet_submission_id == submission.id)
    ).all()
    complete = bool(decisions) and all(q.final_grade is not None for q in decisions)
    submission.status = "completed" if complete else "needs_review"
    submission.finalized_at = now() if complete else None
