"""rights_holders — canonical publishers / writers / composers (polymorphic)

Revision ID: 036
Revises: 035
Create Date: 2026-04-18

User asked for a single place to add new publishers, writers, and composers
that the song-rights pipeline (PRO submissions, MLC DDEX, neighboring rights)
can reference by ID instead of duplicating contact + IPI + PRO info on every
songs_master row's writers/publishers JSONB blobs.

One polymorphic table because publishers, writers, and composers share ~90%
of their fields (legal name, IPI, PRO affiliation, contact, splits, notes)
and a single `kind` column lets the same CRUD endpoints + UI handle all
three. A CHECK constraint pins kind to the three allowed values so a typo
can't silently create a fourth category.

Schema:
  rights_holders (
    id                       UUID PK
    kind                     TEXT NOT NULL — 'publisher' | 'writer' | 'composer'
    legal_name               TEXT NOT NULL — registered legal entity name
    stage_name               TEXT NULL     — pen name / public alias
    ipi_number               TEXT NULL     — ASCAP/BMI/SESAC/etc. rights-org id
    isni                     TEXT NULL     — International Standard Name Identifier
    pro_affiliation          TEXT NULL     — 'ASCAP' | 'BMI' | 'SESAC' | 'GMR' | 'PRS' | etc.
    publisher_company_name   TEXT NULL     — for writers/composers signed to a publisher
    email                    TEXT NULL
    phone                    TEXT NULL
    address                  TEXT NULL
    tax_id                   TEXT NULL     — W-9 / W-8 reference
    default_split_percent    FLOAT NULL    — typical % this party gets on a song
    notes                    TEXT NULL
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
  )

Indexes: (kind, legal_name) for the per-kind list queries the UI runs.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rights_holders",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True) if hasattr(sa.dialects, "postgresql") else sa.Text,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("legal_name", sa.Text, nullable=False),
        sa.Column("stage_name", sa.Text, nullable=True),
        sa.Column("ipi_number", sa.Text, nullable=True),
        sa.Column("isni", sa.Text, nullable=True),
        sa.Column("pro_affiliation", sa.Text, nullable=True),
        sa.Column("publisher_company_name", sa.Text, nullable=True),
        sa.Column("email", sa.Text, nullable=True),
        sa.Column("phone", sa.Text, nullable=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("tax_id", sa.Text, nullable=True),
        sa.Column("default_split_percent", sa.Float, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_check_constraint(
        "ck_rights_holders_kind",
        "rights_holders",
        "kind IN ('publisher','writer','composer')",
    )
    op.create_check_constraint(
        "ck_rights_holders_split_range",
        "rights_holders",
        "default_split_percent IS NULL OR (default_split_percent >= 0 AND default_split_percent <= 100)",
    )
    op.create_index(
        "idx_rights_holders_kind_name",
        "rights_holders",
        ["kind", "legal_name"],
    )


def downgrade() -> None:
    op.drop_index("idx_rights_holders_kind_name", table_name="rights_holders")
    op.drop_constraint(
        "ck_rights_holders_split_range", "rights_holders", type_="check"
    )
    op.drop_constraint("ck_rights_holders_kind", "rights_holders", type_="check")
    op.drop_table("rights_holders")
