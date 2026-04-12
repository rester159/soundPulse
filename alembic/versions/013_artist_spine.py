"""Add artist spine: song_blueprints, ai_artists, ceo_decisions, genre_config

Revision ID: 013
Revises: 012
Create Date: 2026-04-12

Phase 3 MVP-1 spine. Four tables, no cross-FKs to unbuilt tables so the
migration is self-contained. Field shapes match PRD v3 §17 DDL.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # song_blueprints -------------------------------------------------------
    op.create_table(
        "song_blueprints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("genre_id", sa.String(100), nullable=False),
        sa.Column("detected_via", sa.String(50), nullable=False,
                  server_default="breakout_engine_v2"),
        sa.Column("breakout_event_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
                  nullable=True),
        # Sonic profile
        sa.Column("target_tempo", sa.Float),
        sa.Column("target_key", sa.Integer),
        sa.Column("target_mode", sa.Integer),
        sa.Column("target_energy", sa.Float),
        sa.Column("target_danceability", sa.Float),
        sa.Column("target_valence", sa.Float),
        sa.Column("target_acousticness", sa.Float),
        sa.Column("target_loudness", sa.Float),
        # Lyrical profile
        sa.Column("target_themes", postgresql.ARRAY(sa.Text)),
        sa.Column("avoid_themes", postgresql.ARRAY(sa.Text)),
        sa.Column("vocabulary_tone", sa.String(50)),
        sa.Column("structural_pattern", postgresql.JSONB),
        # Assignment hints
        sa.Column("primary_genre", sa.String(100)),
        sa.Column("adjacent_genres", postgresql.ARRAY(sa.Text)),
        sa.Column("target_audience_tags", postgresql.ARRAY(sa.Text)),
        sa.Column("voice_requirements", postgresql.JSONB),
        # Production cues
        sa.Column("production_notes", sa.Text),
        sa.Column("reference_track_descriptors", postgresql.ARRAY(sa.Text)),
        # Predicted success
        sa.Column("predicted_success_score", sa.Float),
        sa.Column("quantification_snapshot", postgresql.JSONB),
        # Smart prompt
        sa.Column("smart_prompt_text", sa.Text, nullable=False),
        sa.Column("smart_prompt_rationale", postgresql.JSONB),
        # Lifecycle
        sa.Column("status", sa.String(30), nullable=False, server_default="pending_assignment"),
        sa.Column("assigned_artist_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_blueprints_status", "song_blueprints", ["status"])
    op.create_index("idx_blueprints_genre", "song_blueprints", ["genre_id"])

    # ai_artists ------------------------------------------------------------
    op.create_table(
        "ai_artists",
        sa.Column("artist_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("stage_name", sa.Text, nullable=False, unique=True),
        sa.Column("legal_name", sa.Text, nullable=False),
        sa.Column("age", sa.Integer),
        sa.Column("gender_presentation", sa.Text),
        sa.Column("ethnicity_heritage", sa.Text),
        sa.Column("provenance", sa.Text),
        sa.Column("early_life_summary", sa.Text),
        sa.Column("relationship_status", sa.Text),
        sa.Column("sexual_orientation", sa.Text),
        sa.Column("languages", postgresql.ARRAY(sa.Text)),
        sa.Column("primary_genre", sa.Text, nullable=False),
        sa.Column("adjacent_genres", postgresql.ARRAY(sa.Text)),
        sa.Column("influences", postgresql.ARRAY(sa.Text)),
        sa.Column("anti_influences", postgresql.ARRAY(sa.Text)),
        sa.Column("voice_dna", postgresql.JSONB, nullable=False),
        sa.Column("visual_dna", postgresql.JSONB, nullable=False),
        sa.Column("fashion_dna", postgresql.JSONB),
        sa.Column("lyrical_dna", postgresql.JSONB),
        sa.Column("persona_dna", postgresql.JSONB),
        sa.Column("social_dna", postgresql.JSONB),
        sa.Column("audience_tags", postgresql.ARRAY(sa.Text)),
        sa.Column("content_rating", sa.Text, server_default="mild"),
        sa.Column("roster_status", sa.Text, server_default="active"),
        sa.Column("song_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_released_at", sa.DateTime(timezone=True)),
        sa.Column("creation_trigger_blueprint_id", postgresql.UUID(as_uuid=True)),
        sa.Column("ceo_approved", sa.Boolean, server_default="FALSE"),
        sa.Column("ceo_approval_at", sa.DateTime(timezone=True)),
        sa.Column("ceo_notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_ai_artists_primary_genre", "ai_artists", ["primary_genre"])
    op.create_index("idx_ai_artists_status", "ai_artists", ["roster_status"])

    # ceo_decisions ---------------------------------------------------------
    op.create_table(
        "ceo_decisions",
        sa.Column("decision_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("decision_type", sa.String(50), nullable=False),
        # artist_assignment | paid_spend_cap | brand_pivot | takedown | tool_spend | policy_issue
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("proposal", sa.String(50), nullable=False),
        # reuse | create_new | approve | reject
        sa.Column("data", postgresql.JSONB, nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        # pending | sent | approved | approved_with_modifications | rejected | timed_out
        sa.Column("sent_via", sa.String(30)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("response_at", sa.DateTime(timezone=True)),
        sa.Column("response_payload", postgresql.JSONB),
        sa.Column("timeout_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_ceo_decisions_status", "ceo_decisions", ["status"])
    op.create_index("idx_ceo_decisions_type", "ceo_decisions", ["decision_type"])
    op.create_index("idx_ceo_decisions_entity", "ceo_decisions", ["entity_type", "entity_id"])

    # genre_config ----------------------------------------------------------
    op.create_table(
        "genre_config",
        sa.Column("genre_id", sa.String(100), primary_key=True),
        sa.Column("reference_artist_count", sa.Integer, nullable=False, server_default="3"),
        sa.Column("reuse_threshold", sa.Float, nullable=False, server_default="0.68"),
        sa.Column("cooldown_days", sa.Integer, nullable=False, server_default="14"),
        sa.Column("max_artists_per_genre", sa.Integer),
        sa.Column("ceo_approval_required", sa.Boolean, nullable=False, server_default="TRUE"),
        sa.Column("notes", sa.Text),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )


def downgrade() -> None:
    op.drop_table("genre_config")
    op.drop_index("idx_ceo_decisions_entity", table_name="ceo_decisions")
    op.drop_index("idx_ceo_decisions_type", table_name="ceo_decisions")
    op.drop_index("idx_ceo_decisions_status", table_name="ceo_decisions")
    op.drop_table("ceo_decisions")
    op.drop_index("idx_ai_artists_status", table_name="ai_artists")
    op.drop_index("idx_ai_artists_primary_genre", table_name="ai_artists")
    op.drop_table("ai_artists")
    op.drop_index("idx_blueprints_genre", table_name="song_blueprints")
    op.drop_index("idx_blueprints_status", table_name="song_blueprints")
    op.drop_table("song_blueprints")
