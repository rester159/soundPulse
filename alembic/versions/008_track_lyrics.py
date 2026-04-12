"""Add track_lyrics table for Genius-sourced lyric storage

Revision ID: 008
Revises: 007
Create Date: 2026-04-12

Stores raw lyrics text + extracted features per track. Layer 5 of the
Breakout Analysis Engine (breakoutengine_prd.md) — feeds Layer 6
LLM-powered lyrical theme analysis.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "track_lyrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("track_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tracks.id"), nullable=False, unique=True),
        sa.Column("lyrics_text", sa.Text, nullable=False),
        sa.Column("word_count", sa.Integer, nullable=True),
        sa.Column("line_count", sa.Integer, nullable=True),
        sa.Column("vocabulary_richness", sa.Float, nullable=True),
        sa.Column("section_structure", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("themes", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("primary_theme", sa.String(50), nullable=True),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("genius_url", sa.String(500), nullable=True),
        sa.Column("genius_song_id", sa.String(50), nullable=True),
        sa.Column("features_json", postgresql.JSON, nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_track_lyrics_track", "track_lyrics", ["track_id"])
    op.create_index("idx_track_lyrics_theme", "track_lyrics", ["primary_theme"])


def downgrade() -> None:
    op.drop_index("idx_track_lyrics_theme", table_name="track_lyrics")
    op.drop_index("idx_track_lyrics_track", table_name="track_lyrics")
    op.drop_table("track_lyrics")
