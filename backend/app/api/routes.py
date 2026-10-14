from datetime import datetime
from io import BytesIO
from typing import Annotated
from uuid import UUID
import json
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session
from app.config import settings
from app.db import get_db
from app.models import Organization, User, Student, WorksheetTemplate, QuestionTemplate, WorksheetSubmission, QuestionSubmission, now
from app.schemas import StudentCreate, QuestionsSave, ReviewCreate
from app.services.ingestion import ingest, png_bytes
from app.services.cropping import crop_region
from app.services.ocr import get_provider
from app.services.pipeline import process_submission, finalize_submission, SAMPLES
from app.services.storage import LocalStorage

router = APIRouter()
DB = Annotated[Session, Depends(get_db)]
storage = LocalStorage(settings.storage_root)
DEMO_USER_ID = UUID("00000000-0000-4000-8000-000000000002")


def ensure_demo_identity(db: Session):
    if not db.get(Organization, settings.organization_id):
        db.add(Organization(id=settings.organization_id, name="Demo learning center"))
        db.flush()
    if not db.get(User, DEMO_USER_ID):
        db.add(User(id=DEMO_USER_ID, organization_id=settings.organization_id, display_name="Local demo grader", role="admin"))
    db.commit()


def owned(db, model, resource_id):
    resource = db.get(model, resource_id)
    if resource is None or resource.organization_id != settings.organization_id:
        raise HTTPException(404, "Resource not found")
    return resource


def owned_question(db, resource_id):
    question = db.get(QuestionSubmission, resource_id)
    if question is None:
        raise HTTPException(404, "Answer not found")
    submission = owned(db, WorksheetSubmission, question.worksheet_submission_id)
    return question, submission


def student_json(student):
    return {"id": str(student.id), "first_name": student.first_name, "last_name": student.last_name,
            "external_id": student.external_id}


def question_template_json(question):
    return {name: getattr(question, name) for name in ["question_number", "x", "y", "width", "height", "expected_answer", "answer_type", "auto_grade_enabled"]} | {"id": str(question.id)}


def template_json(db, template):
    questions = db.scalars(select(QuestionTemplate).where(QuestionTemplate.worksheet_template_id == template.id).order_by(QuestionTemplate.question_number)).all()
    locked = bool(db.scalar(select(func.count()).select_from(WorksheetSubmission).where(WorksheetSubmission.worksheet_template_id == template.id)))
    return {"id": str(template.id), "name": template.name, "version": template.version, "width": template.width,
            "height": template.height, "image_url": f"/api/templates/{template.id}/image", "locked": locked,
            "questions": [question_template_json(q) for q in questions]}


def answer_json(db, answer):
    question = db.get(QuestionTemplate, answer.question_template_id)
    return {"id": str(answer.id), "submission_id": str(answer.worksheet_submission_id), "question_number": question.question_number,
            "crop_url": f"/api/question-submissions/{answer.id}/crop", **{name: getattr(answer, name) for name in [
                "raw_ocr_text", "normalized_answer", "expected_answer", "ocr_confidence", "grading_confidence", "system_grade",
                "final_grade", "review_status", "human_override", "reviewed_answer", "routing_reason", "ocr_provider"]}}


def submission_json(db, submission, detail=True):
    student = db.get(Student, submission.student_id)
    template = db.get(WorksheetTemplate, submission.worksheet_template_id)
    answers = db.scalars(select(QuestionSubmission).join(QuestionTemplate).where(QuestionSubmission.worksheet_submission_id == submission.id).order_by(QuestionTemplate.question_number)).all()
    final = submission.status == "completed"
    return {"id": str(submission.id), "student_name": " ".join(filter(None, [student.first_name, student.last_name])),
            "template_name": template.name, "status": submission.status, "created_at": submission.created_at,
            "finalized_at": submission.finalized_at, "correct": sum(q.final_grade == "correct" for q in answers),
            "total": len(answers), "score_percent": round(100 * sum(q.final_grade == "correct" for q in answers) / len(answers), 1) if final and answers else None,
            "waiting": sum(q.review_status == "needs_review" for q in answers),
            "original_url": f"/api/submissions/{submission.id}/image/original",
            "aligned_url": f"/api/submissions/{submission.id}/image/aligned" if submission.aligned_file_path else None,
            "alignment": submission.alignment_metadata, "processing": submission.processing_metadata, "error": submission.error,
            "answers": [answer_json(db, q) for q in answers] if detail else []}


