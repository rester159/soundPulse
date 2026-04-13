"""Add visual_asset_blobs sidecar table for self-hosted image bytes

Revision ID: 017
Revises: 016
Create Date: 2026-04-12

Mirrors music_generation_audio — stores generated image bytes (artist
portraits, song covers) in Postgres bytea so they survive provider
delivery-URL expiry. Served via /api/v1/admin/visual/{asset_id}.png.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "visual_asset_blobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("artist_visual_assets.asset_id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("content_type", sa.String(50), nullable=False, server_default="image/png"),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("image_bytes", postgresql.BYTEA, nullable=False),
        sa.Column("downloaded_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("source_url", sa.Text),
    )


def downgrade() -> None:
    op.drop_table("visual_asset_blobs")
