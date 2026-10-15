"""Add immutable correction rounds, target snapshots and capture slots."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def identity():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade():
    op.create_table(
        "correction_rounds",
        *identity(),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("booklet_id", sa.Uuid(), sa.ForeignKey("booklets.id"), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("unresolved_before", sa.Integer(), nullable=False),
        sa.Column("unresolved_after", sa.Integer()),
        sa.UniqueConstraint("booklet_id", "round_number", name="uq_correction_round_number"),
        sa.CheckConstraint("round_number > 0 AND unresolved_before > 0", name="ck_correction_round_counts"),
    )
    for name in ("organization_id", "booklet_id"):
        op.create_index(f"ix_correction_rounds_{name}", "correction_rounds", [name])
    op.create_index(
        "uq_open_correction_round",
        "correction_rounds",
        ["booklet_id"],
        unique=True,
        sqlite_where=sa.text("completed_at IS NULL"),
        postgresql_where=sa.text("completed_at IS NULL"),
    )
    # Preserve SQLite's unnamed legacy checks during table recreation.
    with op.batch_alter_table(
        "worksheet_submissions",
        table_args=[
            sa.CheckConstraint("status IN ('uploaded','processing','needs_review','completed','failed')")
        ],
    ) as batch:
        batch.add_column(sa.Column("correction_round_id", sa.Uuid()))
        batch.add_column(sa.Column("source_submission_id", sa.Uuid()))
        batch.create_foreign_key(
            "fk_submission_correction_round", "correction_rounds", ["correction_round_id"], ["id"]
        )
        batch.create_foreign_key(
            "fk_submission_source", "worksheet_submissions", ["source_submission_id"], ["id"]
        )
        batch.create_index("ix_worksheet_submissions_correction_round_id", ["correction_round_id"])
    with op.batch_alter_table(
        "question_submissions",
        table_args=[
            sa.CheckConstraint("system_grade IN ('correct','incorrect','uncertain')"),
            sa.CheckConstraint("final_grade IS NULL OR final_grade IN ('correct','incorrect')"),
            sa.CheckConstraint("review_status IN ('auto_accepted','needs_review','human_reviewed')"),
            sa.CheckConstraint(
                "ocr_confidence >= 0 AND ocr_confidence <= 1 AND grading_confidence >= 0 AND grading_confidence <= 1"
            ),
        ],
    ) as batch:
        batch.add_column(sa.Column("initial_question_submission_id", sa.Uuid()))
        batch.create_foreign_key(
            "fk_answer_initial", "question_submissions", ["initial_question_submission_id"], ["id"]
        )
        batch.create_index(
            "ix_question_submissions_initial_question_submission_id", ["initial_question_submission_id"]
        )
    op.create_table(
        "correction_targets",
        *identity(),
        sa.Column("correction_round_id", sa.Uuid(), sa.ForeignKey("correction_rounds.id"), nullable=False),
        sa.Column(
            "initial_question_submission_id",
            sa.Uuid(),
            sa.ForeignKey("question_submissions.id"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "correction_round_id", "initial_question_submission_id", name="uq_correction_target"
        ),
    )
    op.create_index(
        "ix_correction_targets_correction_round_id", "correction_targets", ["correction_round_id"]
    )
    op.create_table(
        "correction_page_slots",
        *identity(),
        sa.Column("correction_round_id", sa.Uuid(), sa.ForeignKey("correction_rounds.id"), nullable=False),
        sa.Column(
            "source_submission_id", sa.Uuid(), sa.ForeignKey("worksheet_submissions.id"), nullable=False
        ),
        sa.Column("current_submission_id", sa.Uuid(), sa.ForeignKey("worksheet_submissions.id")),
        sa.UniqueConstraint("correction_round_id", "source_submission_id", name="uq_correction_page_slot"),
    )
    op.create_index(
        "ix_correction_page_slots_correction_round_id", "correction_page_slots", ["correction_round_id"]
    )


def downgrade():
    if op.get_context().as_sql:
        raise RuntimeError("Correction downgrade requires an online history check")
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM correction_rounds")):
        raise RuntimeError(
            "Cannot downgrade while correction history exists; restore a pre-correction backup instead"
        )
    op.drop_table("correction_page_slots")
    op.drop_table("correction_targets")
    with op.batch_alter_table("question_submissions") as batch:
        batch.drop_index("ix_question_submissions_initial_question_submission_id")
        batch.drop_constraint("fk_answer_initial", type_="foreignkey")
        batch.drop_column("initial_question_submission_id")
    with op.batch_alter_table("worksheet_submissions") as batch:
        batch.drop_index("ix_worksheet_submissions_correction_round_id")
        batch.drop_constraint("fk_submission_correction_round", type_="foreignkey")
        batch.drop_constraint("fk_submission_source", type_="foreignkey")
        batch.drop_column("correction_round_id")
        batch.drop_column("source_submission_id")
    op.drop_table("correction_rounds")