async def read_page(file: UploadFile):
    content = await file.read(settings.max_upload_bytes + 1)
    await file.close()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(413, "File exceeds the 10 MB upload limit")
    try:
        return ingest(content, settings.max_image_pixels)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None


@router.get("/health")
def health():
    provider = get_provider(settings)
    return {"status": "ok", "ocr_provider": provider.name, "demo_only": True,
            "ocr_fallback": settings.ocr_provider == "mathpix" and provider.name == "mock"}


@router.post("/students", status_code=201)
def create_student(payload: StudentCreate, db: DB):
    student = Student(organization_id=settings.organization_id, **payload.model_dump())
    db.add(student)
    db.commit()
    return student_json(student)


@router.get("/students")
def list_students(db: DB):
    return [student_json(s) for s in db.scalars(select(Student).where(Student.organization_id == settings.organization_id).order_by(Student.created_at))]


@router.post("/templates", status_code=201)
async def create_template(db: DB, name: Annotated[str, Form(min_length=1, max_length=160)], file: Annotated[UploadFile, File()]):
    image = await read_page(file)
    if not name.strip():
        raise HTTPException(422, "Enter a template name")
    template = WorksheetTemplate(organization_id=settings.organization_id, name=name.strip(), template_image_path=storage.save(png_bytes(image)), width=image.width, height=image.height)
    db.add(template)
    db.commit()
    return template_json(db, template)


@router.get("/templates")
def list_templates(db: DB):
    return [template_json(db, t) for t in db.scalars(select(WorksheetTemplate).where(WorksheetTemplate.organization_id == settings.organization_id).order_by(WorksheetTemplate.created_at.desc()))]


@router.get("/templates/{template_id}")
def get_template(template_id: UUID, db: DB):
    return template_json(db, owned(db, WorksheetTemplate, template_id))


@router.get("/templates/{template_id}/image")
def template_image(template_id: UUID, db: DB):
    return FileResponse(storage.path(owned(db, WorksheetTemplate, template_id).template_image_path), media_type="image/png", headers={"Cache-Control": "no-store"})


@router.post("/templates/{template_id}/questions")
def save_questions(template_id: UUID, payload: QuestionsSave, db: DB):
    template = db.scalar(select(WorksheetTemplate).where(WorksheetTemplate.id == template_id, WorksheetTemplate.organization_id == settings.organization_id).with_for_update())
    if template is None:
        raise HTTPException(404, "Template not found")
    if db.scalar(select(func.count()).select_from(WorksheetSubmission).where(WorksheetSubmission.worksheet_template_id == template_id)):
        raise HTTPException(409, "Used templates are locked. Create a new template for a revised answer key.")
    image = ingest(storage.read(template.template_image_path))
    for q in payload.questions:
        try:
            crop_region(image, q.x, q.y, q.width, q.height)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
    db.execute(delete(QuestionTemplate).where(QuestionTemplate.worksheet_template_id == template_id))
    for question in payload.questions:
        db.add(QuestionTemplate(worksheet_template_id=template_id, **question.model_dump()))
    db.commit()
    return template_json(db, template)


