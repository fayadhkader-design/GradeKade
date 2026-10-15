import json
from dataclasses import asdict
from io import BytesIO
from pathlib import Path
from time import monotonic

import httpx
from PIL import Image
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import QuestionSubmission, QuestionTemplate, WorksheetSubmission, WorksheetTemplate, now
from app.services.alignment import align_submission_to_template
from app.services.cropping import crop_region, is_blank, prepare_variants
from app.services.grading import grade_evidence
from app.services.ingestion import image_digest, png_bytes
from app.services.ocr import REAL_OCR_PROVIDERS, FixtureOCRProvider, OCRResult, get_provider
from app.services.quality import assess_photo
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

    def stage(name, **metadata):
        submission.processing_metadata = {**(submission.processing_metadata or {}), **metadata, "stage": name}
        db.commit()

    manifest = json.loads((SAMPLES / "manifest.json").read_text())
    synthetic_pixels = image_digest(original) in {manifest["submission_sha256"], manifest["template_sha256"]}
    stage("aligning", data_origin="synthetic" if synthetic_pixels else "unknown")
    quality = assess_photo(Image.open(BytesIO(original)), settings.photo_blur_minimum)
    stage("aligning", photo_quality=quality)
    if not quality["usable"]:
        submission.status, submission.error = (
            "failed",
            "Retake this page. The photo is too dark, blurred, empty, or low resolution.",
        )
        stage("failed", retake_required=True)
        return
    alignment = align_submission_to_template(
        Image.open(BytesIO(template_bytes)).convert("RGB"), Image.open(BytesIO(original)).convert("RGB")
    )
    submission.aligned_file_path = storage.save(png_bytes(alignment.image))
    submission.alignment_metadata = {
        **alignment.metadata,
        "accepted_for_cropping": bool(
            alignment.metadata["verified"]
            and alignment.metadata["confidence"] >= settings.alignment_minimum_confidence
        ),
    }
    provider = get_provider(settings)
    if submission.fixture_id:
        manifest = json.loads((SAMPLES / "manifest.json").read_text())
        if (
            image_digest(original) != manifest["submission_sha256"]
            or image_digest(template_bytes) != manifest["template_sha256"]
        ):
            raise ValueError("Synthetic OCR only supports the exact supplied demo pages")
        provider = FixtureOCRProvider(json.loads((SAMPLES / "ocr_predictions.json").read_text()))
    stage(
        "cropping",
        ocr_provider=provider.name,
        ocr_mode="REAL"
        if provider.name in REAL_OCR_PROVIDERS
        else "SYNTHETIC"
        if submission.fixture_id
        else "MOCK",
        threshold=settings.auto_grade_confidence_threshold,
        reject_threshold=settings.auto_reject_confidence_threshold,
        confidence_calibrated=False,
        pipeline_version="0.3",
        ocr_available=getattr(provider, "available", True),
        ocr_diagnostic=getattr(provider, "diagnostic", None),
        experimental_auto_grade=provider.name == "paddle" and settings.paddle_allow_experimental_auto_grade,
    )
    if (
        not alignment.metadata["verified"]
        or alignment.metadata["confidence"] < settings.alignment_minimum_confidence
    ):
        submission.status, submission.error = (
            "failed",
            "Retake this page. Keep the entire worksheet visible, flat, and well lit.",
        )
        stage("failed", retake_required=True)
        return
    db.execute(delete(QuestionSubmission).where(QuestionSubmission.worksheet_submission_id == submission.id))
    prepared = []
    selected = [v.strip() for v in settings.ocr_variants.split(",")]
    if not selected or any(v not in {"color", "grayscale", "contrast"} for v in selected):
        raise ValueError("Unknown OCR preprocessing variant")
    selected = list(dict.fromkeys(selected))
    for question in questions:
        try:
            crop = crop_region(alignment.image, question.x, question.y, question.width, question.height)
        except ValueError:
            submission.status, submission.error = (
                "failed",
                "Retake this page or fix the template. Answer regions fall outside valid bounds.",
            )
            stage("failed", retake_required=True)
            return
        variants = prepare_variants(
            alignment.image,
            question.x,
            question.y,
            question.width,
            question.height,
            settings.crop_padding_pixels,
        )
        # The exact fixture is keyed to unpadded pixels; it must never masquerade as real OCR.
        if submission.fixture_id:
            variants, chosen = {"color": crop}, ["color"]
        else:
            chosen = selected
        contents = {name: png_bytes(img) for name, img in variants.items()}
        paths = {name: storage.save(content) for name, content in contents.items()}
        prepared.append((question, crop, storage.save(png_bytes(crop)), contents, paths, chosen))
    stage("recognizing", questions_total=len(prepared), questions_recognized=0)
    recognized = []
    deadline = monotonic() + 110
    for index, (question, crop, key, contents, paths, chosen) in enumerate(prepared):
        results = []
        ocr_started = monotonic()
        for variant in chosen:
            try:
                if monotonic() >= deadline:
                    ocr = OCRResult("", None, error="page_ocr_budget_exhausted")
                elif hasattr(provider, "recognize_answer"):
                    ocr = provider.recognize_answer(contents[variant], question.answer_type)
                else:
                    ocr = provider.recognize(contents[variant])
                    from dataclasses import replace

                    from app.services.normalization import normalize_answer

                    try:
                        candidate = normalize_answer(ocr.raw_text, question.answer_type)
                    except ValueError:
                        candidate = None
                    ocr = replace(ocr, normalized_candidate=candidate)
            except (httpx.HTTPError, ValueError, TypeError, KeyError):
                ocr = OCRResult("", None, error="ocr_provider_error")
            results.append(ocr)
        recognized.append((question, crop, key, paths, chosen, results, monotonic() - ocr_started))
        stage("recognizing", questions_recognized=index + 1)
    stage("grading")
    total_inference_seconds = 0.0
    timed_inference_answers = 0
    for question, crop, key, paths, chosen, results, ocr_seconds in recognized:
        decision, evidence = grade_evidence(
            results,
            question.expected_answer,
            question.answer_type,
            correct_threshold=settings.auto_grade_confidence_threshold,
            incorrect_threshold=settings.auto_reject_confidence_threshold,
            alignment_verified=alignment.metadata["verified"],
            alignment_confidence=alignment.metadata["confidence"],
            alignment_minimum=settings.alignment_minimum_confidence,
            auto_grade_enabled=question.auto_grade_enabled,
            blank=is_blank(crop),
            allow_unscored_agreement=provider.name == "paddle"
            and settings.paddle_allow_experimental_auto_grade,
            min_agreeing_variants=settings.paddle_min_agreeing_variants,
        )
        inference_seconds = sum(r.provider_metadata.get("inference_seconds", 0) for r in results)
        timed_variants = sum("inference_seconds" in r.provider_metadata for r in results)
        total_inference_seconds += inference_seconds
        timed_inference_answers += bool(timed_variants)
        evidence.update(
            ocr_seconds=ocr_seconds,
            inference_seconds=inference_seconds if timed_variants else None,
            variants_run=sum(
                r.error not in {"page_ocr_budget_exhausted", "paddle_initialization_failed"} for r in results
            ),
            variants={name: asdict(result) for name, result in zip(chosen, results)},
            crop_variants=paths,
            selected_variants=chosen,
            padding_pixels=0 if submission.fixture_id else settings.crop_padding_pixels,
            provider_confidence=results[0].confidence,
            synthetic=bool(submission.fixture_id),
        )
        db.add(
            QuestionSubmission(
                worksheet_submission_id=submission.id,
                question_template_id=question.id,
                crop_image_path=key,
                raw_ocr_text=results[0].raw_text,
                expected_answer=question.expected_answer,
                ocr_confidence=results[0].confidence or 0,
                ocr_provider=provider.name,
                evidence=evidence,
                **asdict(decision),
            )
        )
    db.flush()
    finalize_submission(db, submission)
    submission.processing_metadata = {
        **submission.processing_metadata,
        "stage": submission.status,
        "ocr_available": getattr(provider, "available", True),
        "ocr_diagnostic": getattr(provider, "diagnostic", None),
        "total_ocr_seconds": sum(row[-1] for row in recognized),
        "average_ocr_seconds_per_answer": sum(row[-1] for row in recognized) / len(recognized),
        "total_inference_seconds": total_inference_seconds if timed_inference_answers else None,
        "timed_inference_answers": timed_inference_answers,
        "average_inference_seconds_per_answer": total_inference_seconds / timed_inference_answers
        if timed_inference_answers
        else None,
    }


def finalize_submission(db: Session, submission: WorksheetSubmission):
    decisions = db.scalars(
        select(QuestionSubmission).where(QuestionSubmission.worksheet_submission_id == submission.id)
    ).all()
    complete = bool(decisions) and all(q.final_grade is not None for q in decisions)
    submission.status = "completed" if complete else "needs_review"
    submission.finalized_at = now() if complete else None
