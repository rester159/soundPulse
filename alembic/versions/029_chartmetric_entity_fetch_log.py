"""Generic per-entity-per-endpoint freshness tracker.

Revision ID: 029
Revises: 028
Create Date: 2026-04-14

Introduces `chartmetric_entity_fetch_log` — the canonical "when was
this entity last fetched via this endpoint?" signal for any planner.

Not every endpoint writes to a dedicated time-series table (e.g.
artist_stats merges into `artists.metadata_json`), so reading
freshness from the data table is not a general solution. The fetch
log decouples freshness tracking from the specific data layout.

Schema is intentionally minimal: (entity_type, entity_id, endpoint_key)
composite PK, last_fetched_at + last_status. Handlers upsert this
row at the end of a successful parse. Planners order by
`last_fetched_at NULLS FIRST` to get the stalest entities.

This table is NOT authoritative for any user-facing data — it's a
pure coordination aid for the ingest pipeline. Deleting it would
not lose information; the next planner cycle would re-queue
everything at the "never fetched" priority and move on.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chartmetric_entity_fetch_log",
        sa.Column("entity_type", sa.Text, nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("endpoint_key", sa.Text, nullable=False),
        sa.Column(
            "last_fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_status", sa.SmallInteger, nullable=True),
        sa.PrimaryKeyConstraint(
            "entity_type", "entity_id", "endpoint_key",
            name="pk_cm_entity_fetch_log",
        ),
    )
    # Planners need to find the stalest rows per (entity_type, endpoint_key)
    # quickly. This covering index supports that access pattern without a
    # full table scan once the row count gets interesting.
    op.create_index(
        "idx_cm_fetch_log_stale",
        "chartmetric_entity_fetch_log",
        ["entity_type", "endpoint_key", "last_fetched_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_cm_fetch_log_stale", table_name="chartmetric_entity_fetch_log")
    op.drop_table("chartmetric_entity_fetch_log")
