"""Cross-replica Chartmetric rate-limit governor (task #8, Phase B fix for L004 multi-replica fan-out)

Revision ID: 035
Revises: 034
Create Date: 2026-04-16

Phase A (BURST=1 + drain on 429, commit da26f61) eliminated the
in-process microburst, but each Railway replica still instantiates its
own ChartmetricQuota -> own in-process token bucket. N replicas each
firing at 1.0 req/s gives N x 1.0 req/s globally, which is exactly the
multi-replica fan-out called out in L016.

This migration adds a single-row table that backs a Postgres-coordinated
token bucket. Every fetcher (regardless of replica) acquires from the
same row via SELECT ... FOR UPDATE, so the combined dispatch rate is
strictly bounded by rate_per_sec.

Schema:
  chartmetric_global_bucket (
    id              INT PRIMARY KEY DEFAULT 1   -- always 1 (singleton)
    tokens          DOUBLE PRECISION NOT NULL   -- current bucket level
    last_refill_at  TIMESTAMPTZ NOT NULL        -- when tokens were last computed
    rate_per_sec    DOUBLE PRECISION NOT NULL   -- refill rate (1.0 by default)
    burst           DOUBLE PRECISION NOT NULL   -- bucket capacity (1.0 — strict pacing)
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
  )

The id column has a CHECK constraint pinning it to 1 to make the
"single-row table" invariant explicit at the DB level — anyone who
tries to insert a second row will get a constraint violation, not a
silent split-budget bug.

Burst stays at 1.0 to match the Phase A in-process pacing. Bumping it
above 1.0 would re-introduce the microburst risk (L016) at the cross-
replica layer, defeating the point.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chartmetric_global_bucket",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tokens", sa.Float, nullable=False),
        sa.Column(
            "last_refill_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("rate_per_sec", sa.Float, nullable=False),
        sa.Column("burst", sa.Float, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_check_constraint(
        "ck_chartmetric_global_bucket_singleton",
        "chartmetric_global_bucket",
        "id = 1",
    )
    op.create_check_constraint(
        "ck_chartmetric_global_bucket_positive",
        "chartmetric_global_bucket",
        "rate_per_sec > 0 AND burst > 0 AND tokens >= 0",
    )

    # Seed the singleton row. Match Phase A defaults: 1.0 req/s, burst 1.
    op.execute(
        "INSERT INTO chartmetric_global_bucket "
        "(id, tokens, rate_per_sec, burst) "
        "VALUES (1, 1.0, 1.0, 1.0)"
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_chartmetric_global_bucket_positive",
        "chartmetric_global_bucket",
        type_="check",
    )
    op.drop_constraint(
        "ck_chartmetric_global_bucket_singleton",
        "chartmetric_global_bucket",
        type_="check",
    )
    op.drop_table("chartmetric_global_bucket")
