import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class SongBlueprint(Base):
    """
    A concrete song blueprint produced by the breakout engine + smart prompt
    pipeline. One row per generated opportunity that is ready for artist
    assignment (§22) and eventual song generation (§24).
    """
    __tablename__ = "song_blueprints"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    genre_id: Mapped[str] = mapped_column(String(100), nullable=False)
    detected_via: Mapped[str] = mapped_column(String(50), nullable=False, default="breakout_engine_v2")
    breakout_event_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=True
    )

    target_tempo: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_key: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_mode: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_energy: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_danceability: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_valence: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_acousticness: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_loudness: Mapped[float | None] = mapped_column(Float, nullable=True)

    target_themes: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    avoid_themes: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    vocabulary_tone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    structural_pattern: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    primary_genre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    adjacent_genres: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    target_audience_tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    voice_requirements: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    production_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_track_descriptors: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)

    predicted_success_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantification_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # DEPRECATED post-#16 (composition pivot): orchestrator no longer
    # reads smart_prompt_text. Kept nullable for back-compat with
    # legacy rows; new blueprints don't set it.
    smart_prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    smart_prompt_rationale: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # User-facing name. Forks of the same genre's base blueprint each
    # get a name to disambiguate them in the UI. Backfilled from
    # primary_genre for legacy rows in migration 037.
    name: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Marks the ONE base blueprint per genre. Partial unique index
    # `uq_song_blueprints_genre_default` enforces at-most-one.
    is_genre_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending_assignment")
    assigned_artist_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
