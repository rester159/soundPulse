"""blueprint naming + per-song theme — composition pivot (#16)

Revision ID: 037
Revises: 036
Create Date: 2026-04-18

User pivoted the smart-prompt composition model: smart prompts are no
longer authored on the blueprint, they're composed at song-generation
time from (blueprint + artist DNA + structure + per-song theme +
per-song rating). This migration adds the schema bits the new model
needs.

Changes:

1. song_blueprints
   - `name TEXT NULL` — user-facing blueprint name. Blueprints can now
     be forked from a base, so a name disambiguates them in the UI.
     Backfill: title-case of primary_genre (or genre_id) so legacy
     rows aren't blank.
   - `is_genre_default BOOLEAN NOT NULL DEFAULT false` — marks the
     ONE base blueprint per genre. Forks inherit but never set this.
     Partial unique index ensures at most one default per genre.
   - `smart_prompt_text` becomes NULLABLE. Existing rows keep their
     stored text (read-only — orchestrator no longer reads it). New
     blueprints don't supply one.

2. songs_master
   - `theme TEXT NULL` — per-song theme override picked at generation
     time. Values: 'artist_default' | 'genre_default' |
     'love_relationships' | 'sex' | 'introspection' | 'family' |
     'god' | 'partying' | <free-text>. Resolved by the orchestrator's
     theme module; null means caller didn't pick (treat as
     artist_default).

content_rating already lives on songs_master.content_rating — the
per-song clean/explicit toggle just writes to the existing column,
no new field needed.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "song_blueprints",
        sa.Column("name", sa.Text, nullable=True),
    )
    op.add_column(
        "song_blueprints",
        sa.Column(
            "is_genre_default",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.alter_column("song_blueprints", "smart_prompt_text", nullable=True)

    # Backfill name from primary_genre (or genre_id fallback) so the UI
    # has something to display for legacy rows. INITCAP gives a quick
    # title-case; user can rename in the UI.
    op.execute(
        """
        UPDATE song_blueprints
        SET name = INITCAP(REPLACE(COALESCE(primary_genre, genre_id), '-', ' '))
        WHERE name IS NULL
        """
    )

    # Partial unique index: at most one default blueprint per genre.
    # Uses COALESCE so rows missing primary_genre still constrain on
    # genre_id (they should — pre-#109 rows).
    op.execute(
        """
        CREATE UNIQUE INDEX uq_song_blueprints_genre_default
        ON song_blueprints (COALESCE(primary_genre, genre_id))
        WHERE is_genre_default
        """
    )

    op.add_column(
        "songs_master",
        sa.Column("theme", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("songs_master", "theme")
    op.execute("DROP INDEX IF EXISTS uq_song_blueprints_genre_default")
    op.alter_column("song_blueprints", "smart_prompt_text", nullable=False)
    op.drop_column("song_blueprints", "is_genre_default")
    op.drop_column("song_blueprints", "name")
