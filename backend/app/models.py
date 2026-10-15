from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def now():
    return datetime.now(UTC)


class Identity:
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Organization(Identity, Base):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(160))


class User(Identity, Base):
    __tablename__ = "users"
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    role: Mapped[str] = mapped_column(String(20))
    __table_args__ = (CheckConstraint("role IN ('admin','grader')"),)


class Student(Identity, Base):
    __tablename__ = "students"
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str | None] = mapped_column(String(80))
    external_id: Mapped[str | None] = mapped_column(String(80))


class WorksheetTemplate(Identity, Base):
    __tablename__ = "worksheet_templates"
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    version: Mapped[int] = mapped_column(Integer, default=1)
    template_image_path: Mapped[str] = mapped_column(String(200))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    identifying_code: Mapped[str | None] = mapped_column(String(80))


class QuestionTemplate(Identity, Base):
    __tablename__ = "question_templates"
    worksheet_template_id: Mapped[UUID] = mapped_column(ForeignKey("worksheet_templates.id"), index=True)
    question_number: Mapped[int] = mapped_column(Integer)
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    width: Mapped[float] = mapped_column(Float)
    height: Mapped[float] = mapped_column(Float)
    expected_answer: Mapped[str] = mapped_column(String(100))
    answer_type: Mapped[str] = mapped_column(String(20))
    auto_grade_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (
        UniqueConstraint("worksheet_template_id", "question_number"),
        CheckConstraint(
            "question_number > 0 AND x >= 0 AND y >= 0 AND width > 0 AND height > 0 AND x + width <= 1.000001 AND y + height <= 1.000001"
        ),
        CheckConstraint("answer_type IN ('integer','decimal','fraction')"),
    )


class Booklet(Identity, Base):
    __tablename__ = "booklets"
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    student_id: Mapped[UUID] = mapped_column(ForeignKey("students.id"))
    page_count: Mapped[int] = mapped_column(Integer)
    capture_seconds: Mapped[float] = mapped_column(Float, default=0)
    synthetic_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    manual_baseline_seconds: Mapped[float | None] = mapped_column(Float)
    __table_args__ = (CheckConstraint("page_count >= 1 AND page_count <= 30 AND capture_seconds >= 0"),)


class WorksheetSubmission(Identity, Base):
    __tablename__ = "worksheet_submissions"
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    student_id: Mapped[UUID] = mapped_column(ForeignKey("students.id"))
    worksheet_template_id: Mapped[UUID] = mapped_column(ForeignKey("worksheet_templates.id"))
    uploaded_file_path: Mapped[str] = mapped_column(String(200))
    aligned_file_path: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="uploaded", index=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    alignment_metadata: Mapped[dict | None] = mapped_column(JSON)
    processing_metadata: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(String(200))
    fixture_id: Mapped[str | None] = mapped_column(String(50))
    booklet_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("booklets.id", name="fk_submission_booklet"), index=True
    )
    page_number: Mapped[int | None] = mapped_column(Integer)
    processing_seconds: Mapped[float | None] = mapped_column(Float)
    correction_round_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("correction_rounds.id", name="fk_submission_correction_round"), index=True
    )
    source_submission_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("worksheet_submissions.id", name="fk_submission_source")
    )

    __table_args__ = (
        CheckConstraint("status IN ('uploaded','processing','needs_review','completed','failed')"),
        UniqueConstraint("booklet_id", "page_number", name="uq_booklet_page"),
        CheckConstraint(
            "(booklet_id IS NULL AND page_number IS NULL) OR (booklet_id IS NOT NULL AND page_number > 0)",
            name="ck_booklet_page",
        ),
    )


