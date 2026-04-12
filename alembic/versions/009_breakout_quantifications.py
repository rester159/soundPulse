"""Add breakout_quantifications table

Revision ID: 009
Revises: 008
Create Date: 2026-04-12

Per opportunity_quantification_spec.md — caches per-genre per-window
quantification of expected streams + $ revenue + confidence.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "breakout_quantifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("genre_id", sa.String(100), nullable=False),
        sa.Column("window_end", sa.Date, nullable=False),
        sa.Column("quantification", postgresql.JSON, nullable=False),
        sa.Column("confidence_level", sa.String(20), nullable=False),
        sa.Column("confidence_score", sa.Float, nullable=False),
        sa.Column("total_revenue_median_usd", sa.Float, nullable=False),
        sa.Column("n_breakouts_analyzed", sa.Integer, nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_quant_genre_window",
        "breakout_quantifications",
        ["genre_id", sa.text("window_end DESC")],
        unique=True,
    )
    op.create_index(
        "idx_quant_revenue",
        "breakout_quantifications",
        [sa.text("total_revenue_median_usd DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_quant_revenue", table_name="breakout_quantifications")
    op.drop_index("idx_quant_genre_window", table_name="breakout_quantifications")
    op.drop_table("breakout_quantifications")
