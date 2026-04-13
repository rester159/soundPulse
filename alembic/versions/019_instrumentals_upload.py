"""Add instrumentals table + instrumental_blobs sidecar (task #86)

Revision ID: 019
Revises: 018
Create Date: 2026-04-13

Powers the 'upload an instrumental + Suno writes vocals on top' feature.

Design notes:
  - instrumentals = metadata row (title, bpm, key, tempo, duration,
    uploaded_by_user, notes, optional chord_chart_json).
  - instrumental_blobs = bytea sidecar for the actual audio bytes. One
    row per instrumental, unique FK so the blob is auto-deleted when
    the instrumental row goes. Mirrors the music_generation_audio +
    visual_asset_blobs pattern we use everywhere else for self-hosted
    bytes.
  - We need to expose a PUBLIC (unauthenticated) streaming URL so
    Kie.ai's server can fetch the audio by URL when we pass it to the
    /api/v1/generate/add-vocals endpoint. That URL uses the
    instrumentals.id UUID as the path segment — effectively unguessable
    — so no separate signing mechanism is required for MVP.
  - last_used_at tracks when an instrumental was last passed to a Suno
    generation so we can surface 'frequently used' in the SongLab UI.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instrumentals",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("uploaded_by", sa.Text, nullable=True),  # CEO user or agent name
        sa.Column("genre_hint", sa.Text, nullable=True),
        sa.Column("tempo_bpm", sa.Float, nullable=True),
        sa.Column("key_hint", sa.Text, nullable=True),  # e.g. "A minor", "F# major"
        sa.Column("duration_seconds", sa.Float, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "original_filename",
            sa.Text,
            nullable=True,
        ),
        sa.Column(
            "content_type",
            sa.String(50),
            nullable=False,
            server_default="audio/mpeg",
        ),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("source_url", sa.Text, nullable=True),  # if uploaded via URL instead of file
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column("usage_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_instrumentals_created_at",
        "instrumentals",
        ["created_at"],
    )

    op.create_table(
        "instrumental_blobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "instrumental_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("instrumentals.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "audio_bytes",
            postgresql.BYTEA,
            nullable=False,
        ),
        sa.Column(
            "stored_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("instrumental_blobs")
    op.drop_index("ix_instrumentals_created_at", table_name="instrumentals")
    op.drop_table("instrumentals")
