"""Add scraper_configs table

Revision ID: 002
Revises: 001
Create Date: 2026-03-22
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scraper_configs",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("interval_hours", sa.Float, nullable=False, server_default="6.0"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(50), nullable=True),
        sa.Column("last_error", sa.String(2000), nullable=True),
        sa.Column("config_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Seed default Spotify config
    op.execute("""
        INSERT INTO scraper_configs (id, enabled, interval_hours, config_json)
        VALUES ('spotify', true, 6.0, '{}')
        ON CONFLICT (id) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table("scraper_configs")
