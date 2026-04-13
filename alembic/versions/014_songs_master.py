"""Add songs_master — canonical song row (§17)

Revision ID: 014
Revises: 013
Create Date: 2026-04-12

Every song the system produces has exactly one row here. Field families
match PRD v3 §17: identity, classification, audio analysis, vocals,
lyrics, rights, distribution, release planning, artwork, marketing,
generation metadata, QA, ML predictions, actuals, lifecycle.

FKs to tables that don't exist yet (releases, song_qa_reports,
artist_visual_assets) are stored as nullable UUIDs without constraints.
When those tables land (T-101, T-104, T-106), ALTER TABLE will add the
constraints. Keeps this migration self-contained.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "songs_master",
        # Identity
        sa.Column("song_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("internal_code", sa.Text, unique=True, nullable=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("title_sort", sa.Text),
        sa.Column("alt_titles", postgresql.ARRAY(sa.Text)),
        sa.Column("subtitle", sa.Text),
        sa.Column("version_type", sa.String(30)),
        sa.Column("parent_song_id", postgresql.UUID(as_uuid=True)),  # self-ref, no FK yet
        # Classification
        sa.Column("primary_artist_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ai_artists.artist_id"), nullable=False),
        sa.Column("featured_artist_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True))),
        sa.Column("blueprint_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("song_blueprints.id"), nullable=False),
        sa.Column("primary_genre", sa.String(100), nullable=False),
        sa.Column("subgenres", postgresql.ARRAY(sa.Text)),
        sa.Column("mood_tags", postgresql.ARRAY(sa.Text)),
        sa.Column("content_rating", sa.String(10), nullable=False, server_default="mild"),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        # Audio analysis
        sa.Column("tempo_bpm", sa.Float),
        sa.Column("key_pc", sa.Integer),
        sa.Column("key_mode", sa.Integer),
        sa.Column("key_camelot", sa.String(4)),
        sa.Column("time_signature", sa.Integer),
        sa.Column("duration_seconds", sa.Integer),
        sa.Column("loudness_lufs", sa.Float),
        sa.Column("energy", sa.Float),
        sa.Column("danceability", sa.Float),
        sa.Column("valence", sa.Float),
        sa.Column("acousticness", sa.Float),
        sa.Column("instrumentalness", sa.Float),
        sa.Column("speechiness", sa.Float),
        sa.Column("liveness", sa.Float),
        # Vocals
        sa.Column("vocal_profile", postgresql.JSONB),
        sa.Column("has_explicit_vocals", sa.Boolean, server_default="FALSE"),
        sa.Column("vocal_mix_ratio", sa.Float),
        # Lyrics
        sa.Column("lyric_text", sa.Text),
        sa.Column("lyric_themes", postgresql.ARRAY(sa.Text)),
        sa.Column("lyric_structure", postgresql.JSONB),
        sa.Column("lyric_snippet_candidates", postgresql.JSONB),
        sa.Column("vocabulary_tags", postgresql.ARRAY(sa.Text)),
        # Rights
        sa.Column("writers", postgresql.JSONB),
        sa.Column("publishers", postgresql.JSONB),
        sa.Column("master_owner", sa.Text, server_default="SoundPulse Records LLC"),
        sa.Column("iswc", sa.String(20)),
        sa.Column("copyright_year", sa.Integer),
        sa.Column("copyright_line", sa.Text),
        # Distribution
        sa.Column("isrc", sa.String(15), unique=True),
        sa.Column("upc", sa.String(20)),
        sa.Column("distributor", sa.String(30)),
        sa.Column("distributor_work_id", sa.Text),
        sa.Column("territory_rights", postgresql.ARRAY(sa.Text)),
        # Release planning
        sa.Column("release_id", postgresql.UUID(as_uuid=True)),  # FK added when T-101 lands
        sa.Column("scheduled_release_date", sa.Date),
        sa.Column("actual_release_date", sa.Date),
        sa.Column("pre_save_date", sa.Date),
        sa.Column("release_strategy", sa.String(30)),
        # Artwork
        sa.Column("primary_artwork_asset_id", postgresql.UUID(as_uuid=True)),  # FK later
        sa.Column("alt_artwork_asset_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True))),
        sa.Column("artwork_brief", sa.Text),
        # Marketing
        sa.Column("marketing_hook", sa.Text),
        sa.Column("marketing_tags", postgresql.ARRAY(sa.Text)),
        sa.Column("playlist_fit", postgresql.ARRAY(sa.Text)),
        sa.Column("target_audience_tags", postgresql.ARRAY(sa.Text)),
        sa.Column("pr_angle", sa.Text),
        # Generation metadata
        sa.Column("generation_provider", sa.String(30)),
        sa.Column("generation_provider_job_id", sa.Text),
        sa.Column("generation_prompt", sa.Text),
        sa.Column("generation_params", postgresql.JSONB),
        sa.Column("generation_cost_usd", sa.Float),
        sa.Column("llm_call_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("llm_calls.id"), nullable=True),
        sa.Column("regeneration_count", sa.Integer, server_default="0"),
        # QA
        sa.Column("qa_report_id", postgresql.UUID(as_uuid=True)),  # FK when T-104 lands
        sa.Column("qa_pass", sa.Boolean),
        sa.Column("duplication_risk_score", sa.Float),
        # ML predictions (frozen at generation time)
        sa.Column("predicted_success_score", sa.Float),
        sa.Column("predicted_stream_range_low", sa.BigInteger),
        sa.Column("predicted_stream_range_median", sa.BigInteger),
        sa.Column("predicted_stream_range_high", sa.BigInteger),
        sa.Column("predicted_revenue_usd", sa.Float),
        sa.Column("prediction_model_version", sa.String(50)),
        sa.Column("prediction_confidence", sa.Float),
        # Actuals (updated by §46 revenue ingestion)
        sa.Column("actual_streams_30d", sa.BigInteger),
        sa.Column("actual_streams_90d", sa.BigInteger),
        sa.Column("actual_streams_lifetime", sa.BigInteger),
        sa.Column("actual_revenue_usd", sa.Float),
        sa.Column("outcome_label", sa.String(20)),  # hit | moderate | fizzle | unresolvable
        sa.Column("outcome_resolved_at", sa.DateTime(timezone=True)),
        # Lifecycle
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_songs_master_primary_artist", "songs_master", ["primary_artist_id"])
    op.create_index("idx_songs_master_blueprint",      "songs_master", ["blueprint_id"])
    op.create_index("idx_songs_master_release",        "songs_master", ["release_id"])
    op.create_index("idx_songs_master_status",         "songs_master", ["status"])
    op.create_index("idx_songs_master_release_date",   "songs_master", ["actual_release_date"])


def downgrade() -> None:
    op.drop_index("idx_songs_master_release_date", table_name="songs_master")
    op.drop_index("idx_songs_master_status",       table_name="songs_master")
    op.drop_index("idx_songs_master_release",      table_name="songs_master")
    op.drop_index("idx_songs_master_blueprint",    table_name="songs_master")
    op.drop_index("idx_songs_master_primary_artist", table_name="songs_master")
    op.drop_table("songs_master")
