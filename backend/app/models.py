from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
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
    __table_args__ = (
        CheckConstraint("status IN ('uploaded','processing','needs_review','completed','failed')"),
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
    routing_reason: Mapped[str] = mapped_column(String(100))
    ocr_provider: Mapped[str] = mapped_column(String(40))
    __table_args__ = (
        UniqueConstraint("worksheet_submission_id", "question_template_id"),
        CheckConstraint("system_grade IN ('correct','incorrect','uncertain')"),
        CheckConstraint("final_grade IS NULL OR final_grade IN ('correct','incorrect')"),
        CheckConstraint("review_status IN ('auto_accepted','needs_review','human_reviewed')"),
        CheckConstraint(
            "ocr_confidence >= 0 AND ocr_confidence <= 1 AND grading_confidence >= 0 AND grading_confidence <= 1"
        ),
    )
