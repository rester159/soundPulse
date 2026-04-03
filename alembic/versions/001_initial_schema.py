"""Initial schema

Revision ID: 001
Revises: None
Create Date: 2026-03-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # Create genre_status enum
    genre_status = postgresql.ENUM("active", "deprecated", "proposed", name="genre_status", create_type=False)
    genre_status.create(op.get_bind(), checkfirst=True)

    # Genres table (first, since it has no FK dependencies)
    op.create_table(
        "genres",
        sa.Column("id", sa.String(200), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("parent_id", sa.String(200), sa.ForeignKey("genres.id"), nullable=True),
        sa.Column("root_category", sa.String(50), nullable=False),
        sa.Column("depth", sa.Integer, nullable=False, server_default="0"),
        sa.Column("spotify_genres", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("apple_music_genres", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("musicbrainz_tags", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("chartmetric_genres", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("audio_profile", postgresql.JSON, nullable=True),
        sa.Column("adjacent_genres", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("status", genre_status, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_genre_parent", "genres", ["parent_id"])
    op.create_index("idx_genre_root", "genres", ["root_category"])

    # Artists table
    op.create_table(
        "artists",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("spotify_id", sa.String(100), unique=True, nullable=True),
        sa.Column("apple_music_id", sa.String(100), unique=True, nullable=True),
        sa.Column("tiktok_handle", sa.String(200), nullable=True),
        sa.Column("chartmetric_id", sa.Integer, nullable=True),
        sa.Column("musicbrainz_id", sa.String(100), nullable=True),
        sa.Column("image_url", sa.String(1000), nullable=True),
        sa.Column("genres", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("metadata_json", postgresql.JSON, server_default="{}"),
        sa.Column("canonical", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_artist_name", "artists", ["name"])
    op.create_index("idx_artist_spotify", "artists", ["spotify_id"], postgresql_where=sa.text("spotify_id IS NOT NULL"))
    op.execute("CREATE INDEX idx_artist_name_trgm ON artists USING gist (name gist_trgm_ops)")

    # Tracks table
    op.create_table(
        "tracks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("artist_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("artists.id"), nullable=False),
        sa.Column("isrc", sa.String(20), unique=True, nullable=True),
        sa.Column("spotify_id", sa.String(100), unique=True, nullable=True),
        sa.Column("apple_music_id", sa.String(100), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("release_date", sa.Date, nullable=True),
        sa.Column("genres", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("audio_features", postgresql.JSON, nullable=True),
        sa.Column("metadata_json", postgresql.JSON, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_track_title", "tracks", ["title"])
    op.create_index("idx_track_isrc", "tracks", ["isrc"], postgresql_where=sa.text("isrc IS NOT NULL"))
    op.create_index("idx_track_spotify", "tracks", ["spotify_id"], postgresql_where=sa.text("spotify_id IS NOT NULL"))
    op.execute("CREATE INDEX idx_track_title_trgm ON tracks USING gist (title gist_trgm_ops)")
    op.execute("CREATE INDEX idx_track_fts ON tracks USING gin (to_tsvector('english', title))")

    # Trending snapshots table
    op.create_table(
        "trending_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(10), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("platform_rank", sa.Integer, nullable=True),
        sa.Column("platform_score", sa.Float, nullable=True),
        sa.Column("normalized_score", sa.Float, nullable=False, server_default="0"),
        sa.Column("velocity", sa.Float, nullable=True),
        sa.Column("signals_json", postgresql.JSON, server_default="{}"),
        sa.Column("composite_score", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_snapshot", "trending_snapshots", ["entity_type", "entity_id", "snapshot_date", "platform"])
    op.create_index("idx_trending_entity_date", "trending_snapshots", ["entity_id", sa.text("snapshot_date DESC")])
    op.create_index("idx_trending_platform_date", "trending_snapshots", ["platform", sa.text("snapshot_date DESC")])
    op.create_index("idx_trending_snapshot_date", "trending_snapshots", ["snapshot_date"])

    # Predictions table
    op.create_table(
        "predictions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(10), nullable=False),
        sa.Column("entity_id", sa.String(200), nullable=False),
        sa.Column("horizon", sa.String(5), nullable=False),
        sa.Column("predicted_score", sa.Float, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("model_version", sa.String(20), nullable=False),
        sa.Column("features_json", postgresql.JSON, server_default="{}"),
        sa.Column("predicted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_score", sa.Float, nullable=True),
        sa.Column("error", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_prediction_horizon", "predictions", ["horizon", sa.text("predicted_at DESC")])
    op.create_index("idx_prediction_entity", "predictions", ["entity_id", "horizon"])

    # Feedback table
    op.create_table(
        "feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("prediction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("predictions.id"), nullable=False),
        sa.Column("actual_score", sa.Float, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("submitted_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # API Keys table
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("key_prefix", sa.String(20), nullable=False),
        sa.Column("key_last4", sa.String(4), nullable=False),
        sa.Column("tier", sa.String(10), nullable=False, server_default="free"),
        sa.Column("owner", sa.String(200), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_api_key_hash", "api_keys", ["key_hash"])


def downgrade() -> None:
    op.drop_table("api_keys")
    op.drop_table("feedback")
    op.drop_table("predictions")
    op.drop_table("trending_snapshots")
    op.drop_table("tracks")
    op.drop_table("artists")
    op.drop_table("genres")
    op.execute("DROP TYPE IF EXISTS genre_status")
