"""Add backtest_results table

Revision ID: 005
Revises: 004
Create Date: 2026-04-03
"""

from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backtest_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("evaluation_date", sa.Date, nullable=False),
        sa.Column("entity_type", sa.String(10), nullable=True),
        sa.Column("genre_filter", sa.String(200), nullable=True),
        sa.Column("horizon", sa.String(5), nullable=False, server_default="7d"),
        sa.Column("mae", sa.Float, nullable=True),
        sa.Column("rmse", sa.Float, nullable=True),
        sa.Column("precision_score", sa.Float, nullable=True),
        sa.Column("recall_score", sa.Float, nullable=True),
        sa.Column("f1_score", sa.Float, nullable=True),
        sa.Column("auc_roc", sa.Float, nullable=True),
        sa.Column("sample_count", sa.Integer, server_default="0"),
        sa.Column("positive_count", sa.Integer, server_default="0"),
        sa.Column("predicted_avg", sa.Float, nullable=True),
        sa.Column("actual_rate", sa.Float, nullable=True),
        sa.Column("model_version", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), server_default="running"),
        sa.Column("details_json", sa.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_backtest_run_date", "backtest_results", ["run_id", "evaluation_date"])
    op.create_index("idx_backtest_genre_date", "backtest_results", ["genre_filter", "evaluation_date"])


def downgrade() -> None:
    op.drop_index("idx_backtest_genre_date", table_name="backtest_results")
    op.drop_index("idx_backtest_run_date", table_name="backtest_results")
    op.drop_table("backtest_results")
