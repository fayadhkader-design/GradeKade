"""Capture, review and finalize corrections without replacing earlier attempts."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.api import routes
from app.api.routes import DB, answer_json, owned, read_page, submission_json
from app.models import (
    Booklet,
    CorrectionPageSlot,
    CorrectionRound,
    CorrectionTarget,
    QuestionSubmission,
    QuestionTemplate,
    WorksheetSubmission,
    now,
)
from app.services.corrections import assignment_state, round_answers, round_slots, utc
from app.services.ingestion import image_digest, png_bytes

router = APIRouter()


def round_json(db, round_):
    targets = db.scalars(
        select(QuestionSubmission)
        .join(CorrectionTarget, CorrectionTarget.initial_question_submission_id == QuestionSubmission.id)
        .where(CorrectionTarget.correction_round_id == round_.id)
    ).all()
    slots = round_slots(db, round_.id)
    captures = [
        db.get(WorksheetSubmission, s.current_submission_id) for s in slots if s.current_submission_id
    ]
    answers = round_answers(db, round_.id)
    ready = (
        len(captures) == len(slots)
        and all(p.status == "completed" for p in captures)
        and (len(answers) == len(targets) and all(a.final_grade is not None for a in answers))
    )
    human = [a for a in answers if a.review_status == "human_reviewed"]
    return {
        "id": str(round_.id),
        "booklet_id": str(round_.booklet_id),
        "round_number": round_.round_number,
        "created_at": round_.created_at,
        "completed_at": round_.completed_at,
        "status": "finalized" if round_.completed_at else "ready_to_finalize" if ready else "in_progress",
        "unresolved_before": round_.unresolved_before,
        "unresolved_after": round_.unresolved_after,
        "corrected": sum(a.final_grade == "correct" for a in answers),
        "waiting": sum(a.review_status == "needs_review" for a in answers),
        "auto_graded": sum(a.review_status == "auto_accepted" for a in answers),
        "human_reviews": len(human),
        "review_seconds": sum(a.review_seconds or 0 for a in human),
        "timed_reviews": sum(a.review_seconds is not None for a in human),
        "processing_seconds": sum(p.processing_seconds or 0 for p in captures),
        "pages": [
            {
                "source_submission_id": str(s.source_submission_id),
                "page_number": db.get(WorksheetSubmission, s.source_submission_id).page_number,
                "question_numbers": sorted(
                    db.get(QuestionTemplate, a.question_template_id).question_number
                    for a in targets
                    if a.worksheet_submission_id == s.source_submission_id
                ),
                "submission": submission_json(db, db.get(WorksheetSubmission, s.current_submission_id))
                if s.current_submission_id
                else None,
            }
            for s in slots
        ],
    }


def workflow_json(db, booklet):
    state = assignment_state(db, booklet)
    initial = state["initial"]
    total = state["total"]
    all_attempts = [a for r in state["rounds"] for a in round_answers(db, r.id)]
    return {
        "status": state["status"],
        "completed_at": state["completed_at"],
        "initial_accuracy": round(100 * state["initial_correct"] / total, 1) if state["graded"] else None,
        "initial_correct": state["initial_correct"],
        "total_questions": total,
        "initially_incorrect": sum(a.final_grade == "incorrect" for a in initial)
        if state["graded"]
        else None,
        "unresolved_count": len(state["unresolved"]) if state["graded"] else None,
        "current_correct": state["correct"],
        "current_accuracy": round(100 * state["correct"] / total, 1) if state["graded"] and total else None,
        "correction_round_count": len(state["rounds"]),
        "total_correction_attempts": len(all_attempts),
        "time_to_completion_seconds": (utc(state["completed_at"]) - utc(booklet.created_at)).total_seconds()
        if state["completed_at"]
        else None,
        "active_round_id": str(state["active"].id) if state["active"] else None,
        "unresolved": [
            {
                "initial_answer_id": str(a.id),
                "source_submission_id": str(a.worksheet_submission_id),
                "page_number": db.get(WorksheetSubmission, a.worksheet_submission_id).page_number,
                "question_number": db.get(QuestionTemplate, a.question_template_id).question_number,
            }
            for a in state["unresolved"]
        ],
        "rounds": [round_json(db, r) for r in state["rounds"]],
    }


@router.post("/submissions/{submission_id}/assignment")
def attach_assignment(submission_id: UUID, db: DB):
    page = owned(db, WorksheetSubmission, submission_id)
    if page.correction_round_id:
        raise HTTPException(409, "Correction captures already belong to an assignment")
    if page.booklet_id:
        return {"booklet_id": str(page.booklet_id)}
    db.scalar(select(WorksheetSubmission).where(WorksheetSubmission.id == page.id).with_for_update())
    booklet = Booklet(
        organization_id=page.organization_id,
        student_id=page.student_id,
        page_count=1,
        capture_seconds=0,
        synthetic_demo=bool(page.fixture_id),
        created_at=page.created_at,
    )
    db.add(booklet)
    db.flush()
    result = db.execute(
        update(WorksheetSubmission)
        .where(WorksheetSubmission.id == page.id, WorksheetSubmission.booklet_id.is_(None))
        .values(booklet_id=booklet.id, page_number=1)
    )
    if result.rowcount != 1:
        db.rollback()
        db.refresh(page)
        return {"booklet_id": str(page.booklet_id)}
    db.commit()
    return {"booklet_id": str(booklet.id)}


@router.get("/booklets/{booklet_id}/corrections")
def corrections(booklet_id: UUID, db: DB):
    return workflow_json(db, owned(db, Booklet, booklet_id))


@router.post("/booklets/{booklet_id}/correction-rounds", status_code=201)
def start_round(booklet_id: UUID, db: DB):
    booklet = owned(db, Booklet, booklet_id)
    db.scalar(select(Booklet).where(Booklet.id == booklet.id).with_for_update())
    state = assignment_state(db, booklet)
    if state["active"]:
        return round_json(db, state["active"])
    if not state["graded"] or not state["unresolved"]:
        raise HTTPException(
            409, "Finalize initial grading and review first; only incorrect answers can be corrected"
        )
    round_ = CorrectionRound(
        organization_id=booklet.organization_id,
        booklet_id=booklet.id,
        round_number=len(state["rounds"]) + 1,
        unresolved_before=len(state["unresolved"]),
    )
    db.add(round_)
    try:
        db.flush()
        for answer in state["unresolved"]:
            db.add(CorrectionTarget(correction_round_id=round_.id, initial_question_submission_id=answer.id))
        for page_id in {a.worksheet_submission_id for a in state["unresolved"]}:
            db.add(CorrectionPageSlot(correction_round_id=round_.id, source_submission_id=page_id))
        db.commit()
    except IntegrityError:
        db.rollback()
        active = assignment_state(db, booklet)["active"]
        if active:
            return round_json(db, active)
        raise HTTPException(409, "Assignment changed; refresh before starting corrections") from None
    return round_json(db, round_)


@router.get("/correction-rounds/{round_id}")
def get_round(round_id: UUID, db: DB):
    return round_json(db, owned(db, CorrectionRound, round_id))


@router.post("/correction-rounds/{round_id}/pages/{source_id}", status_code=201)
async def upload_correction(round_id: UUID, source_id: UUID, db: DB, file: Annotated[UploadFile, File()]):
    round_ = owned(db, CorrectionRound, round_id)
    source = owned(db, WorksheetSubmission, source_id)
    image = await read_page(file)
    content = png_bytes(image)
    # Lock round before slot/page in every correction mutation.
    db.refresh(round_, with_for_update=True)
    if round_.completed_at:
        raise HTTPException(409, "This round is finalized; its history is immutable")
    slot = db.scalar(
        select(CorrectionPageSlot)
        .where(
            CorrectionPageSlot.correction_round_id == round_id,
            CorrectionPageSlot.source_submission_id == source_id,
        )
        .with_for_update()
    )
    if slot is None or source.booklet_id != round_.booklet_id:
        raise HTTPException(422, "This page has no unresolved questions in this round")
    existing = db.get(WorksheetSubmission, slot.current_submission_id) if slot.current_submission_id else None
    if existing and image_digest(routes.storage.read(existing.uploaded_file_path)) == image_digest(content):
        return submission_json(db, existing)
    if existing and existing.status not in {"failed", "uploaded"}:
        raise HTTPException(
            409, "A processing or graded capture cannot be replaced. Finish this round first."
        )
    page = WorksheetSubmission(
        organization_id=round_.organization_id,
        student_id=source.student_id,
        worksheet_template_id=source.worksheet_template_id,
        uploaded_file_path=routes.storage.save(content),
        correction_round_id=round_id,
        source_submission_id=source.id,
    )
    # Corrections never inherit fixture OCR: supplied completed pixels would fabricate a correction.
    db.add(page)
    db.flush()
    changed = db.execute(
        update(CorrectionPageSlot)
        .where(
            CorrectionPageSlot.id == slot.id,
            CorrectionPageSlot.current_submission_id == (existing.id if existing else None),
        )
        .values(current_submission_id=page.id)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Another capture was uploaded; refresh this round")
    db.commit()
    return submission_json(db, page)


@router.post("/correction-rounds/{round_id}/finalize")
def finalize_round(round_id: UUID, db: DB):
    round_ = owned(db, CorrectionRound, round_id)
    db.refresh(round_, with_for_update=True)
    if round_.completed_at:
        return round_json(db, round_)
    data = round_json(db, round_)
    if data["status"] != "ready_to_finalize":
        raise HTTPException(
            409, "Process every correction page and review every targeted answer before finalizing"
        )
    round_.completed_at = now()
    round_.unresolved_after = round_.unresolved_before - data["corrected"]
    db.commit()
    return round_json(db, round_)


@router.get("/booklets/{booklet_id}/question-history")
def question_history(booklet_id: UUID, db: DB):
    booklet = owned(db, Booklet, booklet_id)
    state = assignment_state(db, booklet)
    history = []
    for original in state["initial"]:
        attempts = [
            original,
            *db.scalars(
                select(QuestionSubmission)
                .join(WorksheetSubmission)
                .join(CorrectionRound, WorksheetSubmission.correction_round_id == CorrectionRound.id)
                .where(
                    CorrectionRound.booklet_id == booklet_id,
                    QuestionSubmission.initial_question_submission_id == original.id,
                )
                .order_by(CorrectionRound.round_number, QuestionSubmission.created_at)
            ).all(),
        ]
        history.append(
            {
                "initial_answer_id": str(original.id),
                "question_number": db.get(QuestionTemplate, original.question_template_id).question_number,
                "page_number": db.get(WorksheetSubmission, original.worksheet_submission_id).page_number,
                "expected_answer": original.expected_answer,
                "resolved": state["latest"][original.id].final_grade == "correct",
                "attempts": [
                    {
                        **answer_json(db, a),
                        "created_at": a.created_at,
                        "reviewed_at": a.reviewed_at,
                        "review_seconds": a.review_seconds,
                        "round_number": db.get(
                            CorrectionRound,
                            db.get(WorksheetSubmission, a.worksheet_submission_id).correction_round_id,
                        ).round_number
                        if a.initial_question_submission_id
                        else 0,
                        "original_url": f"/api/submissions/{a.worksheet_submission_id}/image/original",
                    }
                    for a in attempts
                ],
            }
        )
    return history
