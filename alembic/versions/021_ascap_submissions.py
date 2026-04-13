"""ASCAP work submissions table (T-190..T-194)

Revision ID: 021
Revises: 020
Create Date: 2026-04-13

Tracks every ASCAP work registration attempt — the Fonzworth submissions
agent writes here before submitting, updates on progress, and writes the
returned ASCAP work_id back on success.

Minimum spec (per PRD §31):
  - One row per (song_id, submission_attempt)
  - status: pending | logged_in | submitted | accepted | rejected | failed
  - ascap_work_id: the portal-returned identifier on success
  - writers_json + publishers_json: the split structure at submission time
  - screenshot_blob_id: FK to pro_submission_blobs for audit screenshots
  - retry_count + last_error_message for re-queue logic
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ascap_submissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "song_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("songs_master.song_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "attempt_number",
            sa.Integer,
            nullable=False,
            server_default="1",
        ),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("ascap_work_id", sa.Text, nullable=True),
        sa.Column("writers_json", postgresql.JSONB, nullable=True),
        sa.Column("publishers_json", postgresql.JSONB, nullable=True),
        sa.Column("submission_title", sa.Text, nullable=True),
        sa.Column("submission_iswc", sa.Text, nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error_message", sa.Text, nullable=True),
        sa.Column("portal_screenshot_b64", sa.Text, nullable=True),
        sa.Column("raw_response", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_ascap_submissions_status",
        "ascap_submissions",
        "status IN ('pending','logged_in','submitted','accepted','rejected','failed','awaiting_review')",
    )
    op.create_index(
        "ix_ascap_submissions_song_id",
        "ascap_submissions",
        ["song_id"],
    )
    op.create_index(
        "ix_ascap_submissions_status",
        "ascap_submissions",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_ascap_submissions_status", table_name="ascap_submissions")
    op.drop_index("ix_ascap_submissions_song_id", table_name="ascap_submissions")
    op.drop_constraint("ck_ascap_submissions_status", "ascap_submissions", type_="check")
    op.drop_table("ascap_submissions")
