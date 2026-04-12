"""Add agent_registry, tools_registry, agent_tool_grants

Revision ID: 011
Revises: 010
Create Date: 2026-04-12

Settings tab data model: catalog of agents (14, marketing spec §12 + new
Submissions Agent), catalog of tools/credentials, and a many-to-many
grants table for which agent has access to which tool.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_registry",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("code_letter", sa.String(2), nullable=True),
        sa.Column("purpose", sa.Text, nullable=False),
        sa.Column("instructions", sa.Text, nullable=True),
        sa.Column("skills", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("actions", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("interdependencies", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("enabled", sa.Boolean, server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "tools_registry",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("api_kind", sa.String(30), nullable=False),
        sa.Column("auth_kind", sa.String(30), nullable=False),
        sa.Column("credential_env_vars", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("documentation_url", sa.String(500), nullable=True),
        sa.Column("cost_model", sa.String(200), nullable=True),
        sa.Column("automation_class", sa.String(2), nullable=True),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("capabilities", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "agent_tool_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", sa.String(50),
                  sa.ForeignKey("agent_registry.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_id", sa.String(80),
                  sa.ForeignKey("tools_registry.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", sa.String(200), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("granted_by", sa.String(100), nullable=True),
        sa.UniqueConstraint("agent_id", "tool_id", name="agent_tool_unique"),
    )


def downgrade() -> None:
    op.drop_table("agent_tool_grants")
    op.drop_table("tools_registry")
    op.drop_table("agent_registry")
