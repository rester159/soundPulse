"""web_research_jobs — BlackTip browser-driven research queue (#31)

Revision ID: 038
Revises: 037
Create Date: 2026-04-19

User asked for a hybrid blueprint research path: Wikipedia REST inline
for the fast common case (already shipped), and BlackTip browser-driven
research for hyper-niche subgenres where Wikipedia is thin and we need
Allmusic / RYM / Pitchfork etc.

This migration adds the queue table the portal-worker (Node + Playwright
via BlackTip) polls. Mirrors the ascap_submissions pattern: API queues
a row, worker claims via SELECT FOR UPDATE SKIP LOCKED, posts result
back via /admin/worker/ack.

Schema:
  web_research_jobs (
    id            UUID PK
    target_kind   TEXT — 'genre_research' (more later: 'artist_research' etc)
    query         TEXT — what to research, free-form prompt for the worker
    genre_id      TEXT NULL — for blueprint research, links back to genre
    blueprint_id  UUID NULL — if the research is for a specific blueprint
    status        TEXT — 'pending' | 'in_progress' | 'completed' | 'failed'
    claimed_by    TEXT NULL — worker_id when in_progress
    claimed_at    TIMESTAMPTZ NULL
    completed_at  TIMESTAMPTZ NULL
    result_text   TEXT NULL — concatenated article text the worker fetched
    sources       JSONB NULL — list of {url, title} actually visited
    error         TEXT NULL
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
  )

Indexes: (status, created_at) for the worker's claim query;
         (genre_id) for surfacing per-genre history in the UI.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "web_research_jobs",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True) if hasattr(sa.dialects, "postgresql") else sa.Text,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("target_kind", sa.Text, nullable=False),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("genre_id", sa.Text, nullable=True),
        sa.Column(
            "blueprint_id",
            sa.dialects.postgresql.UUID(as_uuid=True) if hasattr(sa.dialects, "postgresql") else sa.Text,
            nullable=True,
        ),
        sa.Column(
            "status", sa.Text, nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("claimed_by", sa.Text, nullable=True),
        sa.Column(
            "claimed_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column("result_text", sa.Text, nullable=True),
        sa.Column(
            "sources",
            sa.dialects.postgresql.JSONB if hasattr(sa.dialects.postgresql, "JSONB") else sa.JSON,
            nullable=True,
        ),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_check_constraint(
        "ck_web_research_jobs_status",
        "web_research_jobs",
        "status IN ('pending','in_progress','completed','failed')",
    )
    op.create_index(
        "idx_web_research_jobs_status_created",
        "web_research_jobs",
        ["status", "created_at"],
    )
    op.create_index(
        "idx_web_research_jobs_genre_id",
        "web_research_jobs",
        ["genre_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_web_research_jobs_genre_id", table_name="web_research_jobs")
    op.drop_index("idx_web_research_jobs_status_created", table_name="web_research_jobs")
    op.drop_constraint(
        "ck_web_research_jobs_status", "web_research_jobs", type_="check"
    )
    op.drop_table("web_research_jobs")
