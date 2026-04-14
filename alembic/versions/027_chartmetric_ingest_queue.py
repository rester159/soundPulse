"""Chartmetric global work-queue infrastructure.

Revision ID: 027
Revises: 026
Create Date: 2026-04-14

Adds the tables that back the `chartmetric_ingest/` module — a global
priority work queue, a singleton quota-state row, and a per-endpoint
config table that controls freshness targets and priority weights at
runtime without redeploys.

The long-form design rationale lives in `chartmetric_ingest/README` /
the Stage 3 architecture doc; the short version is: every Chartmetric
call in the codebase funnels through one fetcher that drains this
queue. Scrapers become planners that emit jobs here instead of
calling the API directly.

Tables
------
  chartmetric_request_queue
      One row per planned/in-flight/completed API call. The partial
      unique index on `dedup_key WHERE completed_at IS NULL` stops a
      planner from flooding the queue with duplicates — re-enqueues
      bump priority and extend expiry instead of inserting.

  chartmetric_quota_state
      Singleton (CHECK id=1) holding adaptive multiplier + last-429
      timestamp. Persisted so that adaptive throttling survives
      fetcher restarts.

  chartmetric_endpoint_config
      Keyed by `endpoint_key` (= handler name by convention). Holds
      target freshness interval + priority weight. Editable at
      runtime via admin API so we can tune utilization without
      shipping code.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Request queue -------------------------------------------------
    op.create_table(
        "chartmetric_request_queue",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("dedup_key", sa.Text, nullable=False),
        sa.Column("priority", sa.SmallInteger, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column(
            "params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("producer", sa.Text, nullable=False),
        sa.Column("handler", sa.Text, nullable=False),
        sa.Column(
            "handler_context",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "attempt_count",
            sa.SmallInteger,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("response_status", sa.SmallInteger, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Only one PENDING row per dedup_key — completed rows don't block
    # re-enqueues, so the queue can be replayed over time.
    op.execute(
        "CREATE UNIQUE INDEX uq_cmq_pending_dedup "
        "ON chartmetric_request_queue (dedup_key) "
        "WHERE completed_at IS NULL"
    )
    # Fetcher's hot path: claim next ready job by priority then age.
    op.execute(
        "CREATE INDEX idx_cmq_ready "
        "ON chartmetric_request_queue (priority, created_at) "
        "WHERE completed_at IS NULL AND started_at IS NULL"
    )
    # Observability: burn counts by status over a recent window.
    op.create_index(
        "idx_cmq_completed_at",
        "chartmetric_request_queue",
        ["completed_at"],
    )

    # --- Quota state (singleton) ---------------------------------------
    op.create_table(
        "chartmetric_quota_state",
        sa.Column("id", sa.SmallInteger, primary_key=True),
        sa.Column(
            "adaptive_multiplier",
            sa.Float,
            nullable=False,
            server_default=sa.text("1.0"),
        ),
        sa.Column("last_429_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("id = 1", name="ck_cm_quota_singleton"),
    )
    op.execute(
        "INSERT INTO chartmetric_quota_state (id, adaptive_multiplier) "
        "VALUES (1, 1.0)"
    )

    # --- Endpoint config ------------------------------------------------
    op.create_table(
        "chartmetric_endpoint_config",
        sa.Column("endpoint_key", sa.Text, primary_key=True),
        sa.Column("target_interval_hours", sa.Float, nullable=False),
        sa.Column(
            "priority_weight",
            sa.Float,
            nullable=False,
            server_default=sa.text("1.0"),
        ),
        sa.Column(
            "enabled",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("chartmetric_endpoint_config")
    op.drop_table("chartmetric_quota_state")
    op.drop_index("idx_cmq_completed_at", table_name="chartmetric_request_queue")
    op.execute("DROP INDEX IF EXISTS idx_cmq_ready")
    op.execute("DROP INDEX IF EXISTS uq_cmq_pending_dedup")
    op.drop_table("chartmetric_request_queue")