def add_submission(db, student_id, template_id, content, fixture_id=None):
    owned(db, Student, student_id)
    template = db.scalar(select(WorksheetTemplate).where(WorksheetTemplate.id == template_id, WorksheetTemplate.organization_id == settings.organization_id).with_for_update())
    if template is None:
        raise HTTPException(404, "Template not found")
    if not db.scalar(select(func.count()).select_from(QuestionTemplate).where(QuestionTemplate.worksheet_template_id == template.id)):
        raise HTTPException(422, "Save answer boxes before uploading a completed worksheet")
    submission = WorksheetSubmission(organization_id=settings.organization_id, student_id=student_id,
        worksheet_template_id=template_id, uploaded_file_path=storage.save(content), fixture_id=fixture_id)
    db.add(submission)
    db.commit()
    return submission


@router.post("/submissions", status_code=201)
async def create_submission(db: DB, student_id: Annotated[UUID, Form()], worksheet_template_id: Annotated[UUID, Form()], file: Annotated[UploadFile, File()], synthetic_demo: Annotated[bool, Form()] = False):
    image = await read_page(file)
    content = png_bytes(image)
    if synthetic_demo:
        import hashlib
        manifest = json.loads((SAMPLES / "manifest.json").read_text())
        template = owned(db, WorksheetTemplate, worksheet_template_id)
        if hashlib.sha256(content).hexdigest() != manifest["submission_sha256"] or hashlib.sha256(storage.read(template.template_image_path)).hexdigest() != manifest["template_sha256"]:
            raise HTTPException(422, "Synthetic demo requires the supplied blank and completed sample pages")
    submission = add_submission(db, student_id, worksheet_template_id, content, "arithmetic-a" if synthetic_demo else None)
    return submission_json(db, submission)


@router.get("/submissions")
def list_submissions(db: DB):
    return [submission_json(db, s, False) for s in db.scalars(select(WorksheetSubmission).where(WorksheetSubmission.organization_id == settings.organization_id).order_by(WorksheetSubmission.created_at.desc()).limit(100))]


@router.get("/submissions/{submission_id}")
def get_submission(submission_id: UUID, db: DB):
    return submission_json(db, owned(db, WorksheetSubmission, submission_id))


@router.post("/submissions/{submission_id}/process")
def process(submission_id: UUID, db: DB):
    submission = owned(db, WorksheetSubmission, submission_id)
    if submission.status in {"completed", "needs_review"}:
        return submission_json(db, submission)
    claimed = db.execute(update(WorksheetSubmission).where(WorksheetSubmission.id == submission_id,
        WorksheetSubmission.status.in_(["uploaded", "failed"])).values(status="processing", error=None))
    if claimed.rowcount != 1:
        raise HTTPException(409, "This worksheet is already being processed")
    db.commit()
    db.refresh(submission)
    try:
        process_submission(db, submission, storage)
        db.commit()
    except Exception:
        db.rollback()
        submission = owned(db, WorksheetSubmission, submission_id)
        submission.status, submission.error = "failed", "Processing failed. Check the template and file, then retry."
        db.commit()
        # Never return/log OCR responses, secrets, or filesystem paths.
        raise HTTPException(422, submission.error) from None
    return submission_json(db, submission)


@router.get("/submissions/{submission_id}/image/{kind}")
def submission_image(submission_id: UUID, kind: str, db: DB):
    submission = owned(db, WorksheetSubmission, submission_id)
    key = submission.uploaded_file_path if kind == "original" else submission.aligned_file_path if kind == "aligned" else None
    if not key:
        raise HTTPException(404, "Page image is not available")
    return FileResponse(storage.path(key), media_type="image/png", headers={"Cache-Control": "no-store"})


@router.get("/question-submissions/{answer_id}/crop")
def answer_crop(answer_id: UUID, db: DB):
    answer, _ = owned_question(db, answer_id)
    return FileResponse(storage.path(answer.crop_image_path), media_type="image/png", headers={"Cache-Control": "no-store"})


