"""Add edge_profile to ai_artists + pop_culture_references table

Revision ID: 018
Revises: 017
Create Date: 2026-04-13

Powers the edgy-themes pipeline:

  1. ai_artists.edge_profile — per-artist dial that controls lyrical tone
     (clean_edge | flirty_edge | savage_edge). Read by smart_prompt.py
     to scale the Sabrina-Carpenter-level edge rules in the system prompt
     up or down per persona.

  2. pop_culture_references — rolling table of things the lyric writer
     can reference. Seeded by a weekly LLM scraper agent; injected into
     smart_prompt as an optional-hooks block; pruned when expires_at
     passes. Every reference decays because nothing ages worse than a
     stale meme.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_artists",
        sa.Column(
            "edge_profile",
            sa.Text,
            nullable=True,
            comment="clean_edge | flirty_edge | savage_edge — drives lyrical tone",
        ),
    )
    op.create_check_constraint(
        "ck_ai_artists_edge_profile",
        "ai_artists",
        "edge_profile IS NULL OR edge_profile IN ('clean_edge', 'flirty_edge', 'savage_edge')",
    )

    op.create_table(
        "pop_culture_references",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("reference_type", sa.Text, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("context", sa.Text, nullable=True),
        sa.Column("source", sa.Text, nullable=True),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("genres", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column(
            "edge_tiers",
            postgresql.ARRAY(sa.Text),
            nullable=False,
            server_default="{flirty_edge,savage_edge}",
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("peak_date", sa.Date, nullable=True),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW() + INTERVAL '90 days'"),
            nullable=False,
        ),
        sa.Column("usage_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_pop_culture_references_type",
        "pop_culture_references",
        "reference_type IN ('tiktok_sound','tiktok_dance','tiktok_phrase',"
        "'viral_meme','show_reference','brand','app','gaming','celeb_moment',"
        "'news_event','lyric_phrase','slang')",
    )
    op.create_index(
        "ix_pop_culture_references_expires_at",
        "pop_culture_references",
        ["expires_at"],
    )
    op.create_index(
        "ix_pop_culture_references_genres",
        "pop_culture_references",
        ["genres"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_pop_culture_references_genres", table_name="pop_culture_references")
    op.drop_index("ix_pop_culture_references_expires_at", table_name="pop_culture_references")
    op.drop_constraint("ck_pop_culture_references_type", "pop_culture_references", type_="check")
    op.drop_table("pop_culture_references")
    op.drop_constraint("ck_ai_artists_edge_profile", "ai_artists", type_="check")
    op.drop_column("ai_artists", "edge_profile")
