"""Add breakout_events + genre_feature_deltas tables

Revision ID: 007
Revises: 006
Create Date: 2026-04-12

Breakout Analysis Engine Layer 1+2 (breakoutengine_prd.md):
  - breakout_events: tracks that significantly outperform genre peers
  - genre_feature_deltas: cached feature delta analysis per genre
  - genre_lyrical_analysis: LLM-powered lyrical theme extraction (Layer 3)
  - model_runs: ML model training history (Layer 6)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "breakout_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tracks.id"), nullable=False),
        sa.Column("genre_id", sa.String(100), nullable=False),
        sa.Column("detection_date", sa.Date, nullable=False),
        sa.Column("window_start", sa.Date, nullable=False),
        sa.Column("window_end", sa.Date, nullable=False),
        sa.Column("peak_composite", sa.Float, nullable=False),
        sa.Column("peak_velocity", sa.Float, nullable=False),
        sa.Column("avg_rank", sa.Float, nullable=True),
        sa.Column("platform_count", sa.Integer, nullable=True),
        sa.Column("genre_median_composite", sa.Float, nullable=False),
        sa.Column("genre_median_velocity", sa.Float, nullable=False),
        sa.Column("genre_track_count", sa.Integer, nullable=False),
        sa.Column("composite_ratio", sa.Float, nullable=False),
        sa.Column("velocity_ratio", sa.Float, nullable=False),
        sa.Column("breakout_score", sa.Float, nullable=False),
        sa.Column("audio_features", postgresql.JSON, nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome_score", sa.Float, nullable=True),
        sa.Column("outcome_label", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_breakout_genre_date", "breakout_events", ["genre_id", sa.text("detection_date DESC")])
    op.create_index("idx_breakout_track", "breakout_events", ["track_id"])
    op.create_index("idx_breakout_unresolved", "breakout_events", ["resolved_at"],
                     postgresql_where=sa.text("resolved_at IS NULL"))

    op.create_table(
        "genre_feature_deltas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("genre_id", sa.String(100), nullable=False),
        sa.Column("window_start", sa.Date, nullable=False),
        sa.Column("window_end", sa.Date, nullable=False),
        sa.Column("breakout_count", sa.Integer, nullable=False),
        sa.Column("baseline_count", sa.Integer, nullable=False),
        sa.Column("deltas_json", postgresql.JSON, nullable=False),
        sa.Column("significance_json", postgresql.JSON, nullable=False),
        sa.Column("top_differentiators", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_gfd_genre_window", "genre_feature_deltas", ["genre_id", sa.text("window_end DESC")],
                     unique=True)

    op.create_table(
        "genre_lyrical_analysis",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("genre_id", sa.String(100), nullable=False),
        sa.Column("window_end", sa.Date, nullable=False),
        sa.Column("breakout_count", sa.Integer, nullable=False),
        sa.Column("baseline_count", sa.Integer, nullable=False),
        sa.Column("analysis_json", postgresql.JSON, nullable=False),
        sa.Column("llm_call_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_gla_genre_window", "genre_lyrical_analysis", ["genre_id", sa.text("window_end DESC")],
                     unique=True)

    op.create_table(
        "model_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("model_type", sa.String(50), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("training_rows", sa.Integer, nullable=False),
        sa.Column("feature_count", sa.Integer, nullable=False),
        sa.Column("metrics_json", postgresql.JSON, nullable=False),
        sa.Column("model_path", sa.String(500), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("model_runs")
    op.drop_index("idx_gla_genre_window", table_name="genre_lyrical_analysis")
    op.drop_table("genre_lyrical_analysis")
    op.drop_index("idx_gfd_genre_window", table_name="genre_feature_deltas")
    op.drop_table("genre_feature_deltas")
    op.drop_index("idx_breakout_unresolved", table_name="breakout_events")
    op.drop_index("idx_breakout_track", table_name="breakout_events")
    op.drop_index("idx_breakout_genre_date", table_name="breakout_events")
    op.drop_table("breakout_events")
