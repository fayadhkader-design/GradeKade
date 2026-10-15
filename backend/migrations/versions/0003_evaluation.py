"""Preserve OCR evidence and independent human ground truth."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("question_submissions", sa.Column("evidence", sa.JSON()))
    op.create_table(
        "evaluation_annotations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "question_submission_id",
            sa.Uuid(),
            sa.ForeignKey("question_submissions.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("actual_answer", sa.String(100)),
        sa.Column("transcription_status", sa.String(20), nullable=False),
        sa.Column("verified_grade", sa.String(20), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("annotation_seconds", sa.Float()),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("transcription_status IN ('readable','blank','unreadable')"),
        sa.CheckConstraint("verified_grade IN ('correct','incorrect')"),
        sa.CheckConstraint("source IN ('real_handwriting','synthetic','unknown')"),
    )


def downgrade():
    op.drop_table("evaluation_annotations")
    op.drop_column("question_submissions", "evidence")
