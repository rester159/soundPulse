"""Add music_generation_audio sidecar table for self-hosted audio bytes

Revision ID: 016
Revises: 015
Create Date: 2026-04-12

Replicate delivery URLs expire ~1 hour after success (data_removed flag
flips true, output pointer cleared). Previously-persisted audio_url
values become 404s and the play button greys out in the UI.

Fix: download bytes on successful poll, store in a bytea sidecar, serve
via /api/v1/music/audio/{provider}/{task_id}.mp3. Sidecar keeps the
heavy bytes off the frequently-queried music_generation_calls row.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "music_generation_audio",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("music_generation_call_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("music_generation_calls.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("content_type", sa.String(50), nullable=False, server_default="audio/mpeg"),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("mp3_bytes", postgresql.BYTEA, nullable=False),
        sa.Column("downloaded_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("source_url", sa.Text),
    )


def downgrade() -> None:
    op.drop_table("music_generation_audio")
