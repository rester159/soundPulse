"""Add llm_calls table for LLM usage logging

Revision ID: 006
Revises: 005
Create Date: 2026-04-11

CLAUDE.md mandates "every LLM call must be logged" with model, input
tokens, output tokens, estimated cost, timestamp, and action type. This
migration creates the table that satisfies that requirement. Proposed in
schema.md Part II; shipped here with minimal changes.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=True),
        sa.Column("output_tokens", sa.Integer, nullable=True),
        sa.Column("total_tokens", sa.Integer, nullable=True),
        sa.Column("cost_cents", sa.Integer, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("caller", sa.String(200), nullable=True),
        sa.Column("context_id", sa.String(200), nullable=True),
        sa.Column("success", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("error_message", sa.String(2000), nullable=True),
        sa.Column("metadata_json", postgresql.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_llm_call_action_date",
        "llm_calls",
        ["action_type", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_llm_call_model_date",
        "llm_calls",
        ["model", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_llm_call_model_date", table_name="llm_calls")
    op.drop_index("idx_llm_call_action_date", table_name="llm_calls")
    op.drop_table("llm_calls")