@router.get("/review-queue")
def review_queue(db: DB):
    answers = db.scalars(select(QuestionSubmission).join(WorksheetSubmission).join(QuestionTemplate, QuestionSubmission.question_template_id == QuestionTemplate.id).where(
        WorksheetSubmission.organization_id == settings.organization_id, WorksheetSubmission.status == "needs_review",
        QuestionSubmission.review_status == "needs_review").order_by(WorksheetSubmission.created_at, QuestionTemplate.question_number).limit(200)).all()
    return [answer_json(db, q) | {"student_name": submission_json(db, db.get(WorksheetSubmission, q.worksheet_submission_id), False)["student_name"]} for q in answers]


@router.post("/question-submissions/{answer_id}/review")
def review(answer_id: UUID, payload: ReviewCreate, db: DB):
    answer, submission = owned_question(db, answer_id)
    # Serialize decisions within a worksheet so concurrent last reviews finalize consistently.
    db.scalar(select(WorksheetSubmission).where(WorksheetSubmission.id == submission.id).with_for_update())
    if submission.status != "needs_review":
        raise HTTPException(409, "Worksheet is not waiting for review")
    values = {"final_grade": payload.grade, "review_status": "human_reviewed", "human_override": payload.grade != answer.system_grade or payload.recognized_answer is not None,
              "reviewed_at": now(), "reviewed_by": DEMO_USER_ID, "reviewed_answer": payload.recognized_answer}
    result = db.execute(update(QuestionSubmission).where(QuestionSubmission.id == answer_id, QuestionSubmission.review_status == "needs_review").values(**values))
    if result.rowcount != 1:
        raise HTTPException(409, "This answer was already reviewed. Refresh the queue.")
    db.flush()
    db.refresh(answer)
    finalize_submission(db, submission)
    db.commit()
    return answer_json(db, answer)


@router.get("/metrics")
def metrics(db: DB):
    submissions = db.scalars(select(WorksheetSubmission).where(WorksheetSubmission.organization_id == settings.organization_id)).all()
    answers = db.scalars(select(QuestionSubmission).join(WorksheetSubmission).where(WorksheetSubmission.organization_id == settings.organization_id)).all()
    total = len(answers)
    auto = sum(q.review_status == "auto_accepted" for q in answers)
    waiting = sum(q.review_status == "needs_review" for q in answers)
    return {"worksheets_processed": sum(s.status in {"needs_review", "completed"} for s in submissions),
            "answers_processed": total, "auto_graded_percent": round(auto / total * 100, 1) if total else 0,
            "human_review_percent": round((total - auto) / total * 100, 1) if total else 0,
            "waiting_for_review": waiting, "ocr_provider": get_provider(settings).name}


@router.get("/samples/{filename}")
def sample_file(filename: str):
    allowed = {"blank.png", "blank.pdf", "completed.png", "template.json", "answer_key.csv"}
    if filename not in allowed:
        raise HTTPException(404, "Sample not found")
    return FileResponse(SAMPLES / filename, filename=filename)


@router.post("/demo/setup")
def demo_setup(db: DB):
    template = db.scalar(select(WorksheetTemplate).where(WorksheetTemplate.organization_id == settings.organization_id, WorksheetTemplate.identifying_code == "GK-DEMO-A"))
    if template is None:
        from PIL import Image
        content = (SAMPLES / "blank.png").read_bytes()
        image = Image.open(BytesIO(content))
        template = WorksheetTemplate(organization_id=settings.organization_id, name="Arithmetic Practice A", identifying_code="GK-DEMO-A", width=image.width, height=image.height, template_image_path=storage.save(content))
        db.add(template)
        db.flush()
        for question in json.loads((SAMPLES / "template.json").read_text())["questions"]:
            db.add(QuestionTemplate(worksheet_template_id=template.id, **question))
    student = db.scalar(select(Student).where(Student.organization_id == settings.organization_id, Student.external_id == "demo-001"))
    if student is None:
        student = Student(organization_id=settings.organization_id, first_name="Demo student", external_id="demo-001")
        db.add(student)
    db.commit()
    return {"template_id": str(template.id), "student_id": str(student.id)}
