"""Per-artist structure_template + genre_structure_override (task #109)

Revision ID: 034
Revises: 033
Create Date: 2026-04-15

Two columns on ai_artists that let an artist deviate from the per-genre
default in genre_structures:

    structure_template       JSONB NULL
        Same shape as genre_structures.structure: list[{name, bars, vocals}].
        NULL means the artist has no custom structure -> resolver returns
        the genre row as-is.

    genre_structure_override BOOLEAN NOT NULL DEFAULT FALSE
        When TRUE, the artist's structure_template is used as-is and the
        genre row is ignored. When FALSE (default), the resolver blends
        the artist template with the genre row using the section-name
        merge rule locked in NEXT_SESSION_START_HERE.md §3:

            For each section name (Intro, Verse, Chorus, ...) take the
            artist's bar count + vocals flag if the artist specified it;
            otherwise keep the genre's. Artist-only sections insert in
            the artist-declared order; genre-only sections stay in place.

The override flag exists so an artist with a strong signature structure
(e.g. a producer who always opens with a 16-bar voicemail intro) can opt
out of the blend without having to redeclare every section.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_artists",
        sa.Column(
            "structure_template",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "ai_artists",
        sa.Column(
            "genre_structure_override",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
    )


def downgrade() -> None:
    op.drop_column("ai_artists", "genre_structure_override")
    op.drop_column("ai_artists", "structure_template")
