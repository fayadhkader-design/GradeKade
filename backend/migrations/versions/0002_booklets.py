"""Ordered booklet batches and observed workflow timing."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None
STATUS = "status IN ('uploaded','processing','needs_review','completed','failed')"


def upgrade():
    op.create_table(
        "booklets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("student_id", sa.Uuid(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("capture_seconds", sa.Float(), nullable=False),
        sa.Column("synthetic_demo", sa.Boolean(), nullable=False),
        sa.Column("manual_baseline_seconds", sa.Float()),
        sa.CheckConstraint("page_count >= 1 AND page_count <= 30 AND capture_seconds >= 0"),
    )
    op.create_index("ix_booklets_organization_id", "booklets", ["organization_id"])
    with op.batch_alter_table("worksheet_submissions", table_args=[sa.CheckConstraint(STATUS)]) as batch:
        batch.add_column(sa.Column("booklet_id", sa.Uuid()))
        batch.add_column(sa.Column("page_number", sa.Integer()))
        batch.add_column(sa.Column("processing_seconds", sa.Float()))
        batch.create_foreign_key("fk_submission_booklet", "booklets", ["booklet_id"], ["id"])
        batch.create_index("ix_worksheet_submissions_booklet_id", ["booklet_id"])
        batch.create_unique_constraint("uq_booklet_page", ["booklet_id", "page_number"])
        batch.create_check_constraint(
            "ck_booklet_page",
            "(booklet_id IS NULL AND page_number IS NULL) OR (booklet_id IS NOT NULL AND page_number > 0)",
        )
    op.add_column("question_submissions", sa.Column("review_seconds", sa.Float()))


def downgrade():
    op.drop_column("question_submissions", "review_seconds")
    with op.batch_alter_table("worksheet_submissions", table_args=[sa.CheckConstraint(STATUS)]) as batch:
        batch.drop_constraint("fk_submission_booklet", type_="foreignkey")
        batch.drop_constraint("uq_booklet_page", type_="unique")
        batch.drop_constraint("ck_booklet_page", type_="check")
        batch.drop_index("ix_worksheet_submissions_booklet_id")
        batch.drop_column("booklet_id")
        batch.drop_column("page_number")
        batch.drop_column("processing_seconds")
    op.drop_index("ix_booklets_organization_id", table_name="booklets")
    op.drop_table("booklets")
