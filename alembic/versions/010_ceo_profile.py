"""Add ceo_profile single-row table

Revision ID: 010
Revises: 009
Create Date: 2026-04-12

CEO contact info for agent escalations (CEO Action Agent per
soundpulse_artist_release_marketing_spec.md §4.3 + §12.M).
Single-row enforced via CHECK (id = 1).
"""

from alembic import op
import sqlalchemy as sa


revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ceo_profile",
        sa.Column("id", sa.Integer, primary_key=True, server_default="1"),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("telegram_handle", sa.String(100), nullable=True),
        sa.Column("telegram_chat_id", sa.String(100), nullable=True),
        sa.Column("slack_channel", sa.String(100), nullable=True),
        sa.Column("preferred_channel", sa.String(20), server_default="email", nullable=True),
        sa.Column("escalation_severity_threshold", sa.String(20), server_default="medium", nullable=True),
        sa.Column("quiet_hours_start", sa.Time, nullable=True),
        sa.Column("quiet_hours_end", sa.Time, nullable=True),
        sa.Column("timezone", sa.String(50), server_default="UTC", nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("id = 1", name="ceo_profile_singleton"),
        sa.CheckConstraint(
            "preferred_channel IN ('email','phone','telegram','slack')",
            name="ceo_profile_channel_valid",
        ),
        sa.CheckConstraint(
            "escalation_severity_threshold IN ('low','medium','high','critical')",
            name="ceo_profile_severity_valid",
        ),
    )
    op.execute("INSERT INTO ceo_profile (id) VALUES (1)")


def downgrade() -> None:
    op.drop_table("ceo_profile")