class QuestionSubmission(Identity, Base):
    __tablename__ = "question_submissions"
    worksheet_submission_id: Mapped[UUID] = mapped_column(ForeignKey("worksheet_submissions.id"), index=True)
    question_template_id: Mapped[UUID] = mapped_column(ForeignKey("question_templates.id"))
    crop_image_path: Mapped[str] = mapped_column(String(200))
    raw_ocr_text: Mapped[str] = mapped_column(String(1000))
    normalized_answer: Mapped[str | None] = mapped_column(String(100))
    expected_answer: Mapped[str] = mapped_column(String(100))
    ocr_confidence: Mapped[float] = mapped_column(Float)
    grading_confidence: Mapped[float] = mapped_column(Float)
    system_grade: Mapped[str] = mapped_column(String(20))
    final_grade: Mapped[str | None] = mapped_column(String(20))
    review_status: Mapped[str] = mapped_column(String(20), index=True)
    human_override: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_answer: Mapped[str | None] = mapped_column(String(100))
    review_seconds: Mapped[float | None] = mapped_column(Float)
    routing_reason: Mapped[str] = mapped_column(String(100))
    ocr_provider: Mapped[str] = mapped_column(String(40))
    evidence: Mapped[dict | None] = mapped_column(JSON)
    initial_question_submission_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("question_submissions.id", name="fk_answer_initial"), index=True
    )

    __table_args__ = (
        UniqueConstraint("worksheet_submission_id", "question_template_id"),
        CheckConstraint("system_grade IN ('correct','incorrect','uncertain')"),
        CheckConstraint("final_grade IS NULL OR final_grade IN ('correct','incorrect')"),
        CheckConstraint("review_status IN ('auto_accepted','needs_review','human_reviewed')"),
        CheckConstraint(
            "ocr_confidence >= 0 AND ocr_confidence <= 1 AND grading_confidence >= 0 AND grading_confidence <= 1"
        ),
    )


class EvaluationAnnotation(Identity, Base):
    """Human truth is independent of immutable OCR/system snapshots."""

    __tablename__ = "evaluation_annotations"
    question_submission_id: Mapped[UUID] = mapped_column(ForeignKey("question_submissions.id"), unique=True)
    actual_answer: Mapped[str | None] = mapped_column(String(100))
    transcription_status: Mapped[str] = mapped_column(String(20))
    verified_grade: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(30))
    annotation_seconds: Mapped[float | None] = mapped_column(Float)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        CheckConstraint("transcription_status IN ('readable','blank','unreadable')"),
        CheckConstraint("verified_grade IN ('correct','incorrect')"),
        CheckConstraint("source IN ('real_handwriting','synthetic','unknown')"),
    )


class CorrectionRound(Identity, Base):
    __tablename__ = "correction_rounds"
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    booklet_id: Mapped[UUID] = mapped_column(ForeignKey("booklets.id"), index=True)
    round_number: Mapped[int] = mapped_column(Integer)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unresolved_before: Mapped[int] = mapped_column(Integer)
    unresolved_after: Mapped[int | None] = mapped_column(Integer)
    __table_args__ = (
        UniqueConstraint("booklet_id", "round_number", name="uq_correction_round_number"),
        CheckConstraint("round_number > 0 AND unresolved_before > 0", name="ck_correction_round_counts"),
        Index(
            "uq_open_correction_round",
            "booklet_id",
            unique=True,
            sqlite_where=text("completed_at IS NULL"),
            postgresql_where=text("completed_at IS NULL"),
        ),
    )


class CorrectionTarget(Identity, Base):
    __tablename__ = "correction_targets"
    correction_round_id: Mapped[UUID] = mapped_column(ForeignKey("correction_rounds.id"), index=True)
    initial_question_submission_id: Mapped[UUID] = mapped_column(ForeignKey("question_submissions.id"))
    __table_args__ = (
        UniqueConstraint(
            "correction_round_id", "initial_question_submission_id", name="uq_correction_target"
        ),
    )


class CorrectionPageSlot(Identity, Base):
    __tablename__ = "correction_page_slots"
    correction_round_id: Mapped[UUID] = mapped_column(ForeignKey("correction_rounds.id"), index=True)
    source_submission_id: Mapped[UUID] = mapped_column(ForeignKey("worksheet_submissions.id"))
    current_submission_id: Mapped[UUID | None] = mapped_column(ForeignKey("worksheet_submissions.id"))
    __table_args__ = (
        UniqueConstraint("correction_round_id", "source_submission_id", name="uq_correction_page_slot"),
    )
