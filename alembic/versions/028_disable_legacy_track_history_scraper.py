"""Disable the legacy chartmetric_track_history standalone scraper.

Revision ID: 028
Revises: 027
Create Date: 2026-04-14

Stage 3 Phase B handoff: the same work is now produced by
`chartmetric_ingest/planners/track_history.py` which emits jobs into
the global queue, so leaving the old scraper enabled would double-
fetch the API. This one-shot flips its `enabled` column to false on
existing deployments. DEFAULT_CONFIGS in scheduler.py already seeds
it disabled for fresh deployments.

The old `scrapers/chartmetric_track_history.py` module stays in the
registry and tree for one more release cycle so historical logs and
analytics that reference it by name keep resolving. It will be
deleted in a follow-up once Phase B is verified in production.

Idempotent — running twice is a no-op (the row either stays disabled
or is already disabled).
"""
from alembic import op


revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE scraper_configs
        SET enabled = false
        WHERE id = 'chartmetric_track_history'
          AND enabled = true
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE scraper_configs
        SET enabled = true
        WHERE id = 'chartmetric_track_history'
    """)
