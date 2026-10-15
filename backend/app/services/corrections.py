"""Assignment state derives from immutable initial answers and finalized rounds."""

from datetime import UTC

from sqlalchemy import func, select

from app.models import (
    CorrectionPageSlot,
    CorrectionRound,
    CorrectionTarget,
    QuestionSubmission,
    QuestionTemplate,
    WorksheetSubmission,
)


def utc(value):
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def initial_pages(db, booklet_id):
    return db.scalars(
        select(WorksheetSubmission)
        .where(WorksheetSubmission.booklet_id == booklet_id)
        .order_by(WorksheetSubmission.page_number)
    ).all()


def round_slots(db, round_id):
    return db.scalars(
        select(CorrectionPageSlot).where(CorrectionPageSlot.correction_round_id == round_id)
    ).all()


def round_answers(db, round_id):
    current = select(CorrectionPageSlot.current_submission_id).where(
        CorrectionPageSlot.correction_round_id == round_id
    )
    return db.scalars(
        select(QuestionSubmission).where(QuestionSubmission.worksheet_submission_id.in_(current))
    ).all()


def assignment_state(db, booklet):
    pages = initial_pages(db, booklet.id)
    initial = db.scalars(
        select(QuestionSubmission)
        .join(WorksheetSubmission)
        .where(WorksheetSubmission.booklet_id == booklet.id)
        .order_by(WorksheetSubmission.page_number, QuestionSubmission.created_at)
    ).all()
    expected_total = sum(
        db.scalar(
            select(func.count())
            .select_from(QuestionTemplate)
            .where(QuestionTemplate.worksheet_template_id == p.worksheet_template_id)
        )
        for p in pages
    )
    graded = (
        len(pages) == booklet.page_count
        and len(initial) == expected_total
        and bool(initial)
        and all(p.status == "completed" for p in pages)
        and all(a.final_grade is not None for a in initial)
    )
    rounds = db.scalars(
        select(CorrectionRound)
        .where(CorrectionRound.booklet_id == booklet.id)
        .order_by(CorrectionRound.round_number)
    ).all()
    latest = {a.id: a for a in initial}
    for round_ in rounds:
        if round_.completed_at:
            for attempt in round_answers(db, round_.id):
                if attempt.initial_question_submission_id in latest:
                    latest[attempt.initial_question_submission_id] = attempt
    active = next((r for r in rounds if r.completed_at is None), None)
    unresolved = [a for a in initial if latest[a.id].final_grade == "incorrect"] if graded else []
    complete = graded and not unresolved and active is None
    if active:
        captures = [
            db.get(WorksheetSubmission, slot.current_submission_id)
            for slot in round_slots(db, active.id)
            if slot.current_submission_id
        ]
        status = (
            "failed"
            if any(p.status == "failed" for p in captures)
            else "processing"
            if any(p.status == "processing" for p in captures)
            else "needs_review"
            if any(p.status == "needs_review" for p in captures)
            else "correction_in_progress"
        )
    else:
        status = (
            "completed"
            if complete
            else "needs_correction"
            if graded
            else "failed"
            if any(p.status == "failed" for p in pages)
            else "processing"
            if any(p.status == "processing" for p in pages)
            else "needs_review"
            if any(p.status == "needs_review" for p in pages)
            else "initial"
        )
    completed_at = (
        (
            rounds[-1].completed_at
            if rounds
            else max((p.finalized_at for p in pages if p.finalized_at), default=None)
        )
        if complete
        else None
    )
    return {
        "pages": pages,
        "initial": initial,
        "latest": latest,
        "rounds": rounds,
        "active": active,
        "unresolved": unresolved,
        "graded": graded,
        "complete": complete,
        "status": status,
        "completed_at": completed_at,
        "total": expected_total,
        "initial_correct": sum(a.final_grade == "correct" for a in initial),
        "correct": sum(a.final_grade == "correct" for a in latest.values()),
    }


def targets_for_submission(db, submission):
    if submission.correction_round_id is None:
        return None
    round_ = db.get(CorrectionRound, submission.correction_round_id)
    slot = db.scalar(
        select(CorrectionPageSlot).where(
            CorrectionPageSlot.correction_round_id == round_.id,
            CorrectionPageSlot.source_submission_id == submission.source_submission_id,
        )
    )
    if round_.completed_at or slot is None or slot.current_submission_id != submission.id:
        raise ValueError("This correction capture is no longer active")
    originals = db.scalars(
        select(QuestionSubmission)
        .join(CorrectionTarget, CorrectionTarget.initial_question_submission_id == QuestionSubmission.id)
        .where(
            CorrectionTarget.correction_round_id == round_.id,
            QuestionSubmission.worksheet_submission_id == submission.source_submission_id,
        )
    ).all()
    if not originals:
        raise ValueError("This page has no unresolved correction targets")
    return {a.question_template_id: a.id for a in originals}
