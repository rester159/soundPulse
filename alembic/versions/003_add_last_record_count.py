"""Add last_record_count column to scraper_configs.

Revision ID: 003
Revises: 002
"""

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scraper_configs",
        sa.Column("last_record_count", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scraper_configs", "last_record_count")
