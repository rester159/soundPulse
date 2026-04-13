"""Make songs_master.blueprint_id nullable

Revision ID: 023
Revises: 022
Create Date: 2026-04-13

Artist-first instrumental generation (POST /admin/instrumentals/{id}/
generate-song) allows the CEO to bypass the blueprint and generate a
song directly from an artist + instrumental. That path has no
blueprint_id to attach, so the NOT NULL constraint was crashing the
INSERT with asyncpg NotNullViolationError.

Making blueprint_id nullable is the right long-term move — a manual-
create song doesn't need a spec row, the song's own columns (title,
primary_genre, content_rating, writers, publishers, marketing_hook)
carry all the metadata the pipeline needs after generation.
"""
from alembic import op
import sqlalchemy as sa


revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "songs_master",
        "blueprint_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    # Backfill any NULL rows with a sentinel before reimposing NOT NULL
    # would be required to downgrade cleanly — left as manual work if
    # anyone ever needs to.
    op.alter_column(
        "songs_master",
        "blueprint_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=False,
    )
