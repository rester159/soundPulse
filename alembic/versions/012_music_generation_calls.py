"""Add music_generation_calls table

Revision ID: 012
Revises: 011
Create Date: 2026-04-12

Lightweight generation log for the music provider layer (§24, §56). Not
songs_master — that arrives later once QA + distribution are wired. This
table captures every provider call so SongLab can show history, costs
can be tallied, and failures are auditable.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "music_generation_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("task_id", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        # pending | processing | succeeded | failed
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("params_json", postgresql.JSONB, nullable=True),
        sa.Column("model_variant", sa.String(100), nullable=True),
        sa.Column("duration_seconds_requested", sa.Integer, nullable=True),
        sa.Column("genre_hint", sa.String(100), nullable=True),
        sa.Column("breakout_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("blueprint_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audio_url", sa.Text, nullable=True),
        sa.Column("audio_duration_seconds", sa.Float, nullable=True),
        sa.Column("estimated_cost_usd", sa.Float, nullable=True),
        sa.Column("actual_cost_usd", sa.Float, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("raw_response", postgresql.JSONB, nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("provider", "task_id", name="music_gen_provider_task_unique"),
    )
    op.create_index(
        "idx_music_gen_submitted_at",
        "music_generation_calls",
        ["submitted_at"],
        postgresql_ops={"submitted_at": "DESC"},
    )
    op.create_index(
        "idx_music_gen_status",
        "music_generation_calls",
        ["status"],
    )
    op.create_index(
        "idx_music_gen_genre",
        "music_generation_calls",
        ["genre_hint"],
    )


def downgrade() -> None:
    op.drop_index("idx_music_gen_genre", table_name="music_generation_calls")
    op.drop_index("idx_music_gen_status", table_name="music_generation_calls")
    op.drop_index("idx_music_gen_submitted_at", table_name="music_generation_calls")
    op.drop_table("music_generation_calls")
