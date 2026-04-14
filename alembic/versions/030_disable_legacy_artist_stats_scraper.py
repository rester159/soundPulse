"""Disable the legacy chartmetric_artist_stats standalone scraper.

Revision ID: 030
Revises: 029
Create Date: 2026-04-14

Stage 3 Phase C1 handoff: the work now flows through the
`chartmetric_ingest.planners.artist_stats` planner + global queue.
Idempotent UPDATE mirroring migration 028.
"""
from alembic import op


revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE scraper_configs
        SET enabled = false
        WHERE id = 'chartmetric_artist_stats'
          AND enabled = true
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE scraper_configs
        SET enabled = true
        WHERE id = 'chartmetric_artist_stats'
    """)
