"""track_stat_history: tall/narrow per-track time series.

Revision ID: 026
Revises: 025
Create Date: 2026-04-14

Stage 2B of the Chartmetric ingestion throughput push.

Adds `track_stat_history`, a tall/narrow time-series table holding
daily per-platform / per-metric values for every track that has a
`chartmetric_id`. One row per (track, platform, metric, snapshot_date)
so adding new metrics is a zero-migration operation.

Why tall/narrow instead of wide/compact?
  - New metrics don't require migrations (write a new `metric` string).
  - Each row is self-describing — queries can aggregate by metric
    without knowing the column layout.
  - Sparse coverage is free (missing metrics simply have no row)
    instead of leaking NULLs across dozens of columns.
  - Partial backfills are idempotent via the UNIQUE constraint — we
    can re-run any historical window and rely on ON CONFLICT.

Expected steady-state volume: ~50k tracks × 3 platforms × 3 metrics
× 90 days ≈ 40M rows. Postgres handles tall/narrow time series of this
size comfortably when the (track_id, platform, snapshot_date) index is
in place; it's the access pattern we care about for charts.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "track_stat_history",
        sa.Column(
            "id",
            sa.BigInteger,
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "track_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chartmetric_track_id", sa.Integer, nullable=True, index=True),
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("metric", sa.Text, nullable=False),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("value", sa.BigInteger, nullable=True),
        sa.Column("value_float", sa.Float, nullable=True),
        sa.Column(
            "pulled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "track_id",
            "platform",
            "metric",
            "snapshot_date",
            name="uq_track_stat_history_natural",
        ),
    )
    op.create_index(
        "idx_track_stat_history_lookup",
        "track_stat_history",
        ["track_id", "platform", "snapshot_date"],
    )
    op.create_index(
        "idx_track_stat_history_metric_date",
        "track_stat_history",
        ["metric", "snapshot_date"],
    )


def downgrade() -> None:
    op.drop_index("idx_track_stat_history_metric_date", table_name="track_stat_history")
    op.drop_index("idx_track_stat_history_lookup", table_name="track_stat_history")
    op.drop_table("track_stat_history")
