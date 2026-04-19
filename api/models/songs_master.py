import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class SongMaster(Base):
    """
    Canonical song row (§17, §27). Every song the system produces has
    exactly one row here. ~80 fields across 13 field families.

    FKs to tables that don't yet exist (releases, qa_reports,
    artwork_assets) are stored as plain UUIDs without constraints.
    Those constraints land in later migrations.
    """
    __tablename__ = "songs_master"

    # Identity
    song_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    internal_code: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    title_sort: Mapped[str | None] = mapped_column(Text, nullable=True)
    alt_titles: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    subtitle: Mapped[str | None] = mapped_column(Text, nullable=True)
    version_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    parent_song_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Classification
    primary_artist_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    featured_artist_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=True
    )
    blueprint_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    primary_genre: Mapped[str] = mapped_column(String(100), nullable=False)
    subgenres: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    mood_tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    content_rating: Mapped[str] = mapped_column(String(10), nullable=False, default="mild")
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    # Per-song theme override picked at generation time (#17 composition
    # pivot). Picklist values: 'artist_default' | 'genre_default' |
    # 'love_relationships' | 'sex' | 'introspection' | 'family' | 'god'
    # | 'partying' | <free-text>. Null = caller didn't pick (treated as
    # artist_default by the orchestrator's theme resolver).
    theme: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Audio analysis
    tempo_bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    key_pc: Mapped[int | None] = mapped_column(Integer, nullable=True)
    key_mode: Mapped[int | None] = mapped_column(Integer, nullable=True)
    key_camelot: Mapped[str | None] = mapped_column(String(4), nullable=True)
    time_signature: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    loudness_lufs: Mapped[float | None] = mapped_column(Float, nullable=True)
    energy: Mapped[float | None] = mapped_column(Float, nullable=True)
    danceability: Mapped[float | None] = mapped_column(Float, nullable=True)
    valence: Mapped[float | None] = mapped_column(Float, nullable=True)
    acousticness: Mapped[float | None] = mapped_column(Float, nullable=True)
    instrumentalness: Mapped[float | None] = mapped_column(Float, nullable=True)
    speechiness: Mapped[float | None] = mapped_column(Float, nullable=True)
    liveness: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Vocals
    vocal_profile: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    has_explicit_vocals: Mapped[bool] = mapped_column(Boolean, default=False)
    vocal_mix_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Lyrics
    lyric_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    lyric_themes: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    lyric_structure: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    lyric_snippet_candidates: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    vocabulary_tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)

    # Rights
    writers: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    publishers: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    master_owner: Mapped[str | None] = mapped_column(Text, default="SoundPulse Records LLC")
    iswc: Mapped[str | None] = mapped_column(String(20), nullable=True)
    copyright_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    copyright_line: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Distribution
    isrc: Mapped[str | None] = mapped_column(String(15), unique=True, nullable=True)
    upc: Mapped[str | None] = mapped_column(String(20), nullable=True)
    distributor: Mapped[str | None] = mapped_column(String(30), nullable=True)
    distributor_work_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    territory_rights: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)

    # Release planning
    release_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    scheduled_release_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_release_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    pre_save_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    release_strategy: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Artwork
    primary_artwork_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    alt_artwork_asset_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=True
    )
    artwork_brief: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Marketing
    marketing_hook: Mapped[str | None] = mapped_column(Text, nullable=True)
    marketing_tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    playlist_fit: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    target_audience_tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    pr_angle: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Generation metadata
    generation_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    generation_provider_job_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation_params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    generation_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    llm_call_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    regeneration_count: Mapped[int] = mapped_column(Integer, default=0)

    # QA
    qa_report_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    qa_pass: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    duplication_risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ML predictions (frozen at generation time)
    predicted_success_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted_stream_range_low: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    predicted_stream_range_median: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    predicted_stream_range_high: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    predicted_revenue_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    prediction_model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    prediction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Actuals
    actual_streams_30d: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actual_streams_90d: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actual_streams_lifetime: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actual_revenue_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    outcome_resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Lifecycle
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
